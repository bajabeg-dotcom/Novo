"""Read-only musical context classification for MIDI event streams.

The classifier deliberately separates three questions:

* ``structural_role`` -- a role confirmed by the source/container;
* ``encoding`` -- ordinary notes versus a possible Pa-series Guitar Mode stream;
* ``function`` -- what the part appears to do musically.

The generic core has no knowledge of Style channel numbers.  The small Style
adapter only transfers context already validated by :mod:`style_loader`.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from style_loader import MidiEvent, StyleElementModel, StyleTrackSlice


class StructuralRole(str, Enum):
    DRUM = "DRUM"
    PERC = "PERC"
    BASS = "BASS"
    ACC = "ACC"
    UNKNOWN = "UNKNOWN"


class Encoding(str, Enum):
    ORDINARY_MIDI = "ORDINARY_MIDI"
    GUITAR_MODE_CANDIDATE = "GUITAR_MODE_CANDIDATE"
    UNKNOWN = "UNKNOWN"


class FunctionLabel(str, Enum):
    RHYTHM_DRUM = "RHYTHM_DRUM"
    RHYTHM_PERC = "RHYTHM_PERC"
    BASS_ACCOMP = "BASS_ACCOMP"
    ACCOMP_CHORDAL = "ACCOMP_CHORDAL"
    ACCOMP_LINE_RIFF = "ACCOMP_LINE_RIFF"
    RHYTHM_GUITAR = "RHYTHM_GUITAR"
    SOLO_CANDIDATE = "SOLO_CANDIDATE"
    UNKNOWN = "UNKNOWN"


class ClassificationStatus(str, Enum):
    CLASSIFIED = "CLASSIFIED"
    UNCERTAIN = "UNCERTAIN"
    BLOCKED = "BLOCKED"


class EditPolicy(str, Enum):
    SAFE_BOUNDED = "SAFE_BOUNDED"
    SUGGEST_ONLY = "SUGGEST_ONLY"
    DO_NOT_TOUCH = "DO_NOT_TOUCH"


@dataclass(frozen=True, slots=True)
class ClassificationInput:
    """Generic immutable input; all events must belong to one logical part."""

    events: tuple[MidiEvent, ...]
    ticks_per_beat: int | None
    window_start_tick: int = 0
    window_end_tick: int | None = None
    structural_role: StructuralRole = StructuralRole.UNKNOWN
    track_name: str | None = None
    sound_text: str | None = None
    element: str | None = None
    source_blocked_reason: str | None = None
    encoding_hint: Encoding | None = None
    encoding_evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NoteSpan:
    channel: int
    pitch: int
    velocity: int
    start_tick: int
    end_tick: int | None


@dataclass(frozen=True, slots=True)
class TrackFeatures:
    note_count: int
    onset_count: int
    maximum_onset_polyphony: int
    chord_onset_ratio: float
    monophonic_onset_ratio: float
    average_pitch: float | None
    average_duration_beats: float | None
    density_per_beat: float
    repeated_pattern_ratio: float
    unique_pitch_ratio: float
    pitch_bend_count: int
    high_note_count: int
    rx_high_note_ambiguous: bool
    onset_cluster_tolerance_ticks: int
    musical_channels: tuple[int, ...]
    programs: tuple[int, ...]
    note_spans: tuple[NoteSpan, ...]


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    positive: tuple[str, ...]
    counter: tuple[str, ...]
    protections: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContextClassification:
    structural_role: StructuralRole
    encoding: Encoding
    function: FunctionLabel
    fixed_intro_ending_candidate: bool
    rx_high_note_ambiguous: bool
    status: ClassificationStatus
    confidence: int
    edit_policy: EditPolicy
    features: TrackFeatures
    evidence: EvidenceBundle


class FeatureExtractor:
    """Derive immutable measurements without changing source events or bytes."""

    def extract(self, source: ClassificationInput) -> TrackFeatures:
        events = tuple(
            event for event in source.events
            if event.absolute_tick >= source.window_start_tick
            and (source.window_end_tick is None or event.absolute_tick < source.window_end_tick)
        )
        notes = self._pair_notes(events)
        note_ons = [event for event in events if event.is_note_on]
        ppq = source.ticks_per_beat or 480
        onset_tolerance = max(1, round(ppq / 48))
        ordered_onsets = self._cluster_onsets(note_ons, onset_tolerance)
        onset_count = len(ordered_onsets)
        chord_count = sum(len(pitches) >= 2 for _, pitches in ordered_onsets)
        mono_count = sum(len(pitches) == 1 for _, pitches in ordered_onsets)
        pitches = [event.data[0] for event in note_ons]
        durations = [note.end_tick - note.start_tick for note in notes if note.end_tick is not None]
        if note_ons:
            first_tick = min(event.absolute_tick for event in note_ons)
            last_tick = max(event.absolute_tick for event in note_ons)
            if source.window_end_tick is not None:
                last_tick = max(last_tick, source.window_end_tick)
            span_beats = max((last_tick - first_tick) / ppq, 1 / 16)
            density = len(note_ons) / span_beats
        else:
            density = 0.0
        signatures = tuple(tuple(sorted(pitch_group)) for _, pitch_group in ordered_onsets)
        programs = tuple(sorted({event.data[0] for event in events if event.kind == "program_change" and event.data}))
        return TrackFeatures(
            note_count=len(note_ons),
            onset_count=onset_count,
            maximum_onset_polyphony=max((len(group) for _, group in ordered_onsets), default=0),
            chord_onset_ratio=chord_count / onset_count if onset_count else 0.0,
            monophonic_onset_ratio=mono_count / onset_count if onset_count else 0.0,
            average_pitch=sum(pitches) / len(pitches) if pitches else None,
            average_duration_beats=(sum(durations) / len(durations) / ppq) if durations else None,
            density_per_beat=density,
            repeated_pattern_ratio=self._repeated_pattern_ratio(signatures),
            unique_pitch_ratio=len(set(pitches)) / len(pitches) if pitches else 0.0,
            pitch_bend_count=sum(event.kind == "pitch_bend" for event in events),
            high_note_count=sum(pitch >= 96 for pitch in pitches),
            rx_high_note_ambiguous=any(pitch >= 96 for pitch in pitches),
            onset_cluster_tolerance_ticks=onset_tolerance,
            musical_channels=tuple(sorted({event.channel for event in note_ons if event.channel is not None})),
            programs=programs,
            note_spans=notes,
        )

    @staticmethod
    def _cluster_onsets(
        note_ons: Iterable[MidiEvent], tolerance_ticks: int
    ) -> list[tuple[int, list[int]]]:
        """Group near-simultaneous attacks using a PPQ-scaled gesture window."""

        ordered = sorted(note_ons, key=lambda event: (event.absolute_tick, event.event_index))
        clusters: list[tuple[int, list[int]]] = []
        for event in ordered:
            if not clusters or event.absolute_tick - clusters[-1][0] > tolerance_ticks:
                clusters.append((event.absolute_tick, [event.data[0]]))
            else:
                clusters[-1][1].append(event.data[0])
        return clusters

    @staticmethod
    def _pair_notes(events: Iterable[MidiEvent]) -> tuple[NoteSpan, ...]:
        active: dict[tuple[int, int], deque[tuple[int, int]]] = defaultdict(deque)
        completed: list[NoteSpan] = []
        for event in events:
            if event.channel is None or len(event.data) != 2:
                continue
            key = (event.channel, event.data[0])
            if event.is_note_on:
                active[key].append((event.absolute_tick, event.data[1]))
            elif event.kind == "note_off" or (event.kind == "note_on" and event.data[1] == 0):
                if active[key]:
                    start, velocity = active[key].popleft()
                    completed.append(NoteSpan(event.channel, key[1], velocity, start, event.absolute_tick))
        for (channel, pitch), pending in active.items():
            for start, velocity in pending:
                completed.append(NoteSpan(channel, pitch, velocity, start, None))
        return tuple(sorted(completed, key=lambda note: (note.start_tick, note.channel, note.pitch)))

    @staticmethod
    def _repeated_pattern_ratio(signatures: tuple[tuple[int, ...], ...]) -> float:
        size = len(signatures)
        if size < 4:
            return 0.0
        best = 0.0
        for period in range(1, size // 2 + 1):
            comparisons = size - period
            matches = sum(signatures[index] == signatures[index - period] for index in range(period, size))
            best = max(best, matches / comparisons)
        return best


class ContextClassifier:
    def __init__(self, extractor: FeatureExtractor | None = None) -> None:
        self.extractor = extractor or FeatureExtractor()

    def classify(self, source: ClassificationInput) -> ContextClassification:
        features = self.extractor.extract(source)
        if source.source_blocked_reason:
            return self._result(
                source, features, Encoding.UNKNOWN, FunctionLabel.UNKNOWN,
                ClassificationStatus.BLOCKED, 0, EditPolicy.DO_NOT_TOUCH,
                (), (), (source.source_blocked_reason,),
            )
        if len(features.musical_channels) > 1:
            channels = ", ".join(str(channel + 1) for channel in features.musical_channels)
            return self._result(
                source, features, Encoding.UNKNOWN, FunctionLabel.UNKNOWN,
                ClassificationStatus.BLOCKED, 0, EditPolicy.DO_NOT_TOUCH,
                (), (f"ulaz sadrži više glazbenih MIDI kanala: {channels}",),
                ("kanale treba razdvojiti prije funkcijske klasifikacije",),
            )
        if not features.note_count:
            return self._result(
                source, features, Encoding.UNKNOWN, FunctionLabel.UNKNOWN,
                ClassificationStatus.UNCERTAIN, 0, EditPolicy.DO_NOT_TOUCH,
                (), ("nema Note On događaja u potvrđenom prozoru",),
                ("prazan track se ne mijenja",),
            )

        guitar = self._is_guitar(source, features)
        encoding, encoding_evidence = self._encoding(source)
        positive = list(encoding_evidence)
        counter: list[str] = []
        protections: list[str] = []

        if features.rx_high_note_ambiguous:
            protections.append(
                "visoke note mogu biti RX Noise; same ne dokazuju Guitar Mode i ne smiju se automatski mijenjati"
            )

        if source.structural_role is StructuralRole.DRUM:
            function = FunctionLabel.RHYTHM_DRUM
            confidence = 98
            policy = EditPolicy.SAFE_BOUNDED
            positive.append("izvor potvrđuje strukturnu ulogu DRUM")
        elif source.structural_role is StructuralRole.PERC:
            function = FunctionLabel.RHYTHM_PERC
            confidence = 98
            policy = EditPolicy.SAFE_BOUNDED
            positive.append("izvor potvrđuje strukturnu ulogu PERC")
        elif source.structural_role is StructuralRole.BASS:
            function = FunctionLabel.BASS_ACCOMP
            confidence = 96
            policy = EditPolicy.SAFE_BOUNDED
            positive.append("izvor potvrđuje strukturnu ulogu BASS")
        elif guitar and (
            features.chord_onset_ratio >= 0.30 or features.maximum_onset_polyphony >= 3
        ):
            function = FunctionLabel.RHYTHM_GUITAR
            confidence = 84
            policy = EditPolicy.SAFE_BOUNDED
            positive.extend((
                "guitar je potvrđena nazivom ili Program Change događajem",
                "akordske onset-grupe podržavaju ritam-gitarsku funkciju",
            ))
        elif features.chord_onset_ratio >= 0.35 or features.maximum_onset_polyphony >= 4:
            function = FunctionLabel.ACCOMP_CHORDAL
            confidence = 80
            policy = EditPolicy.SAFE_BOUNDED
            positive.append("učestale višeglasne onset-grupe podržavaju akordsku pratnju")
        elif (
            features.monophonic_onset_ratio >= 0.80
            and features.onset_count >= 4
            and features.repeated_pattern_ratio >= 0.60
        ):
            function = FunctionLabel.ACCOMP_LINE_RIFF
            confidence = 78
            policy = EditPolicy.SUGGEST_ONLY
            positive.append("pretežno monofon obrazac pokazuje ponovljivu tonsku figuru")
        elif (
            features.monophonic_onset_ratio >= 0.75
            and (features.pitch_bend_count > 0 or features.unique_pitch_ratio >= 0.55)
        ):
            function = FunctionLabel.SOLO_CANDIDATE
            confidence = 74 if features.pitch_bend_count else 68
            policy = EditPolicy.SUGGEST_ONLY
            positive.append("pretežno monofona i promjenjiva linija podržava solo kandidata")
        else:
            function = FunctionLabel.UNKNOWN
            confidence = 45
            policy = EditPolicy.SUGGEST_ONLY
            counter.append("nema dovoljno dominantnih strukturnih ili funkcijskih obilježja")

        if source.structural_role is StructuralRole.ACC:
            positive.append("izvor potvrđuje strukturnu ulogu ACC")

        fixed_candidate = self._fixed_candidate(source, features)
        if fixed_candidate:
            positive.append("Intro 1/Ending 1 kontekst može sadržavati fiksnu harmoniju")
            protections.append("fiksni Intro/Ending kandidat zahtijeva korisničku provjeru harmonije")
            policy = self._stricter_policy(policy, EditPolicy.DO_NOT_TOUCH)
        if encoding is Encoding.GUITAR_MODE_CANDIDATE:
            protections.append("izvor označava mogući Guitar Mode; funkcija se klasificira zasebno")
            policy = self._stricter_policy(policy, EditPolicy.DO_NOT_TOUCH)
        if features.rx_high_note_ambiguous:
            high_ratio = features.high_note_count / features.note_count
            rx_policy = EditPolicy.DO_NOT_TOUCH if high_ratio >= 0.25 else EditPolicy.SUGGEST_ONLY
            policy = self._stricter_policy(policy, rx_policy)

        status = ClassificationStatus.CLASSIFIED if confidence >= 65 else ClassificationStatus.UNCERTAIN
        return self._result(
            source, features, encoding, function, status, confidence, policy,
            tuple(positive), tuple(counter), tuple(protections),
        )

    @staticmethod
    def _is_guitar(source: ClassificationInput, features: TrackFeatures) -> bool:
        text = " ".join(filter(None, (source.track_name, source.sound_text))).casefold()
        return any(24 <= program <= 31 for program in features.programs) or "guitar" in text or "gtr" in text

    @staticmethod
    def _encoding(source: ClassificationInput) -> tuple[Encoding, tuple[str, ...]]:
        """Use explicit/configurable evidence; note ranges are not portable proof."""

        if source.encoding_hint is Encoding.GUITAR_MODE_CANDIDATE:
            evidence = source.encoding_evidence or (
                "vanjski izvor označava mogući Guitar Mode zapis",
            )
            return Encoding.GUITAR_MODE_CANDIDATE, evidence
        if source.encoding_hint is Encoding.UNKNOWN:
            return Encoding.UNKNOWN, source.encoding_evidence
        return Encoding.ORDINARY_MIDI, source.encoding_evidence

    @staticmethod
    def _fixed_candidate(source: ClassificationInput, features: TrackFeatures) -> bool:
        melodic_context = source.structural_role in {StructuralRole.ACC, StructuralRole.UNKNOWN}
        return (
            melodic_context
            and features.note_count > 0
            and source.element in {"INTRO_1", "ENDING_1"}
        )

    @staticmethod
    def _stricter_policy(*policies: EditPolicy) -> EditPolicy:
        rank = {
            EditPolicy.SAFE_BOUNDED: 0,
            EditPolicy.SUGGEST_ONLY: 1,
            EditPolicy.DO_NOT_TOUCH: 2,
        }
        return max(policies, key=rank.__getitem__)

    @staticmethod
    def _result(
        source: ClassificationInput,
        features: TrackFeatures,
        encoding: Encoding,
        function: FunctionLabel,
        status: ClassificationStatus,
        confidence: int,
        policy: EditPolicy,
        positive: tuple[str, ...],
        counter: tuple[str, ...],
        protections: tuple[str, ...],
    ) -> ContextClassification:
        return ContextClassification(
            structural_role=source.structural_role,
            encoding=encoding,
            function=function,
            fixed_intro_ending_candidate=ContextClassifier._fixed_candidate(source, features),
            rx_high_note_ambiguous=features.rx_high_note_ambiguous,
            status=status,
            confidence=confidence,
            edit_policy=policy,
            features=features,
            evidence=EvidenceBundle(positive, counter, protections),
        )


def style_classification_input(
    element: StyleElementModel, track_slice: StyleTrackSlice
) -> ClassificationInput:
    """Adapt a validated Style slice without deriving roles from channels."""

    role_text = track_slice.role or ""
    if role_text in {"DRUM", "PERC", "BASS"}:
        role = StructuralRole(role_text)
    elif role_text.startswith("ACC"):
        role = StructuralRole.ACC
    else:
        role = StructuralRole.UNKNOWN
    physical_track_index = track_slice.physical_track - 1
    track = element.midi.tracks[physical_track_index]
    valid_indexes = frozenset(track_slice.valid_event_indexes)
    events = tuple(event for event in track.events if event.event_index in valid_indexes)
    blocked = None
    if element.valid_end_tick is None:
        blocked = "; ".join(element.warnings) or "Style element nema potvrđen vremenski prozor"
    return ClassificationInput(
        events=events,
        ticks_per_beat=element.midi.ticks_per_beat,
        window_end_tick=element.valid_end_tick,
        structural_role=role,
        track_name=track_slice.track_name,
        sound_text=track_slice.sound_text,
        element=element.element,
        source_blocked_reason=blocked,
    )


def classify_style_element(
    element: StyleElementModel, classifier: ContextClassifier | None = None
) -> tuple[ContextClassification, ...]:
    engine = classifier or ContextClassifier()
    return tuple(engine.classify(style_classification_input(element, item)) for item in element.tracks)