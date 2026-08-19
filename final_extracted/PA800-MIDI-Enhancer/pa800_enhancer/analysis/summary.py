from collections import Counter
from dataclasses import dataclass

from ..domain.events import EventKind
from ..domain.song import Song
from .notes import maximum_polyphony, pair_notes
from .tempo_map import TempoMap
from .parameters import analyze_parameters


@dataclass(frozen=True, slots=True)
class SongSummary:
    format_type: int
    track_count: int
    event_count: int
    end_tick: int
    ppq: int | None
    channels: tuple[int, ...]
    note_count: int
    unmatched_notes: int
    sustained_notes: int
    maximum_polyphony: int
    duration_seconds: float
    tempo_events: int
    meter_events: int
    sysex_events: int
    unknown_chunks: int
    trailing_bytes: int
    event_types: dict[str, int]
    controller_events: int
    parameter_changes: int
    parameter_issues: int


def summarize(song: Song) -> SongSummary:
    notes, unmatched = pair_notes(song)
    channels: set[int] = set()
    types: Counter[str] = Counter()
    tempo_events = meter_events = sysex_events = 0
    for track in song.tracks:
        for event in track.events:
            if event.channel is not None:
                channels.add(event.channel)
            if event.kind is EventKind.CHANNEL:
                types[f"0x{event.message_type:02X}"] += 1
            else:
                types[event.kind.value] += 1
            tempo_events += event.meta_type == 0x51
            meter_events += event.meta_type == 0x58
            sysex_events += event.kind is EventKind.SYSEX
    raw = song.raw_document
    duration_seconds = float(TempoMap(song).tick_to_seconds(song.end_tick))
    parameters = analyze_parameters(song)
    return SongSummary(
        song.header.format_type,
        len(song.tracks),
        song.event_count,
        song.end_tick,
        song.header.ppq,
        tuple(sorted(channels)),
        len(notes),
        len(unmatched),
        sum(note.sustained for note in notes),
        maximum_polyphony(notes),
        duration_seconds,
        tempo_events,
        meter_events,
        sysex_events,
        len(raw.unknown_chunks) if raw else 0,
        raw.trailing_span.length if raw and raw.trailing_span else 0,
        dict(sorted(types.items())),
        types.get("0xB0", 0),
        len(parameters.changes),
        len(parameters.issues),
    )