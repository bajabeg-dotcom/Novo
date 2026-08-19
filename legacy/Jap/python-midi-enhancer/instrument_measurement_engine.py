"""Read-only shared instrument measurements for the MIDI Enhancer.

M09 combines immutable MIDI events with optional M07 context and M08 timeline
results. It derives descriptive statistics only and has no writer path.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from statistics import mean, median, pstdev
from typing import Iterable

from context_classifier import (
    ClassificationStatus,
    ContextClassification,
    ContextClassifier,
    EditPolicy,
    Encoding,
    FunctionLabel,
    style_classification_input,
)
from measure_phrase_analyzer import (
    AnalysisStatus,
    MeasurePhraseAnalysis,
    MeasurePhraseAnalyzer,
    analyze_style_track,
)
from style_loader import MidiEvent, StyleElementModel, StyleTrackSlice


class MeasurementStatus(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class Distribution:
    count: int
    minimum: float | None
    maximum: float | None
    mean: float | None
    median: float | None
    population_stddev: float | None


@dataclass(frozen=True, slots=True)
class MeasuredNote:
    track_index: int
    channel: int
    pitch: int
    velocity: int
    start_tick: int
    end_tick: int | None


@dataclass(frozen=True, slots=True)
class ControllerMeasurement:
    controller: int
    values: Distribution


@dataclass(frozen=True, slots=True)
class MeasureMeasurement:
    measure: int
    start_tick: int
    end_tick: int
    note_count: int
    onset_count: int
    density_per_beat: float
    velocity: Distribution
    duration_beats: Distribution


@dataclass(frozen=True, slots=True)
class PhraseMeasurement:
    phrase: int
    start_tick: int
    end_tick: int
    boundary_reason: str
    boundary_confidence: int
    note_count: int
    density_per_beat: float
    velocity: Distribution
    duration_beats: Distribution


@dataclass(frozen=True, slots=True)
class MeasurementEvidence:
    metric: str
    status: str
    rule: str


@dataclass(frozen=True, slots=True)
class MeasurementInput:
    source_sha256: str
    events: tuple[MidiEvent, ...]
    ticks_per_beat: int | None
    window_start_tick: int = 0
    window_end_tick: int | None = None
    classification: ContextClassification | None = None
    timeline: MeasurePhraseAnalysis | None = None
    source_blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class InstrumentMeasurement:
    source_sha256: str
    status: MeasurementStatus
    function: FunctionLabel
    encoding: Encoding
    inherited_edit_policy: EditPolicy
    window_start_tick: int
    window_end_tick: int
    note_count: int
    closed_note_count: int
    open_note_count: int
    orphan_note_off_count: int
    pitch_minimum: int | None
    pitch_maximum: int | None
    velocity: Distribution
    duration_ticks: Distribution
    duration_beats: Distribution
    density_per_beat: float | None
    maximum_sounding_polyphony: int
    maximum_exact_onset_polyphony: int
    controller_measurements: tuple[ControllerMeasurement, ...]
    pitch_bend_count: int
    poly_aftertouch_count: int
    channel_aftertouch_count: int
    measure_measurements: tuple[MeasureMeasurement, ...]
    phrase_measurements: tuple[PhraseMeasurement, ...]
    evidence: tuple[MeasurementEvidence, ...]
    warnings: tuple[str, ...]
    protections: tuple[str, ...]


class InstrumentMeasurementEngine:
    """Derive shared instrument metrics while preserving upstream protections."""

    def measure(self, source: MeasurementInput) -> InstrumentMeasurement:
        events = tuple(
            event for event in source.events
            if event.absolute_tick >= source.window_start_tick
            and (source.window_end_tick is None or event.absolute_tick < source.window_end_tick)
        )
        inferred_end = max(
            (event.absolute_tick + 1 for event in events),
            default=source.window_start_tick + 1,
        )
        end_tick = source.window_end_tick if source.window_end_tick is not None else inferred_end
        notes, orphan_offs = self._pair_notes(events)
        note_ons = tuple(event for event in events if event.is_note_on)
        closed = tuple(note for note in notes if note.end_tick is not None)
        open_notes = tuple(note for note in notes if note.end_tick is None)
        ppq = source.ticks_per_beat

        velocity = self._distribution(note.velocity for note in notes)
        duration_ticks = self._distribution(
            note.end_tick - note.start_tick for note in closed if note.end_tick is not None
        )
        duration_beats = self._distribution(
            (note.end_tick - note.start_tick) / ppq
            for note in closed if note.end_tick is not None and ppq is not None
        )
        density = None
        if (
            ppq is not None
            and source.window_end_tick is not None
            and end_tick > source.window_start_tick
        ):
            density = len(note_ons) / ((end_tick - source.window_start_tick) / ppq)

        controllers = self._controllers(events)
        warnings: list[str] = []
        protections = [
            "M09 je Analyze-only: mjerenja ne autoriziraju Suggest, Change, Humanize ili Enhance."
        ]
        evidence = [
            MeasurementEvidence(
                "NOTE_EVENT_COUNTS", "DERIVED",
                "Note On/Off događaji sparuju se FIFO po kanalu i visini unutar potvrđenog prozora.",
            ),
            MeasurementEvidence(
                "VELOCITY_PITCH_DURATION", "DERIVED",
                "Statistike koriste sačuvane MIDI vrijednosti; trajanje koristi samo zatvorene note.",
            ),
            MeasurementEvidence(
                "CONTROLLERS", "DERIVED",
                "Control Change, pitch bend i aftertouch broje se bez semantičkog nagađanja.",
            ),
        ]

        classification = source.classification
        function = classification.function if classification else FunctionLabel.UNKNOWN
        encoding = classification.encoding if classification else Encoding.UNKNOWN
        policy = classification.edit_policy if classification else EditPolicy.DO_NOT_TOUCH
        blocked = bool(source.source_blocked_reason)
        note_track_indexes = {
            event.track_index
            for event in events
            if event.kind in ("note_on", "note_off")
        }
        if len(note_track_indexes) > 1:
            blocked = True
            warnings.append(
                "Note iz više fizičkih trackova ne smiju se spojiti u jedan M09 profil."
            )
            protections.append(
                "Višetrack ulaz zahtijeva zaseban profil po tracku prije glazbene odluke."
            )
        if source.source_blocked_reason:
            warnings.append(source.source_blocked_reason)
        if not notes:
            warnings.append("Nema Note On događaja za profil instrumenta.")
        if open_notes:
            warnings.append(f"Nezatvorenih nota: {len(open_notes)}.")
        if orphan_offs:
            warnings.append(f"Note Off događaja bez odgovarajućeg Note On: {orphan_offs}.")
        if ppq is None:
            warnings.append("SMPTE division: trajanje u beatovima i gustoća nisu izvedeni.")
        elif source.window_end_tick is None:
            warnings.append(
                "Gustoća nije izvedena jer završetak mjernog prozora nije eksplicitno potvrđen."
            )
        if classification is not None:
            evidence.append(MeasurementEvidence(
                "CONTEXT",
                "CONFLICT" if classification.status is ClassificationStatus.BLOCKED else "INFERRED",
                f"M07 function={classification.function.value}, confidence={classification.confidence}, policy={classification.edit_policy.value}.",
            ))
            protections.extend(classification.evidence.protections)
            if classification.status is ClassificationStatus.BLOCKED:
                blocked = True
                warnings.append("M07 kontekst je BLOCKED; profil se ne smije koristiti za odluku o izmjeni.")
            if classification.encoding is not Encoding.ORDINARY_MIDI:
                protections.append("Poseban ili nepoznat encoding zadržava DO_NOT_TOUCH zaštitu.")
            if classification.fixed_intro_ending_candidate:
                protections.append("Fixed Intro/Ending kandidat ne smije dobiti automatsku korekciju.")
        usable_timeline = source.timeline
        timeline_mismatches: list[str] = []
        if usable_timeline is not None:
            if usable_timeline.source_sha256 != source.source_sha256:
                timeline_mismatches.append("SHA-256 izvora")
            if usable_timeline.ticks_per_beat != source.ticks_per_beat:
                timeline_mismatches.append("PPQ")
            if (
                usable_timeline.window_start_tick != source.window_start_tick
                or usable_timeline.window_end_tick != end_tick
            ):
                timeline_mismatches.append("vremenski prozor")
        if timeline_mismatches:
            blocked = True
            warnings.append(
                "M08 timeline ne pripada istom mjernom ulazu: "
                + ", ".join(timeline_mismatches)
                + "."
            )
            protections.append(
                "Foreign ili neusklađen M08 timeline ne smije proizvesti profile mjera/fraza."
            )
            usable_timeline = None

        if source.timeline is not None:
            evidence.append(MeasurementEvidence(
                "MEASURE_PHRASE_CONTEXT",
                "CONFLICT" if timeline_mismatches else (
                    "DERIVED" if source.timeline.status is AnalysisStatus.READY else "UNKNOWN"
                ),
                f"M08 status={source.timeline.status.value}; mjere i fraze koriste se samo kada su dostupne i provenance je usklađen.",
            ))
            protections.extend(source.timeline.protections)
            if source.timeline.status is AnalysisStatus.BLOCKED:
                blocked = True
                warnings.append("M08 timeline je BLOCKED; profil nema valjan kontekst mjere/fraze.")

        measure_metrics = self._measure_metrics(notes, usable_timeline, ppq)
        phrase_metrics = self._phrase_metrics(notes, usable_timeline, ppq, end_tick)

        status = MeasurementStatus.BLOCKED if blocked else (
            MeasurementStatus.PARTIAL if warnings else MeasurementStatus.READY
        )
        return InstrumentMeasurement(
            source.source_sha256, status, function, encoding, policy,
            source.window_start_tick, end_tick, len(notes), len(closed), len(open_notes),
            orphan_offs, min((note.pitch for note in notes), default=None),
            max((note.pitch for note in notes), default=None), velocity, duration_ticks,
            duration_beats, density, self._maximum_sounding_polyphony(notes, end_tick),
            self._maximum_exact_onset_polyphony(note_ons), controllers,
            sum(event.kind == "pitch_bend" for event in events),
            sum(event.kind == "poly_aftertouch" for event in events),
            sum(event.kind == "channel_aftertouch" for event in events),
            measure_metrics, phrase_metrics, tuple(evidence), tuple(warnings),
            tuple(dict.fromkeys(protections)),
        )

    @staticmethod
    def _distribution(values: Iterable[float]) -> Distribution:
        items = tuple(values)
        if not items:
            return Distribution(0, None, None, None, None, None)
        return Distribution(
            len(items), min(items), max(items), mean(items), median(items),
            pstdev(items) if len(items) > 1 else 0.0,
        )

    @staticmethod
    def _pair_notes(events: Iterable[MidiEvent]) -> tuple[tuple[MeasuredNote, ...], int]:
        active: dict[tuple[int, int, int], deque[tuple[int, int]]] = defaultdict(deque)
        notes: list[MeasuredNote] = []
        orphan_offs = 0
        for event in sorted(events, key=lambda item: (item.absolute_tick, item.event_index)):
            if event.channel is None or len(event.data) != 2:
                continue
            key = (event.track_index, event.channel, event.data[0])
            if event.is_note_on:
                active[key].append((event.absolute_tick, event.data[1]))
            elif event.kind == "note_off" or (event.kind == "note_on" and event.data[1] == 0):
                if active[key]:
                    start, velocity = active[key].popleft()
                    notes.append(MeasuredNote(
                        event.track_index, event.channel, key[2], velocity,
                        start, event.absolute_tick,
                    ))
                else:
                    orphan_offs += 1
        for (track_index, channel, pitch), pending in active.items():
            for start, velocity in pending:
                notes.append(MeasuredNote(
                    track_index, channel, pitch, velocity, start, None,
                ))
        return tuple(sorted(
            notes,
            key=lambda note: (note.start_tick, note.track_index, note.channel, note.pitch),
        )), orphan_offs

    @classmethod
    def _controllers(cls, events: Iterable[MidiEvent]) -> tuple[ControllerMeasurement, ...]:
        values: dict[int, list[int]] = defaultdict(list)
        for event in events:
            if event.kind == "control_change" and len(event.data) == 2:
                values[event.data[0]].append(event.data[1])
        return tuple(
            ControllerMeasurement(controller, cls._distribution(items))
            for controller, items in sorted(values.items())
        )

    @staticmethod
    def _maximum_sounding_polyphony(notes: Iterable[MeasuredNote], end_tick: int) -> int:
        changes: list[tuple[int, int]] = []
        for note in notes:
            changes.append((note.start_tick, 1))
            changes.append((note.end_tick if note.end_tick is not None else end_tick, -1))
        active = maximum = 0
        for _tick, delta in sorted(changes, key=lambda item: (item[0], item[1])):
            active += delta
            maximum = max(maximum, active)
        return maximum

    @staticmethod
    def _maximum_exact_onset_polyphony(events: Iterable[MidiEvent]) -> int:
        counts: dict[int, int] = defaultdict(int)
        for event in events:
            counts[event.absolute_tick] += 1
        return max(counts.values(), default=0)

    @classmethod
    def _measure_metrics(
        cls,
        notes: tuple[MeasuredNote, ...],
        timeline: MeasurePhraseAnalysis | None,
        ppq: int | None,
    ) -> tuple[MeasureMeasurement, ...]:
        if timeline is None or ppq is None or not timeline.measures:
            return ()
        result: list[MeasureMeasurement] = []
        for span in timeline.measures:
            selected = tuple(note for note in notes if span.start_tick <= note.start_tick < span.end_tick)
            beats = (span.end_tick - span.start_tick) / ppq
            result.append(MeasureMeasurement(
                span.number, span.start_tick, span.end_tick, len(selected),
                len({note.start_tick for note in selected}), len(selected) / beats if beats else 0.0,
                cls._distribution(note.velocity for note in selected),
                cls._distribution(
                    (note.end_tick - note.start_tick) / ppq
                    for note in selected if note.end_tick is not None
                ),
            ))
        return tuple(result)

    @classmethod
    def _phrase_metrics(
        cls,
        notes: tuple[MeasuredNote, ...],
        timeline: MeasurePhraseAnalysis | None,
        ppq: int | None,
        end_tick: int,
    ) -> tuple[PhraseMeasurement, ...]:
        if timeline is None or ppq is None or not timeline.phrase_boundaries:
            return ()
        boundaries = tuple(sorted(timeline.phrase_boundaries, key=lambda item: item.tick))
        result: list[PhraseMeasurement] = []
        for index, boundary in enumerate(boundaries):
            phrase_end = boundaries[index + 1].tick if index + 1 < len(boundaries) else end_tick
            if phrase_end <= boundary.tick:
                continue
            selected = tuple(note for note in notes if boundary.tick <= note.start_tick < phrase_end)
            beats = (phrase_end - boundary.tick) / ppq
            result.append(PhraseMeasurement(
                index + 1, boundary.tick, phrase_end, boundary.reason, boundary.confidence,
                len(selected), len(selected) / beats if beats else 0.0,
                cls._distribution(note.velocity for note in selected),
                cls._distribution(
                    (note.end_tick - note.start_tick) / ppq
                    for note in selected if note.end_tick is not None
                ),
            ))
        return tuple(result)


def measure_style_track(
    element: StyleElementModel,
    track_slice: StyleTrackSlice,
    engine: InstrumentMeasurementEngine | None = None,
) -> InstrumentMeasurement:
    """Run M07, M08 and M09 for one validated Style track slice."""
    classification_source = style_classification_input(element, track_slice)
    classification = ContextClassifier().classify(classification_source)
    timeline = analyze_style_track(element, track_slice, MeasurePhraseAnalyzer())
    return (engine or InstrumentMeasurementEngine()).measure(MeasurementInput(
        source_sha256=element.midi.sha256,
        events=classification_source.events,
        ticks_per_beat=element.midi.ticks_per_beat,
        window_end_tick=element.valid_end_tick,
        classification=classification,
        timeline=timeline,
        source_blocked_reason=classification_source.source_blocked_reason,
    ))