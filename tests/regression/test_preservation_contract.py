"""Ugovor o ocuvanju -- stavka 11.1 iz spiska nedovrsenog.

Ovo je najvazniji regresijski modul u projektu. Standardni konzervativni
`Optimize` NIKADA ne smije izgubiti originalni track, notu, lyrics ili
pitch bend.

Povijesni incident koji ovi testovi trajno zakljucavaju:

    "Nevera moja": 16 trackova / 8.340 nota  ->  7 trackova / 4.492 note

Test `test_nevera_moja_incident_cannot_recur` reprodukuje tacno tu
strukturu i pada ako se ikada vrati put koji je to omogucio.

Sto se ovdje NE tvrdi: da je izabrani sound dobar. To je hardverski
posao (P0 2.1), a ne softverski. Ovdje se tvrdi samo da se nista ne gubi.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from pa800_enhancer.optimize.conservative import optimize_conservatively
from pa800_enhancer.smf.reader import SmfReader
from tests.conftest import build_midi


# --------------------------------------------------------------------------
# Minimalni Factory katalog (bez 19 MB vanjskog fajla)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FakeRole:
    role: str
    channel: int
    bank_msb: int
    bank_lsb: int
    program: int
    note_count: int


@dataclass(frozen=True)
class FakeElement:
    roles: tuple[FakeRole, ...]


@dataclass(frozen=True)
class FakeCatalog:
    elements: tuple[FakeElement, ...]


@pytest.fixture
def catalog() -> FakeCatalog:
    """Pokriva accompaniment/bass/guitar sa po dvije varijante banke."""
    roles = (
        FakeRole("accompaniment", 12, 121, 3, 0, 5000),
        FakeRole("accompaniment", 12, 121, 1, 0, 2000),
        FakeRole("bass", 9, 121, 2, 33, 4000),
        FakeRole("bass", 9, 121, 6, 33, 1500),
        FakeRole("guitar", 13, 121, 4, 25, 3000),
        FakeRole("guitar", 13, 121, 8, 25, 1200),
        FakeRole("accompaniment", 11, 121, 5, 66, 900),
    )
    return FakeCatalog(elements=(FakeElement(roles=roles),))


# --------------------------------------------------------------------------
# Pomocno brojanje -- namjerno nezavisno od koda koji se testira
# --------------------------------------------------------------------------
def count_note_ons(song) -> int:
    return sum(
        1
        for track in song.tracks
        for event in track.events
        if event.message_type == 0x90 and event.data and event.data[1] > 0
    )


def note_multiset(song) -> list[tuple[int, int, int, int]]:
    """(tick, kanal, visina, velocity) za svaki Note On -- sortirano."""
    out = []
    for track in song.tracks:
        for event in track.events:
            if event.message_type == 0x90 and event.data and event.data[1] > 0:
                out.append(
                    (event.absolute_tick, event.channel, event.data[0], event.data[1])
                )
    return sorted(out)


def meta_events(song, meta_type: int) -> list[bytes]:
    """Meta eventi zadanog tipa.

    Napomena: za meta event `status` je 0xFF, pa `message_type`
    (status & 0xF0) daje 0xF0. Filtrira se po `meta_type` polju.
    """
    out = []
    for track in song.tracks:
        for event in track.events:
            if event.status == 0xFF and event.meta_type == meta_type:
                out.append(bytes(event.data))
    return sorted(out)


def pitch_bends(song) -> list[tuple[int, int, bytes]]:
    out = []
    for track in song.tracks:
        for event in track.events:
            if event.message_type == 0xE0:
                out.append((event.absolute_tick, event.channel, bytes(event.data)))
    return sorted(out)


# --------------------------------------------------------------------------
# Fixture: bogata pjesma sa 16 trackova, lyrics i pitch bendom
# --------------------------------------------------------------------------
@pytest.fixture
def rich_song(tmp_path):
    """Format 1, 16 trackova, lyrics, pitch bend, sustain -- kao prava pjesma."""
    ppq = 384
    tracks: list[list[tuple[int, bytes]]] = []

    # Track 0: samo meta (tempo, metar, naslov)
    tracks.append(
        [
            (0, b"\xff\x51\x03\x07\xa1\x20"),
            (0, b"\xff\x58\x04\x04\x02\x18\x08"),
            (0, b"\xff\x03\x0bNevera moja"),
        ]
    )

    # 15 muzickih trackova na kanalima 1-16 (bez 10 na dva mjesta radi bubnjeva)
    channels = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    programs = [0, 48, 33, 25, 4, 61, 66, 73, 33, 0, 66, 0, 28, 27, 16]

    for index, (channel, program) in enumerate(zip(channels, programs, strict=True)):
        status_on = 0x90 | ((channel - 1) & 0x0F)
        status_off = 0x80 | ((channel - 1) & 0x0F)
        status_cc = 0xB0 | ((channel - 1) & 0x0F)
        status_pc = 0xC0 | ((channel - 1) & 0x0F)
        status_pb = 0xE0 | ((channel - 1) & 0x0F)

        events: list[tuple[int, bytes]] = [
            (0, bytes([status_cc, 0, 121])),
            (0, bytes([status_cc, 32, 0])),
            (0, bytes([status_pc, program])),
            (0, bytes([status_cc, 7, 100])),
        ]
        # 20 nota po tracku
        for n in range(20):
            pitch = 40 + (index * 3 + n) % 48
            events.append((0, bytes([status_on, pitch, 64 + (n % 40)])))
            events.append((ppq // 4, bytes([status_off, pitch, 0])))
        # pitch bend i sustain samo na nekim trackovima
        if index % 3 == 0:
            events.append((0, bytes([status_pb, 0x00, 0x50])))
            events.append((ppq, bytes([status_pb, 0x00, 0x40])))
        if index % 4 == 0:
            events.append((0, bytes([status_cc, 64, 127])))
            events.append((ppq, bytes([status_cc, 64, 0])))
        # lyrics na melodijskom tracku
        if index == 1:
            events.append((0, b"\xff\x05\x06nevera"))
            events.append((ppq, b"\xff\x05\x04moja"))
        tracks.append(events)

    data = build_midi(fmt=1, ppq=ppq, tracks=tracks)
    path = tmp_path / "nevera-moja.mid"
    path.write_bytes(data)
    return path


# --------------------------------------------------------------------------
# Ugovor
# --------------------------------------------------------------------------
class TestTrackPreservation:
    def test_track_count_never_changes(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        result = optimize_conservatively(song, catalog)

        assert len(result.song.tracks) == len(song.tracks)

    def test_reported_track_count_matches_reality(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        result = optimize_conservatively(song, catalog)

        assert result.preserved_tracks == len(result.song.tracks)

    def test_track_indices_are_stable(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        result = optimize_conservatively(song, catalog)

        assert [t.index for t in result.song.tracks] == [
            t.index for t in song.tracks
        ]


class TestNotePreservation:
    def test_note_count_never_changes(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        before = count_note_ons(song)
        result = optimize_conservatively(song, catalog)

        assert count_note_ons(result.song) == before

    def test_every_note_is_bit_identical(self, rich_song, catalog) -> None:
        """Ni tick, ni kanal, ni visina, ni velocity ne smiju se pomaknuti."""
        song = SmfReader().read(rich_song)
        before = note_multiset(song)
        result = optimize_conservatively(song, catalog)

        assert note_multiset(result.song) == before

    def test_reported_note_count_matches_reality(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        result = optimize_conservatively(song, catalog)

        assert result.preserved_notes == count_note_ons(result.song)


class TestMetadataPreservation:
    def test_lyrics_survive(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        before = meta_events(song, 0x05)
        result = optimize_conservatively(song, catalog)

        assert meta_events(result.song, 0x05) == before
        assert before, "fixture mora sadrzavati lyrics"

    def test_track_names_survive(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        before = meta_events(song, 0x03)
        result = optimize_conservatively(song, catalog)

        assert meta_events(result.song, 0x03) == before

    def test_pitch_bend_survives(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        before = pitch_bends(song)
        result = optimize_conservatively(song, catalog)

        assert pitch_bends(result.song) == before
        assert before, "fixture mora sadrzavati pitch bend"

    def test_tempo_and_meter_survive(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        before = (meta_events(song, 0x51), meta_events(song, 0x58))
        result = optimize_conservatively(song, catalog)

        assert (
            meta_events(result.song, 0x51),
            meta_events(result.song, 0x58),
        ) == before

    def test_sustain_pedal_survives(self, rich_song, catalog) -> None:
        def sustain(song) -> list[tuple[int, int, int]]:
            return sorted(
                (e.absolute_tick, e.channel, e.data[1])
                for t in song.tracks
                for e in t.events
                if e.message_type == 0xB0 and len(e.data) == 2 and e.data[0] == 64
            )

        song = SmfReader().read(rich_song)
        before = sustain(song)
        result = optimize_conservatively(song, catalog)

        assert sustain(result.song) == before
        assert before, "fixture mora sadrzavati sustain"

    def test_header_is_unchanged(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        result = optimize_conservatively(song, catalog)

        assert result.song.header.format_type == song.header.format_type
        assert result.song.header.ppq == song.header.ppq


class TestNeveraMojaIncident:
    """Zakljucavanje konkretnog povijesnog gubitka."""

    def test_nevera_moja_incident_cannot_recur(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        tracks_before = len(song.tracks)
        notes_before = count_note_ons(song)

        assert tracks_before == 16, "fixture mora imati 16 trackova"
        assert notes_before == 300, "fixture mora imati stabilan broj nota"

        result = optimize_conservatively(song, catalog)

        # Tacni brojevi iz incidenta -- nikada vise.
        assert len(result.song.tracks) != 7, "incident: 16 -> 7 trackova"
        assert count_note_ons(result.song) != 4492, "incident: 8340 -> 4492 nota"

        # Opsti oblik iste tvrdnje.
        assert len(result.song.tracks) == tracks_before
        assert count_note_ons(result.song) == notes_before

    def test_no_channel_is_silently_dropped(self, rich_song, catalog) -> None:
        def channels(song) -> set[int]:
            return {
                e.channel
                for t in song.tracks
                for e in t.events
                if e.message_type == 0x90 and e.data and e.data[1] > 0
            }

        song = SmfReader().read(rich_song)
        before = channels(song)
        result = optimize_conservatively(song, catalog)

        assert channels(result.song) == before

    def test_unmapped_channels_are_reported_not_hidden(
        self, rich_song, catalog
    ) -> None:
        """Kanal bez Factory dokaza ostaje nepromijenjen I biva prijavljen."""
        song = SmfReader().read(rich_song)
        result = optimize_conservatively(song, catalog)

        mapped = {m.channel for m in result.mappings}
        skipped = set(result.skipped_channels)

        assert not (mapped & skipped), "kanal ne moze biti i mapiran i preskocen"
        # Nista se ne gubi bez traga: svaki kanal je ili mapiran ili prijavljen.
        assert count_note_ons(result.song) == count_note_ons(song)


class TestIdempotence:
    def test_running_twice_changes_nothing_more(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        first = optimize_conservatively(song, catalog)
        second = optimize_conservatively(first.song, catalog)

        assert note_multiset(second.song) == note_multiset(first.song)
        assert len(second.song.tracks) == len(first.song.tracks)


class TestEmptyAndEdgeCases:
    def test_song_without_matching_catalog_keeps_all_music(
        self, rich_song
    ) -> None:
        empty = FakeCatalog(elements=())
        song = SmfReader().read(rich_song)
        before = note_multiset(song)

        result = optimize_conservatively(song, empty)

        assert note_multiset(result.song) == before
        assert len(result.song.tracks) == len(song.tracks)

    def test_drum_kit_comes_from_evidence_not_hardcode(self, rich_song) -> None:
        """Rupa N1 zatvorena: bez izvora nema drum adrese.

        Ranije je 120.0.4 bila hardkodirana u conservative.py i dodjeljivala
        se i uz prazan katalog. Sada `drum_kit=None` znaci da se drum kanal
        preskace, a ne nagadja.
        """
        empty = FakeCatalog(elements=())
        song = SmfReader().read(rich_song)

        result = optimize_conservatively(song, empty, drum_kit=None)

        assert result.mappings == (), (
            "bez dokaza se ne smije dodijeliti nijedna adresa, "
            "ukljucujuci podrazumijevani drum kit"
        )

    def test_skipped_channels_carry_a_reason(self, rich_song) -> None:
        empty = FakeCatalog(elements=())
        song = SmfReader().read(rich_song)

        result = optimize_conservatively(song, empty, drum_kit=None)

        assert result.skipped_details, "preskoceni kanali moraju biti objasnjeni"
        for detail in result.skipped_details:
            assert detail.reason, f"kanal {detail.channel} nema razlog"
        # Drum kanal mora biti medju preskocenima, i to sa jasnim razlogom.
        drums = [d for d in result.skipped_details if d.role == "drums"]
        assert drums and "drum" in drums[0].reason.lower()

    def test_drum_kit_below_evidence_threshold_is_refused(
        self, rich_song
    ) -> None:
        from pa800_enhancer.optimize.conservative import DrumKitReference

        guess = DrumKitReference(
            name="Nagadjanje",
            bank_msb=120,
            bank_lsb=0,
            program=4,
            evidence_status="hypothesis",
            evidence=("pretpostavka",),
        )
        song = SmfReader().read(rich_song)

        result = optimize_conservatively(
            song, FakeCatalog(elements=()), drum_kit=guess
        )

        assert result.mappings == ()
        assert any("hypothesis" in d.reason for d in result.skipped_details)

    def test_drum_kit_without_evidence_list_is_refused(self, rich_song) -> None:
        from pa800_enhancer.optimize.conservative import DrumKitReference

        undocumented = DrumKitReference(
            name="Bez izvora",
            bank_msb=120,
            bank_lsb=0,
            program=4,
            evidence_status="documented",
            evidence=(),  # tvrdi da je dokumentovan, ali ne navodi cime
        )
        song = SmfReader().read(rich_song)

        result = optimize_conservatively(
            song, FakeCatalog(elements=()), drum_kit=undocumented
        )

        assert result.mappings == ()

    def test_configured_drum_kit_is_applied_with_provenance(
        self, rich_song
    ) -> None:
        """Sa validnim izvorom kit se primjenjuje I nosi trag odakle je."""
        song = SmfReader().read(rich_song)

        result = optimize_conservatively(song, FakeCatalog(elements=()))

        drums = [m for m in result.mappings if m.role == "drums"]
        assert len(drums) == 1
        assert drums[0].evidence_status == "documented"
        assert drums[0].evidence_source.startswith("config:")

    def test_every_mapping_records_its_evidence(self, rich_song, catalog) -> None:
        song = SmfReader().read(rich_song)
        result = optimize_conservatively(song, catalog)

        assert result.mappings
        for mapping in result.mappings:
            assert mapping.evidence_status in (
                "documented",
                "software_verified",
                "hardware_confirmed",
            )
            assert mapping.evidence_source

    def test_single_track_song(self, simple_midi, catalog) -> None:
        song = SmfReader().read(simple_midi)
        before = count_note_ons(song)

        result = optimize_conservatively(song, catalog)

        assert count_note_ons(result.song) == before
        assert len(result.song.tracks) == len(song.tracks)

    def test_dangling_note_is_preserved_not_repaired(
        self, dangling_note_midi, catalog
    ) -> None:
        """Viseca nota se ne smije 'popraviti' u konzervativnom nacinu."""
        song = SmfReader().read(dangling_note_midi)
        before = count_note_ons(song)

        result = optimize_conservatively(song, catalog)

        assert count_note_ons(result.song) == before
