"""Read-only tempo, meter, measure, repetition and phrase analysis.

M08 consumes the immutable models produced by :mod:`style_loader`.  It never
rewrites events or MIDI bytes.  Exact measure repetition is reported as a
derived fact; phrase boundaries are conservative candidates based on long
inter-onset gaps and are therefore explicitly marked as inferred.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from style_loader import MidiEvent, MidiFileModel, StyleElementModel, StyleTrackSlice


class AnalysisStatus(str, Enum):
    READY = "READY"
    UNCERTAIN = "UNCERTAIN"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class TempoPoint:
    tick: int
    microseconds_per_quarter: int
    bpm: float


@dataclass(frozen=True, slots=True)
class MeterPoint:
    tick: int
    numerator: int
    denominator: int
    ticks_per_measure: int


@dataclass(frozen=True, slots=True)
class MeasureSpan:
    number: int
    start_tick: int
    end_tick: int
    numerator: int
    denominator: int
    complete: bool


@dataclass(frozen=True, slots=True)
class EventPosition:
    track_index: int
    event_index: int
    absolute_tick: int
    kind: str
    measure: int
    beat: int
    tick_in_beat: int


@dataclass(frozen=True, slots=True)
class MeasureContent:
    measure: int
    onset_count: int
    note_count: int
    signature: tuple[tuple[int, int, int, int, int, int, int], ...]


@dataclass(frozen=True, slots=True)
class RepeatedMeasureGroup:
    measures: tuple[int, ...]
    signature: tuple[tuple[int, int, int, int, int, int, int], ...]


@dataclass(frozen=True, slots=True)
class PhraseBoundaryCandidate:
    tick: int
    measure: int
    reason: str
    confidence: int


@dataclass(frozen=True, slots=True)
class MeasurePhraseAnalysis:
    source_sha256: str
    status: AnalysisStatus
    ticks_per_beat: int | None
    window_start_tick: int
    window_end_tick: int
    tempo_points: tuple[TempoPoint, ...]
    meter_points: tuple[MeterPoint, ...]
    measures: tuple[MeasureSpan, ...]
    event_positions: tuple[EventPosition, ...]
    measure_contents: tuple[MeasureContent, ...]
    repeated_measure_groups: tuple[RepeatedMeasureGroup, ...]
    phrase_boundaries: tuple[PhraseBoundaryCandidate, ...]
    warnings: tuple[str, ...]
    protections: tuple[str, ...]


class MeasurePhraseAnalyzer:
    """Derive timeline and phrase evidence without authorizing an edit."""

    def analyze(
        self,
        midi: MidiFileModel,
        *,
        musical_events: Iterable[MidiEvent] | None = None,
        window_start_tick: int = 0,
        window_end_tick: int | None = None,
        source_blocked_reason: str | None = None,
    ) -> MeasurePhraseAnalysis:
        all_events = tuple(event for track in midi.tracks for event in track.events)
        selected = tuple(musical_events) if musical_events is not None else all_events
        selected = tuple(
            event for event in selected
            if event.absolute_tick >= window_start_tick
            and (window_end_tick is None or event.absolute_tick < window_end_tick)
        )
        inferred_end = max(
            (event.absolute_tick + 1 for event in selected),
            default=max((track.end_tick for track in midi.tracks), default=window_start_tick + 1),
        )
        end_tick = window_end_tick if window_end_tick is not None else inferred_end
        warnings: list[str] = []
        protections = [
            "M08 je Analyze-only: rezultat ne dopušta pomicanje, kvantizaciju ni brisanje događaja."
        ]

        if source_blocked_reason:
            return self._blocked(midi, window_start_tick, end_tick, source_blocked_reason)
        if midi.ticks_per_beat is None:
            return self._blocked(
                midi, window_start_tick, end_tick,
                "SMPTE division nema PPQ osnovu potrebnu za položaj u taktu.",
            )
        if end_tick <= window_start_tick:
            return self._blocked(
                midi, window_start_tick, end_tick,
                "Vremenski prozor mora završiti nakon početnog ticka.",
            )

        tempo_points, tempo_conflict, tempo_warnings = self._tempo_points(
            all_events, window_start_tick, end_tick
        )
        meter_points, meter_conflict, meter_warnings = self._meter_points(
            all_events, midi.ticks_per_beat, window_start_tick, end_tick
        )
        warnings.extend(tempo_warnings)
        warnings.extend(meter_warnings)
        if not tempo_points:
            warnings.append(
                "Nema eksplicitne Set Tempo poruke; položaj u taktu je dostupan, ali vrijeme u sekundama nije izvedeno."
            )
        if tempo_conflict or meter_conflict:
            protections.append("Konfliktni timeline podaci blokiraju vremensko tumačenje.")
            return MeasurePhraseAnalysis(
                midi.sha256, AnalysisStatus.BLOCKED, midi.ticks_per_beat,
                window_start_tick, end_tick, tempo_points, meter_points,
                (), (), (), (), (), tuple(warnings), tuple(protections),
            )
        if not meter_points:
            warnings.append("Nema potvrđene Time Signature poruke; mjere i fraze nisu izvedene.")
            return MeasurePhraseAnalysis(
                midi.sha256, AnalysisStatus.UNCERTAIN, midi.ticks_per_beat,
                window_start_tick, end_tick, tempo_points, (), (), (), (), (), (),
                tuple(warnings), tuple(protections),
            )

        measures, span_warnings = self._measure_spans(
            meter_points, window_start_tick, end_tick
        )
        warnings.extend(span_warnings)
        positions = self._event_positions(selected, measures, midi.ticks_per_beat)
        contents = self._measure_contents(selected, measures)
        repetitions = self._repetitions(contents)
        phrases = self._phrase_boundaries(selected, measures, midi.ticks_per_beat)
        status = AnalysisStatus.UNCERTAIN if warnings else AnalysisStatus.READY
        return MeasurePhraseAnalysis(
            midi.sha256, status, midi.ticks_per_beat, window_start_tick, end_tick,
            tempo_points, meter_points, measures, positions, contents, repetitions,
            phrases, tuple(warnings), tuple(protections),
        )

    @staticmethod
    def _blocked(
        midi: MidiFileModel, start: int, end: int, reason: str
    ) -> MeasurePhraseAnalysis:
        return MeasurePhraseAnalysis(
            midi.sha256, AnalysisStatus.BLOCKED, midi.ticks_per_beat, start, end,
            (), (), (), (), (), (), (), (reason,),
            ("Izvorni događaji ostaju netaknuti; vremenska analiza je blokirana.",),
        )

    @staticmethod
    def _tempo_points(
        events: Iterable[MidiEvent], start: int, end: int,
    ) -> tuple[tuple[TempoPoint, ...], bool, tuple[str, ...]]:
        values: dict[int, set[int]] = defaultdict(set)
        warnings: list[str] = []
        for event in events:
            if event.kind != "meta" or event.meta_type != 0x51:
                continue
            if event.absolute_tick >= end:
                continue
            if len(event.payload) != 3:
                warnings.append(f"Nevaljana Set Tempo poruka na ticku {event.absolute_tick}.")
                continue
            value = int.from_bytes(event.payload, "big")
            if value <= 0:
                warnings.append(f"Nedopušten tempo na ticku {event.absolute_tick}.")
                continue
            values[event.absolute_tick].add(value)
        active_tick = max((tick for tick in values if tick <= start), default=None)
        relevant_conflict_ticks = {
            tick for tick in values
            if tick >= start or tick == active_tick
        }
        conflict = any(len(values[tick]) > 1 for tick in relevant_conflict_ticks)
        for tick, items in values.items():
            if tick in relevant_conflict_ticks and len(items) > 1:
                warnings.append(f"Konflikt Set Tempo vrijednosti na ticku {tick}: {sorted(items)}.")
        points = tuple(
            TempoPoint(tick, next(iter(items)), 60_000_000 / next(iter(items)))
            for tick, items in sorted(values.items()) if len(items) == 1
        )
        return points, conflict, tuple(warnings)

    @staticmethod
    def _meter_points(
        events: Iterable[MidiEvent], ppq: int, start: int, end: int
    ) -> tuple[tuple[MeterPoint, ...], bool, tuple[str, ...]]:
        values: dict[int, set[tuple[int, int]]] = defaultdict(set)
        warnings: list[str] = []
        for event in events:
            if event.kind != "meta" or event.meta_type != 0x58:
                continue
            if event.absolute_tick >= end:
                continue
            if len(event.payload) < 2 or event.payload[0] == 0 or event.payload[1] > 7:
                warnings.append(f"Nevaljana Time Signature poruka na ticku {event.absolute_tick}.")
                continue
            values[event.absolute_tick].add((event.payload[0], 2 ** event.payload[1]))
        active_tick = max((tick for tick in values if tick <= start), default=None)
        relevant_conflict_ticks = {
            tick for tick in values
            if tick >= start or tick == active_tick
        }
        conflict = any(len(values[tick]) > 1 for tick in relevant_conflict_ticks)
        for tick, items in values.items():
            if tick in relevant_conflict_ticks and len(items) > 1:
                warnings.append(f"Konflikt Time Signature vrijednosti na ticku {tick}: {sorted(items)}.")
        points: list[MeterPoint] = []
        for tick, items in sorted(values.items()):
            if len(items) != 1:
                continue
            numerator, denominator = next(iter(items))
            raw_length = numerator * ppq * 4
            if raw_length % denominator:
                warnings.append(
                    f"Metar {numerator}/{denominator} na ticku {tick} nema cjelobrojnu PPQ mjeru."
                )
                continue
            points.append(MeterPoint(tick, numerator, denominator, raw_length // denominator))
        return tuple(points), conflict, tuple(warnings)

    @staticmethod
    def _measure_spans(
        points: tuple[MeterPoint, ...], start: int, end: int
    ) -> tuple[tuple[MeasureSpan, ...], tuple[str, ...]]:
        warnings: list[str] = []
        if not any(point.tick <= start for point in points):
            return (), ("Prva potvrđena oznaka takta nalazi se nakon početka analitičkog prozora.",)
        spans: list[MeasureSpan] = []
        number = 1
        for index, point in enumerate(points):
            if point.tick >= end:
                break
            cursor = point.tick
            point = points[index]
            next_change = points[index + 1].tick if index + 1 < len(points) else end
            segment_end = min(next_change, end)
            while cursor < segment_end:
                natural_end = cursor + point.ticks_per_measure
                span_end = min(natural_end, segment_end)
                complete = span_end == natural_end
                if span_end > start:
                    spans.append(MeasureSpan(
                        number, cursor, span_end, point.numerator, point.denominator, complete
                    ))
                if not complete and span_end > start:
                    warnings.append(
                        f"Promjena metra ili kraj prozora prekida mjeru {number} na ticku {span_end}."
                    )
                cursor = span_end
                number += 1
        return tuple(spans), tuple(warnings)

    @staticmethod
    def _event_positions(
        events: Iterable[MidiEvent], measures: tuple[MeasureSpan, ...], ppq: int
    ) -> tuple[EventPosition, ...]:
        result: list[EventPosition] = []
        for event in sorted(events, key=lambda item: (item.absolute_tick, item.track_index, item.event_index)):
            span = next(
                (item for item in measures if item.start_tick <= event.absolute_tick < item.end_tick),
                None,
            )
            if span is None:
                continue
            ticks_per_beat = ppq * 4 // span.denominator
            offset = event.absolute_tick - span.start_tick
            result.append(EventPosition(
                event.track_index, event.event_index, event.absolute_tick, event.kind,
                span.number, offset // ticks_per_beat + 1, offset % ticks_per_beat,
            ))
        return tuple(result)

    @staticmethod
    def _measure_contents(
        events: Iterable[MidiEvent], measures: tuple[MeasureSpan, ...]
    ) -> tuple[MeasureContent, ...]:
        active: dict[tuple[int, int], deque[MidiEvent]] = defaultdict(deque)
        completed: list[tuple[MidiEvent, int | None, int, int]] = []
        ordered = sorted(
            events,
            key=lambda item: (item.absolute_tick, item.track_index, item.event_index),
        )
        for event in ordered:
            if event.channel is None or len(event.data) != 2:
                continue
            key = (event.channel, event.data[0])
            if event.is_note_on:
                active[key].append(event)
            elif event.kind == "note_off" or (event.kind == "note_on" and event.data[1] == 0):
                if not active[key]:
                    continue
                note_on = active[key].popleft()
                off_semantics = 0 if event.kind == "note_off" else 1
                completed.append((note_on, event.absolute_tick, event.data[1], off_semantics))
        for pending in active.values():
            for note_on in pending:
                completed.append((note_on, None, -1, -1))

        result: list[MeasureContent] = []
        for span in measures:
            notes = tuple(
                note for note in completed
                if span.start_tick <= note[0].absolute_tick < span.end_tick
            )
            signature = tuple(sorted(
                (
                    note_on.absolute_tick - span.start_tick,
                    note_on.channel if note_on.channel is not None else -1,
                    note_on.data[0],
                    note_on.data[1],
                    end_tick - note_on.absolute_tick if end_tick is not None else -1,
                    release_velocity,
                    off_semantics,
                )
                for note_on, end_tick, release_velocity, off_semantics in notes
            ))
            result.append(MeasureContent(
                span.number, len({note[0].absolute_tick for note in notes}), len(notes), signature
            ))
        return tuple(result)

    @staticmethod
    def _repetitions(
        contents: tuple[MeasureContent, ...]
    ) -> tuple[RepeatedMeasureGroup, ...]:
        groups: dict[
            tuple[tuple[int, int, int, int, int, int, int], ...], list[int]
        ] = defaultdict(list)
        for content in contents:
            if content.signature:
                groups[content.signature].append(content.measure)
        return tuple(
            RepeatedMeasureGroup(tuple(measures), signature)
            for signature, measures in sorted(groups.items(), key=lambda item: item[1][0])
            if len(measures) >= 2
        )

    @staticmethod
    def _phrase_boundaries(
        events: Iterable[MidiEvent], measures: tuple[MeasureSpan, ...], ppq: int
    ) -> tuple[PhraseBoundaryCandidate, ...]:
        onsets = sorted({event.absolute_tick for event in events if event.is_note_on})
        if not onsets:
            return ()
        result: list[PhraseBoundaryCandidate] = []
        first_span = next((span for span in measures if span.start_tick <= onsets[0] < span.end_tick), None)
        if first_span is not None:
            result.append(PhraseBoundaryCandidate(onsets[0], first_span.number, "FIRST_ONSET", 100))
        for previous, current in zip(onsets, onsets[1:]):
            if current - previous < 2 * ppq:
                continue
            span = next((item for item in measures if item.start_tick <= current < item.end_tick), None)
            if span is not None:
                result.append(PhraseBoundaryCandidate(current, span.number, "LONG_GAP_CANDIDATE", 70))
        return tuple(result)


def analyze_style_track(
    element: StyleElementModel,
    track_slice: StyleTrackSlice,
    analyzer: MeasurePhraseAnalyzer | None = None,
) -> MeasurePhraseAnalysis:
    """Apply M08 to one validated Style track slice."""
    track = element.midi.tracks[track_slice.physical_track - 1]
    valid = frozenset(track_slice.valid_event_indexes)
    events = tuple(event for event in track.events if event.event_index in valid)
    blocked = None
    if element.valid_end_tick is None:
        blocked = "; ".join(element.warnings) or "Style element nema potvrđen vremenski prozor."
    return (analyzer or MeasurePhraseAnalyzer()).analyze(
        element.midi,
        musical_events=events,
        window_end_tick=element.valid_end_tick,
        source_blocked_reason=blocked,
    )