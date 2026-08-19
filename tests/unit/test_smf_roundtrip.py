"""B1 -- SMF reader/writer/VLQ.

Najrizicniji sloj: ako ovdje nesto pukne, korisnikov MIDI se tiho kvari.
"""

from __future__ import annotations

import struct

import pytest

from pa800_enhancer.smf.errors import SmfStructureError
from pa800_enhancer.smf.reader import SmfReader
from pa800_enhancer.smf.vlq import decode_vlq, encode_vlq
from pa800_enhancer.smf.writer import PreserveWriter, SmfWriter

from tests.conftest import build_midi


class TestVlq:
    @pytest.mark.parametrize(
        "value", [0, 1, 63, 127, 128, 255, 8192, 16383, 16384, 0x0FFFFFFF]
    )
    def test_roundtrip(self, value: int) -> None:
        encoded = encode_vlq(value)
        decoded, consumed = decode_vlq(encoded, 0)
        assert decoded == value
        assert consumed == len(encoded)

    def test_canonical_lengths(self) -> None:
        assert encode_vlq(0) == b"\x00"
        assert encode_vlq(127) == b"\x7f"
        assert encode_vlq(128) == b"\x81\x00"
        assert encode_vlq(16383) == b"\xff\x7f"

    def test_truncated_raises(self) -> None:
        with pytest.raises(Exception):
            decode_vlq(b"\x81", 0)


class TestReader:
    def test_reads_header(self, simple_midi_bytes: bytes) -> None:
        song = SmfReader().parse(simple_midi_bytes)
        assert song.header.format_type == 1
        assert song.header.ppq == 384
        assert len(song.tracks) == 1

    def test_rejects_missing_mthd(self) -> None:
        with pytest.raises(SmfStructureError):
            SmfReader().parse(b"XXXX" + b"\x00" * 20)

    def test_rejects_truncated_file(self) -> None:
        with pytest.raises(SmfStructureError):
            SmfReader().parse(b"MThd\x00\x00\x00\x06\x00\x01")

    def test_rejects_oversized_file(self) -> None:
        reader = SmfReader(max_file_size=32)
        with pytest.raises(SmfStructureError):
            reader.parse(build_midi())

    def test_running_status(self, running_status_midi) -> None:
        song = SmfReader().read(running_status_midi)
        note_ons = [
            e
            for t in song.tracks
            for e in t.events
            if e.message_type == 0x90 and e.data and e.data[1] > 0
        ]
        assert len(note_ons) == 2

    def test_multi_track_channels(self, multi_track_midi) -> None:
        song = SmfReader().read(multi_track_midi)
        assert song.header.format_type == 1
        assert len(song.tracks) == 3
        assert song.header.ppq == 192


class TestPreserveWriter:
    """Kljucna garancija: preserve mora vratiti IDENTICNE bajtove."""

    def test_byte_identical(self, simple_midi_bytes: bytes) -> None:
        song = SmfReader().parse(simple_midi_bytes)
        assert PreserveWriter.serialize(song) == simple_midi_bytes

    def test_byte_identical_multi_track(self, multi_track_midi) -> None:
        original = multi_track_midi.read_bytes()
        song = SmfReader().read(multi_track_midi)
        assert PreserveWriter.serialize(song) == original

    def test_byte_identical_running_status(self, running_status_midi) -> None:
        original = running_status_midi.read_bytes()
        song = SmfReader().read(running_status_midi)
        assert PreserveWriter.serialize(song) == original

    def test_byte_identical_dangling(self, dangling_note_midi) -> None:
        original = dangling_note_midi.read_bytes()
        song = SmfReader().read(dangling_note_midi)
        assert PreserveWriter.serialize(song) == original


class TestCanonicalWriter:
    def test_reparses_to_equivalent_model(self, simple_midi_bytes: bytes) -> None:
        reader = SmfReader()
        song = reader.parse(simple_midi_bytes)
        rewritten = SmfWriter().serialize(song)
        reparsed = reader.parse(rewritten)

        assert reparsed.header.format_type == song.header.format_type
        assert reparsed.header.ppq == song.header.ppq
        assert len(reparsed.tracks) == len(song.tracks)

    def test_stable_under_repeated_write(self, multi_track_midi) -> None:
        reader = SmfReader()
        writer = SmfWriter()
        song = reader.read(multi_track_midi)
        first = writer.serialize(song)
        second = writer.serialize(reader.parse(first))
        assert first == second, "kanonski zapis mora biti idempotentan"

    def test_preserves_note_count(self, multi_track_midi) -> None:
        reader = SmfReader()
        song = reader.read(multi_track_midi)

        def note_ons(s) -> int:
            return sum(
                1
                for t in s.tracks
                for e in t.events
                if e.message_type == 0x90 and e.data and e.data[1] > 0
            )

        before = note_ons(song)
        after = note_ons(reader.parse(SmfWriter().serialize(song)))
        assert before == after


class TestFormats:
    @pytest.mark.parametrize("fmt", [0, 1])
    def test_supported_formats(self, fmt: int) -> None:
        data = build_midi(fmt=fmt)
        song = SmfReader().parse(data)
        assert song.header.format_type == fmt
        assert PreserveWriter.serialize(song) == data

    def test_smpte_division_reports_no_ppq(self) -> None:
        """SMPTE vremenska baza ne smije se predstaviti kao PPQ."""
        division = struct.pack(">bb", -25, 40)  # 25 fps, 40 ticks/frame
        header = b"MThd" + struct.pack(">I", 6) + struct.pack(">HH", 0, 1) + division
        chunk = b"\x00\xff\x2f\x00"
        data = header + b"MTrk" + struct.pack(">I", len(chunk)) + chunk

        song = SmfReader().parse(data)
        assert song.header.uses_smpte is True
        assert song.header.ppq is None
        # fps_code je sirovi potpisani bajt iz SMF-a (-25), a
        # smpte_frames_per_second ga prevodi u stvarnu brzinu.
        assert song.header.smpte_fps_code == -25
        assert song.header.smpte_frames_per_second == 25
        assert song.header.smpte_ticks_per_frame == 40
