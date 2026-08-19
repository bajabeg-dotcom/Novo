"""B3 -- garancije exporta.

Export je zadnja tacka prije korisnikovog diska. Ovdje se provjerava
obecanje iz README-a: `preserve` pise IDENTICNE bajtove, svaki export se
ponovo parsira i validira, i svaki dobija .report.json.
"""

from __future__ import annotations

import json

import pytest

from pa800_enhancer.export.service import ExportService
from pa800_enhancer.smf.reader import SmfReader


@pytest.fixture
def service() -> ExportService:
    return ExportService()


class TestPreserveMode:
    def test_writes_identical_bytes(self, service, simple_midi, tmp_path) -> None:
        original = simple_midi.read_bytes()
        song = SmfReader().read(simple_midi)
        out = tmp_path / "out.mid"

        service.export(song, out, profile_id="test", mode="preserve")

        assert out.read_bytes() == original

    def test_identical_for_multi_track(
        self, service, multi_track_midi, tmp_path
    ) -> None:
        original = multi_track_midi.read_bytes()
        song = SmfReader().read(multi_track_midi)
        out = tmp_path / "out.mid"

        service.export(song, out, profile_id="test", mode="preserve")

        assert out.read_bytes() == original

    def test_identical_for_running_status(
        self, service, running_status_midi, tmp_path
    ) -> None:
        original = running_status_midi.read_bytes()
        song = SmfReader().read(running_status_midi)
        out = tmp_path / "out.mid"

        service.export(song, out, profile_id="test", mode="preserve")

        assert out.read_bytes() == original


class TestReport:
    def test_report_written_next_to_output(
        self, service, simple_midi, tmp_path
    ) -> None:
        song = SmfReader().read(simple_midi)
        out = tmp_path / "song.mid"

        service.export(song, out, profile_id="test", mode="preserve")

        report = tmp_path / "song.mid.report.json"
        assert report.exists()

    def test_report_contains_hashes(self, service, simple_midi, tmp_path) -> None:
        song = SmfReader().read(simple_midi)
        out = tmp_path / "song.mid"

        service.export(song, out, profile_id="test", mode="preserve")

        data = json.loads((tmp_path / "song.mid.report.json").read_text())
        text = json.dumps(data)
        assert "sha256" in text.lower()

    def test_report_can_be_suppressed(self, service, simple_midi, tmp_path) -> None:
        song = SmfReader().read(simple_midi)
        out = tmp_path / "song.mid"

        service.export(
            song, out, profile_id="test", mode="preserve", write_report=False
        )

        assert not (tmp_path / "song.mid.report.json").exists()


class TestModes:
    @pytest.mark.parametrize(
        "mode", ["auto", "preserve", "segment-preserve", "canonical"]
    )
    def test_supported_modes_produce_valid_midi(
        self, service, multi_track_midi, tmp_path, mode
    ) -> None:
        song = SmfReader().read(multi_track_midi)
        out = tmp_path / f"{mode}.mid"

        service.export(song, out, profile_id="test", mode=mode)

        reparsed = SmfReader().read(out)
        assert reparsed.header.ppq == song.header.ppq
        assert len(reparsed.tracks) == len(song.tracks)

    def test_rejects_unknown_mode(self, service, simple_midi, tmp_path) -> None:
        song = SmfReader().read(simple_midi)
        with pytest.raises(ValueError):
            service.export(
                song, tmp_path / "x.mid", profile_id="test", mode="nonsense"
            )

    @pytest.mark.parametrize("mode", ["preserve", "segment-preserve", "canonical"])
    def test_note_count_never_changes(
        self, service, multi_track_midi, tmp_path, mode
    ) -> None:
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
        out = tmp_path / f"{mode}.mid"
        service.export(song, out, profile_id="test", mode=mode)

        assert note_ons(reader.read(out)) == before


class TestDanglingNotes:
    """Fajl sa visecom notom mora prezivjeti export bez izmjene.

    Vezano za nalaz iz FORENZIKA.md: 405 Factory fajlova ima Note On bez
    Note Off. Export ih ne smije "popraviti" na svoju ruku.
    """

    def test_preserve_keeps_dangling_note(
        self, service, dangling_note_midi, tmp_path
    ) -> None:
        original = dangling_note_midi.read_bytes()
        song = SmfReader().read(dangling_note_midi)
        out = tmp_path / "out.mid"

        service.export(song, out, profile_id="test", mode="preserve")

        assert out.read_bytes() == original

    def test_canonical_does_not_invent_note_off(
        self, service, dangling_note_midi, tmp_path
    ) -> None:
        reader = SmfReader()
        song = reader.read(dangling_note_midi)
        out = tmp_path / "out.mid"

        service.export(song, out, profile_id="test", mode="canonical")

        def count(s, message_type: int, zero_velocity: bool) -> int:
            total = 0
            for t in s.tracks:
                for e in t.events:
                    if e.message_type != message_type or not e.data:
                        continue
                    if message_type == 0x90 and (e.data[1] == 0) != zero_velocity:
                        continue
                    total += 1
            return total

        before_off = count(song, 0x80, False) + count(song, 0x90, True)
        after = reader.read(out)
        after_off = count(after, 0x80, False) + count(after, 0x90, True)

        assert after_off == before_off, "export ne smije izmisliti Note Off"
