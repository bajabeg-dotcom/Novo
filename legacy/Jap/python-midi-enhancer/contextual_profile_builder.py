"""Read-only contextual Factory Style profile builder.

Profiles are never merged across source kind, full K01 address, M07 function,
Style Element, CV, structural role, encoding, or fixed Intro/Ending candidate.
The catalog is empirical reference data and does not authorize Suggest/Change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

from instrument_identity_resolver import IdentityStatus, InstrumentIdentityResolver
from instrument_segmenter import SegmentationStatus, segment_style_track
from style_loader import MidiEvent, StyleWorksLoader, sha256_path

FACTORY_SOURCE_KIND = "FACTORY_STYLE"


class ContextualProfileError(ValueError):
    """Raised when observations would violate profile isolation/provenance."""


@dataclass(frozen=True, slots=True)
class ProfileKey:
    source_kind: str
    address: str
    item_kind: str
    function: str
    element: str
    cv: int | None
    structural_role: str
    encoding: str
    fixed_intro_ending_candidate: bool


@dataclass(frozen=True, slots=True)
class ProfileObservation:
    source_id: str
    source_sha256: str
    source_kind: str
    member_name: str
    style_name: str
    key: ProfileKey
    official_name: str
    segment_status: str
    measurement_status: str
    velocities: tuple[int, ...]
    pitches: tuple[int, ...]
    duration_beats: tuple[float, ...]
    density_per_beat: float | None
    maximum_sounding_polyphony: int
    maximum_onset_polyphony: int
    controller_event_counts: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class DistributionSummary:
    count: int
    minimum: float | None
    maximum: float | None
    mean: float | None
    p10: float | None
    p25: float | None
    median: float | None
    p75: float | None
    p90: float | None


@dataclass(frozen=True, slots=True)
class ContextualInstrumentProfile:
    profile_id: str
    key: ProfileKey
    official_name: str
    observation_count: int
    style_count: int
    member_count: int
    note_count: int
    velocity: DistributionSummary
    pitch: DistributionSummary
    duration_beats: DistributionSummary
    density_per_beat: DistributionSummary
    maximum_sounding_polyphony: int
    maximum_onset_polyphony: int
    controller_event_counts: tuple[tuple[int, int], ...]
    segment_status_counts: tuple[tuple[str, int], ...]
    measurement_status_counts: tuple[tuple[str, int], ...]
    source_members: tuple[str, ...]
    evidence_status: str
    safety_policy: str


@dataclass(frozen=True, slots=True)
class ContextualProfileCatalog:
    schema_version: str
    source_id: str
    source_path: str
    source_sha256: str
    source_kind: str
    observation_count: int
    profile_count: int
    excluded_identity_counts: tuple[tuple[str, int], ...]
    profiles: tuple[ContextualInstrumentProfile, ...]
    safety_policy: str


class _Accumulator:
    def __init__(self, observation: ProfileObservation):
        self.key = observation.key
        self.official_name = observation.official_name
        self.observations = 0
        self.styles: set[str] = set()
        self.members: set[str] = set()
        self.velocities: list[int] = []
        self.pitches: list[int] = []
        self.durations: list[float] = []
        self.densities: list[float] = []
        self.max_sounding = 0
        self.max_onset = 0
        self.controllers: Counter[int] = Counter()
        self.segment_statuses: Counter[str] = Counter()
        self.measurement_statuses: Counter[str] = Counter()

    def add(self, observation: ProfileObservation) -> None:
        if observation.key != self.key:
            raise ContextualProfileError("attempted to mix different contextual profile keys")
        if observation.official_name != self.official_name:
            raise ContextualProfileError("same profile key has conflicting official names")
        self.observations += 1
        self.styles.add(observation.style_name)
        self.members.add(observation.member_name)
        self.velocities.extend(observation.velocities)
        self.pitches.extend(observation.pitches)
        self.durations.extend(observation.duration_beats)
        if observation.density_per_beat is not None:
            self.densities.append(observation.density_per_beat)
        self.max_sounding = max(self.max_sounding, observation.maximum_sounding_polyphony)
        self.max_onset = max(self.max_onset, observation.maximum_onset_polyphony)
        self.controllers.update(dict(observation.controller_event_counts))
        self.segment_statuses[observation.segment_status] += 1
        self.measurement_statuses[observation.measurement_status] += 1

    def finish(self) -> ContextualInstrumentProfile:
        key_dict = asdict(self.key)
        profile_id = "PROFILE-" + hashlib.sha256(
            json.dumps(key_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20].upper()
        return ContextualInstrumentProfile(
            profile_id=profile_id,
            key=self.key,
            official_name=self.official_name,
            observation_count=self.observations,
            style_count=len(self.styles),
            member_count=len(self.members),
            note_count=len(self.velocities),
            velocity=_distribution(self.velocities),
            pitch=_distribution(self.pitches),
            duration_beats=_distribution(self.durations),
            density_per_beat=_distribution(self.densities),
            maximum_sounding_polyphony=self.max_sounding,
            maximum_onset_polyphony=self.max_onset,
            controller_event_counts=tuple(sorted(self.controllers.items())),
            segment_status_counts=tuple(sorted(self.segment_statuses.items())),
            measurement_status_counts=tuple(sorted(self.measurement_statuses.items())),
            source_members=tuple(sorted(self.members)),
            evidence_status="DERIVED_EMPIRICAL",
            safety_policy="REFERENCE_ONLY_NO_SUGGEST_AUTHORIZATION",
        )


class ContextualProfileBuilder:
    """Build deterministic isolated profile catalogs from immutable observations."""

    def build_from_observations(
        self,
        observations: Iterable[ProfileObservation],
        *,
        source_id: str,
        source_path: str,
        source_sha256: str,
        source_kind: str,
        excluded_identity_counts: Counter[str] | None = None,
    ) -> ContextualProfileCatalog:
        if not source_id or not source_path or len(source_sha256) != 64:
            raise ContextualProfileError("source ID/path/SHA-256 are required")
        accumulators: dict[ProfileKey, _Accumulator] = {}
        count = 0
        for observation in observations:
            if (
                observation.source_id != source_id
                or observation.source_sha256 != source_sha256
                or observation.source_kind != source_kind
                or observation.key.source_kind != source_kind
            ):
                raise ContextualProfileError("observation source provenance mismatch")
            accumulator = accumulators.get(observation.key)
            if accumulator is None:
                accumulator = _Accumulator(observation)
                accumulators[observation.key] = accumulator
            accumulator.add(observation)
            count += 1
        profiles = tuple(
            accumulators[key].finish()
            for key in sorted(accumulators, key=_key_sort)
        )
        return ContextualProfileCatalog(
            schema_version="1.0.0",
            source_id=source_id,
            source_path=source_path,
            source_sha256=source_sha256,
            source_kind=source_kind,
            observation_count=count,
            profile_count=len(profiles),
            excluded_identity_counts=tuple(sorted((excluded_identity_counts or Counter()).items())),
            profiles=profiles,
            safety_policy="FACTORY_EMPIRICAL_REFERENCE_ONLY_NO_SUGGEST_OR_CHANGE",
        )

    def build_factory_archive(self, archive_path: str | Path) -> ContextualProfileCatalog:
        archive = Path(archive_path)
        before = sha256_path(archive)
        loader = StyleWorksLoader()
        resolver = InstrumentIdentityResolver()
        observations: list[ProfileObservation] = []
        excluded: Counter[str] = Counter()

        with ZipFile(archive) as source:
            for info in source.infolist():
                if info.is_dir() or not info.filename.lower().endswith((".mid", ".midi")):
                    continue
                element = loader.load_element_bytes(
                    source.read(info), member_name=info.filename
                )
                event_map = {
                    (event.track_index, event.event_index): event
                    for track in element.midi.tracks
                    for event in track.events
                }
                for track_slice in element.tracks:
                    segmentation = segment_style_track(element, track_slice)
                    identity_result = resolver.resolve(segmentation)
                    identity_by_ordinal = {
                        item.segment_ordinal: item for item in identity_result.identities
                    }
                    for segment in segmentation.segments:
                        identity = identity_by_ordinal[segment.ordinal]
                        if identity.status is not IdentityStatus.FACTORY_CONFIRMED:
                            excluded[identity.status.value] += 1
                            continue
                        if (
                            identity.effective_address is None
                            or identity.factory_entry is None
                            or segment.note_on_count == 0
                            or segment.status is SegmentationStatus.BLOCKED
                            or segment.measurement.status.value == "BLOCKED"
                        ):
                            excluded["UNUSABLE_CONFIRMED_SEGMENT"] += 1
                            continue
                        selected_events = tuple(
                            event_map[ref] for ref in segment.event_refs if ref in event_map
                        )
                        velocities = tuple(
                            event.data[1] for event in selected_events if event.is_note_on
                        )
                        pitches = tuple(
                            event.data[0] for event in selected_events if event.is_note_on
                        )
                        if not velocities:
                            excluded["EMPTY_CONFIRMED_SEGMENT"] += 1
                            continue
                        durations = _closed_duration_beats(
                            selected_events, element.midi.ticks_per_beat
                        )
                        controllers = Counter(
                            event.data[0]
                            for event in selected_events
                            if event.kind == "control_change" and len(event.data) == 2
                        )
                        function = segment.measurement.function.value
                        fixed = (
                            track_slice.role is not None
                            and track_slice.role.startswith("ACC")
                            and element.element in {"INTRO_1", "ENDING_1"}
                        )
                        key = ProfileKey(
                            source_kind=FACTORY_SOURCE_KIND,
                            address=identity.effective_address,
                            item_kind=identity.factory_entry.kind,
                            function=function,
                            element=element.element,
                            cv=track_slice.cv,
                            structural_role=track_slice.role or "UNKNOWN",
                            encoding=segment.measurement.encoding.value,
                            fixed_intro_ending_candidate=fixed,
                        )
                        observations.append(ProfileObservation(
                            source_id="PA800_FACTORY_STYLES",
                            source_sha256=before,
                            source_kind=FACTORY_SOURCE_KIND,
                            member_name=element.member_name,
                            style_name=element.style_name,
                            key=key,
                            official_name=identity.factory_entry.name,
                            segment_status=segment.status.value,
                            measurement_status=segment.measurement.status.value,
                            velocities=velocities,
                            pitches=pitches,
                            duration_beats=durations,
                            density_per_beat=segment.measurement.density_per_beat,
                            maximum_sounding_polyphony=(
                                segment.measurement.maximum_sounding_polyphony
                            ),
                            maximum_onset_polyphony=(
                                segment.measurement.maximum_exact_onset_polyphony
                            ),
                            controller_event_counts=tuple(sorted(controllers.items())),
                        ))

        after = sha256_path(archive)
        if before != after:
            raise ContextualProfileError("Factory archive changed during profile build")
        return self.build_from_observations(
            observations,
            source_id="PA800_FACTORY_STYLES",
            source_path=str(archive),
            source_sha256=before,
            source_kind=FACTORY_SOURCE_KIND,
            excluded_identity_counts=excluded,
        )


def catalog_to_dict(catalog: ContextualProfileCatalog) -> dict:
    return asdict(catalog)


def render_catalog(catalog: ContextualProfileCatalog) -> str:
    return json.dumps(catalog_to_dict(catalog), ensure_ascii=False, indent=2) + "\n"


def catalog_digest(catalog: ContextualProfileCatalog) -> str:
    return hashlib.sha256(render_catalog(catalog).encode("utf-8")).hexdigest()


def _closed_duration_beats(
    events: tuple[MidiEvent, ...], ppq: int | None
) -> tuple[float, ...]:
    if ppq is None:
        return ()
    active: dict[tuple[int, int, int], deque[int]] = defaultdict(deque)
    durations: list[float] = []
    for event in sorted(
        events, key=lambda item: (item.absolute_tick, item.track_index, item.event_index)
    ):
        if event.channel is None or len(event.data) != 2:
            continue
        key = (event.track_index, event.channel, event.data[0])
        if event.is_note_on:
            active[key].append(event.absolute_tick)
        elif event.kind == "note_off" or (
            event.kind == "note_on" and event.data[1] == 0
        ):
            if active[key]:
                durations.append((event.absolute_tick - active[key].popleft()) / ppq)
    return tuple(durations)


def _distribution(values: Iterable[float]) -> DistributionSummary:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return DistributionSummary(0, None, None, None, None, None, None, None, None)
    return DistributionSummary(
        count=len(ordered),
        minimum=ordered[0],
        maximum=ordered[-1],
        mean=sum(ordered) / len(ordered),
        p10=_percentile(ordered, 0.10),
        p25=_percentile(ordered, 0.25),
        median=_percentile(ordered, 0.50),
        p75=_percentile(ordered, 0.75),
        p90=_percentile(ordered, 0.90),
    )


def _percentile(ordered: list[float], quantile: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _key_sort(key: ProfileKey) -> tuple:
    address = tuple(int(part) for part in key.address.split("."))
    return (
        key.source_kind,
        address,
        key.item_kind,
        key.function,
        key.element,
        -1 if key.cv is None else key.cv,
        key.structural_role,
        key.encoding,
        key.fixed_intro_ending_candidate,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    catalog = ContextualProfileBuilder().build_factory_archive(args.archive)
    rendered = render_catalog(catalog)
    if args.json_output:
        if args.json_output.resolve() == args.archive.resolve():
            raise ContextualProfileError("profile output cannot overwrite source archive")
        args.json_output.write_text(rendered, encoding="utf-8")
    else:
        print(json.dumps({
            "source_sha256": catalog.source_sha256,
            "observations": catalog.observation_count,
            "profiles": catalog.profile_count,
            "digest": catalog_digest(catalog),
            "safety_policy": catalog.safety_policy,
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
