"""Read-only instrument segmentation by MIDI bank/program state.

M10 partitions channel event streams at Program Change boundaries and records
the Bank Select state that was active at each boundary.  It deliberately does
not decide whether an address is Factory, User or Unknown.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable

from context_classifier import ClassificationInput, ContextClassifier, style_classification_input
from instrument_measurement_engine import (
    InstrumentMeasurement,
    InstrumentMeasurementEngine,
    MeasurementInput,
    MeasurementStatus,
)
from style_loader import MidiEvent, StyleElementModel, StyleTrackSlice


EventKey = tuple[int, int, int]
EventRef = tuple[int, int]


class SegmentationStatus(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class AddressStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    NO_PROGRAM = "NO_PROGRAM"


@dataclass(frozen=True, slots=True)
class SegmentAddress:
    bank_msb: int | None
    bank_lsb: int | None
    program: int | None
    status: AddressStatus

    @property
    def value(self) -> str | None:
        if self.status is not AddressStatus.COMPLETE:
            return None
        return f"{self.bank_msb}.{self.bank_lsb}.{self.program}"


@dataclass(frozen=True, slots=True)
class SegmentationInput:
    source_sha256: str
    events: tuple[MidiEvent, ...]
    ticks_per_beat: int | None
    window_start_tick: int = 0
    window_end_tick: int | None = None
    classification_input: ClassificationInput | None = None
    source_blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class InstrumentSegment:
    ordinal: int
    channel: int
    start_tick: int
    end_tick: int
    start_key: EventKey
    end_key: EventKey | None
    address: SegmentAddress
    identity_status: str
    selection_event_refs: tuple[EventRef, ...]
    event_refs: tuple[EventRef, ...]
    note_on_count: int
    crossing_boundary_note_count: int
    status: SegmentationStatus
    measurement: InstrumentMeasurement
    warnings: tuple[str, ...]
    protections: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    source_sha256: str
    status: SegmentationStatus
    segments: tuple[InstrumentSegment, ...]
    musical_channels: tuple[int, ...]
    warnings: tuple[str, ...]
    protections: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Selection:
    key: EventKey
    event: MidiEvent
    bank_msb: int | None
    bank_lsb: int | None
    setup_refs: tuple[EventRef, ...]


class InstrumentSegmenter:
    """Split events at Program Change boundaries without resolving identity."""

    def __init__(self, measurement_engine: InstrumentMeasurementEngine | None = None) -> None:
        self.measurement_engine = measurement_engine or InstrumentMeasurementEngine()

    def segment(self, source: SegmentationInput) -> SegmentationResult:
        events = tuple(
            event for event in source.events
            if event.absolute_tick >= source.window_start_tick
            and (source.window_end_tick is None or event.absolute_tick < source.window_end_tick)
            and event.channel is not None
        )
        inferred_end = max((event.absolute_tick + 1 for event in events), default=source.window_start_tick + 1)
        end_tick = source.window_end_tick if source.window_end_tick is not None else inferred_end
        protections = [
            "M10 je Analyze-only i ne određuje Factory, User ili Unknown identitet adrese.",
            "Granica segmenta nije dopuštenje za promjenu Bank Select ili Program Change događaja.",
        ]
        warnings: list[str] = []
        if source.source_blocked_reason:
            warnings.append(source.source_blocked_reason)
        channels = tuple(sorted({event.channel + 1 for event in events if event.is_note_on}))
        if len(channels) > 1:
            warnings.append(
                "Ulaz sadrži više glazbenih kanala; segmenti su odvojeni po kanalu, ali zajednički part ostaje PARTIAL."
            )

        by_channel: dict[int, list[MidiEvent]] = defaultdict(list)
        for event in events:
            by_channel[event.channel or 0].append(event)
        ambiguous_cross_track_ticks = self._ambiguous_cross_track_ticks(by_channel)
        if ambiguous_cross_track_ticks:
            rendered = ", ".join(
                f"kanal {channel + 1} @ tick {tick}"
                for channel, tick in ambiguous_cross_track_ticks
            )
            warnings.append(
                "Program Change dijeli tick s događajem istog kanala iz drugog tracka; "
                f"redoslijed nije potvrđen ({rendered})."
            )
        segments: list[InstrumentSegment] = []
        for channel, channel_events in sorted(by_channel.items()):
            segments.extend(self._channel_segments(source, channel, tuple(channel_events), end_tick))
        segments = [
            replace(segment, ordinal=ordinal)
            for ordinal, segment in enumerate(segments, start=1)
        ]

        blocked = bool(source.source_blocked_reason)
        partial = bool(warnings) or not segments or any(
            segment.status is not SegmentationStatus.READY for segment in segments
        )
        status = SegmentationStatus.BLOCKED if blocked else (
            SegmentationStatus.PARTIAL if partial else SegmentationStatus.READY
        )
        return SegmentationResult(
            source.source_sha256, status, tuple(segments), channels,
            tuple(warnings), tuple(protections),
        )

    @staticmethod
    def _ambiguous_cross_track_ticks(
        by_channel: dict[int, list[MidiEvent]],
    ) -> tuple[tuple[int, int], ...]:
        """Find same-channel cross-track ticks whose Program Change order is ambiguous.

        Track index provides a reproducible storage order, but SMF does not make that
        order a musical timing guarantee across simultaneous tracks.  M10 therefore
        keeps producing a deterministic read-only view while marking the overall
        result PARTIAL whenever that order could change a segment boundary.
        """
        ambiguous: list[tuple[int, int]] = []
        for channel, events in sorted(by_channel.items()):
            by_tick: dict[int, list[MidiEvent]] = defaultdict(list)
            for event in events:
                by_tick[event.absolute_tick].append(event)
            for tick, simultaneous in sorted(by_tick.items()):
                if len({event.track_index for event in simultaneous}) < 2:
                    continue
                if any(event.kind == "program_change" for event in simultaneous):
                    ambiguous.append((channel, tick))
        return tuple(ambiguous)

    def _channel_segments(
        self,
        source: SegmentationInput,
        channel: int,
        events: tuple[MidiEvent, ...],
        window_end_tick: int,
    ) -> list[InstrumentSegment]:
        ordered = tuple(sorted(events, key=self._key))
        selections = self._selections(ordered)
        boundaries: list[tuple[EventKey, _Selection | None]] = []
        prefix = tuple(
            event for event in ordered
            if not selections or self._key(event) < selections[0].key
        )
        prefix_has_content = any(
            not (
                event.kind == "control_change"
                and len(event.data) == 2
                and event.data[0] in (0, 32)
            )
            for event in prefix
        )
        if not selections or prefix_has_content:
            boundaries.append(((source.window_start_tick, -1, -1), None))
        boundaries.extend((selection.key, selection) for selection in selections)
        crossing = self._crossing_counts(ordered, tuple(key for key, _ in boundaries))
        result: list[InstrumentSegment] = []

        for index, (start_key, selection) in enumerate(boundaries):
            end_key = boundaries[index + 1][0] if index + 1 < len(boundaries) else None
            selected_events = tuple(
                event for event in ordered
                if self._key(event) >= start_key and (end_key is None or self._key(event) < end_key)
            )
            if not selected_events:
                continue
            start_tick = selection.event.absolute_tick if selection else source.window_start_tick
            end_tick = end_key[0] if end_key is not None else window_end_tick
            address = self._address(selection)
            segment_warnings: list[str] = []
            segment_protections = ["Identity status ostaje UNRESOLVED dok K01/K02 ne prođu."]
            if address.status is AddressStatus.INCOMPLETE:
                segment_warnings.append("Program Change nema potpunu CC00/CC32 adresu.")
            elif address.status is AddressStatus.NO_PROGRAM:
                segment_warnings.append("Događaji prije prvog Program Changea nemaju potvrđen program.")
            crossing_count = crossing.get(start_key, 0)
            if crossing_count:
                segment_warnings.append(
                    f"Nota koje prelaze sljedeću Program Change granicu: {crossing_count}."
                )
                segment_protections.append("Note preko granice instrumenta zahtijevaju ručnu provjeru.")

            measurement_end = max(
                end_tick, start_tick + 1,
                max((event.absolute_tick + 1 for event in selected_events), default=start_tick + 1),
            )
            classification = None
            if source.classification_input is not None:
                classification = ContextClassifier().classify(replace(
                    source.classification_input,
                    events=selected_events,
                    window_start_tick=start_tick,
                    window_end_tick=measurement_end,
                ))
            measurement = self.measurement_engine.measure(MeasurementInput(
                source_sha256=source.source_sha256,
                events=selected_events,
                ticks_per_beat=source.ticks_per_beat,
                window_start_tick=start_tick,
                window_end_tick=measurement_end,
                classification=classification,
                source_blocked_reason=source.source_blocked_reason,
            ))
            segment_blocked = measurement.status is MeasurementStatus.BLOCKED
            segment_partial = bool(segment_warnings) or measurement.status is MeasurementStatus.PARTIAL
            segment_status = SegmentationStatus.BLOCKED if segment_blocked else (
                SegmentationStatus.PARTIAL if segment_partial else SegmentationStatus.READY
            )
            refs = tuple((event.track_index, event.event_index) for event in selected_events)
            selection_refs = selection.setup_refs if selection else ()
            result.append(InstrumentSegment(
                len(result) + 1, channel + 1, start_tick, end_tick, start_key, end_key,
                address, "UNRESOLVED", selection_refs, refs,
                sum(event.is_note_on for event in selected_events), crossing_count,
                segment_status, measurement, tuple(segment_warnings),
                tuple(segment_protections),
            ))
        return result

    @classmethod
    def _selections(cls, events: tuple[MidiEvent, ...]) -> tuple[_Selection, ...]:
        bank_msb: int | None = None
        bank_lsb: int | None = None
        msb_ref: EventRef | None = None
        lsb_ref: EventRef | None = None
        result: list[_Selection] = []
        for event in events:
            if event.kind == "control_change" and len(event.data) == 2:
                if event.data[0] == 0:
                    bank_msb = event.data[1]
                    msb_ref = (event.track_index, event.event_index)
                elif event.data[0] == 32:
                    bank_lsb = event.data[1]
                    lsb_ref = (event.track_index, event.event_index)
            elif event.kind == "program_change" and event.data:
                refs = tuple(ref for ref in (msb_ref, lsb_ref, (event.track_index, event.event_index)) if ref)
                result.append(_Selection(cls._key(event), event, bank_msb, bank_lsb, refs))
        return tuple(result)

    @staticmethod
    def _address(selection: _Selection | None) -> SegmentAddress:
        if selection is None:
            return SegmentAddress(None, None, None, AddressStatus.NO_PROGRAM)
        program = selection.event.data[0]
        status = (
            AddressStatus.COMPLETE
            if selection.bank_msb is not None and selection.bank_lsb is not None
            else AddressStatus.INCOMPLETE
        )
        return SegmentAddress(selection.bank_msb, selection.bank_lsb, program, status)

    @classmethod
    def _crossing_counts(
        cls, events: tuple[MidiEvent, ...], starts: tuple[EventKey, ...]
    ) -> dict[EventKey, int]:
        active: dict[tuple[int, int], deque[EventKey]] = defaultdict(deque)
        counts: dict[EventKey, int] = defaultdict(int)
        for event in events:
            if event.channel is None or len(event.data) != 2:
                continue
            key = (event.channel, event.data[0])
            event_key = cls._key(event)
            if event.is_note_on:
                active[key].append(event_key)
            elif event.kind == "note_off" or (event.kind == "note_on" and event.data[1] == 0):
                if not active[key]:
                    continue
                note_start = active[key].popleft()
                segment_start = max((start for start in starts if start <= note_start), default=None)
                next_start = min((start for start in starts if start > segment_start), default=None) if segment_start else None
                if segment_start is not None and next_start is not None and event_key >= next_start:
                    counts[segment_start] += 1
        # An unterminated note is still known to cross a later Program Change
        # boundary.  Waiting for Note Off would silently miss exactly the unsafe
        # case that must keep segmentation conservative.
        for note_starts in active.values():
            for note_start in note_starts:
                segment_start = max((start for start in starts if start <= note_start), default=None)
                if segment_start is None:
                    continue
                if any(start > note_start for start in starts):
                    counts[segment_start] += 1
        return counts

    @staticmethod
    def _key(event: MidiEvent) -> EventKey:
        return event.absolute_tick, event.track_index, event.event_index


def segment_style_track(
    element: StyleElementModel,
    track_slice: StyleTrackSlice,
    segmenter: InstrumentSegmenter | None = None,
) -> SegmentationResult:
    """Apply M10 to one M06-validated Style track slice."""
    classification_input = style_classification_input(element, track_slice)
    return (segmenter or InstrumentSegmenter()).segment(SegmentationInput(
        source_sha256=element.midi.sha256,
        events=classification_input.events,
        ticks_per_beat=element.midi.ticks_per_beat,
        window_end_tick=element.valid_end_tick,
        classification_input=classification_input,
        source_blocked_reason=classification_input.source_blocked_reason,
    ))