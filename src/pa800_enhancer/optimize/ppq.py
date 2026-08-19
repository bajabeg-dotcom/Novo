from dataclasses import dataclass, replace
from fractions import Fraction

from ..analysis.notes import pair_notes
from ..domain.song import Song, Track


def _round_half_up(value: Fraction) -> int:
    quotient, remainder = divmod(value.numerator, value.denominator)
    return quotient + (1 if remainder * 2 >= value.denominator else 0)


@dataclass(frozen=True, slots=True)
class PpqResampleResult:
    song: Song
    source_ppq: int
    target_ppq: int
    moved_event_count: int


def resample_ppq(song: Song, target_ppq: int) -> PpqResampleResult:
    source_ppq = song.header.ppq
    if not source_ppq:
        raise ValueError("PPQ resampling is unavailable for SMPTE time division")
    if not 1 <= target_ppq <= 0x7FFF:
        raise ValueError("target PPQ must be in the range 1..32767")
    scale = Fraction(target_ppq, source_ppq)
    scaled: dict[str, int] = {
        event.event_id: _round_half_up(Fraction(event.absolute_tick) * scale)
        for track in song.tracks
        for event in track.events
    }
    notes, _ = pair_notes(song)
    for note in notes:
        on_tick = scaled[note.on_event_id]
        if scaled[note.off_event_id] <= on_tick:
            scaled[note.off_event_id] = on_tick + 1

    tracks: list[Track] = []
    moved = 0
    for track in song.tracks:
        previous = 0
        events = []
        for event in sorted(track.events, key=lambda item: item.order):
            tick = max(previous, scaled[event.event_id])
            moved += tick != event.absolute_tick
            events.append(replace(event, absolute_tick=tick))
            previous = tick
        tracks.append(Track(track.index, events))
    header = replace(song.header, division=target_ppq)
    transformed = Song(header, tracks, song.source_path, song.source_sha256, song.raw_document)
    return PpqResampleResult(transformed, source_ppq, target_ppq, moved)