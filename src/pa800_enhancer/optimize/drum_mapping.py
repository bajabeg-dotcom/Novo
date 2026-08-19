from dataclasses import dataclass

from ..analysis.notes import pair_notes
from ..domain.changes import Change, ChangeGroup, ChangeTransaction, RiskLevel
from ..domain.song import Song
from ..profiles.loader import DeviceProfileLoader
from ..profiles.models import DeviceProfile
from .engine import ChangeEngine, song_revision
from .sound_mapping import SoundMappingRequest, plan_sound_mapping


@dataclass(frozen=True, slots=True)
class DrumMappingRequest:
    program_event_id: str
    target_kit_id: str
    source_note: int
    target_note: int


@dataclass(frozen=True, slots=True)
class DrumMappingUpdate:
    role: str
    event_id: str
    old_value: int
    new_value: int


@dataclass(frozen=True, slots=True)
class DrumMappingPlan:
    status: str
    source_revision: str
    profile_id: str
    profile_sha256: str
    request: DrumMappingRequest
    target_kit_name: str | None
    target_drum_name: str | None
    interval_start_tick: int | None
    interval_end_tick: int | None
    mapped_note_count: int
    updates: tuple[DrumMappingUpdate, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DrumMappingPreview:
    original_revision: str
    projected_revision: str
    original_event_count: int
    projected_event_count: int
    mapped_note_count: int
    updates: tuple[DrumMappingUpdate, ...]


def plan_drum_mapping(
    song: Song,
    profile: DeviceProfile,
    request: DrumMappingRequest,
    *,
    minimum_identity_status: str = "hardware_confirmed",
    target_model: str | None = None,
    target_os_version: str | None = None,
    target_musical_resources_version: str | None = None,
) -> DrumMappingPlan:
    _midi_note(request.source_note, "source_note")
    _midi_note(request.target_note, "target_note")
    blockers: list[str] = []
    warnings: list[str] = []
    revision = song_revision(song)
    profile_digest = DeviceProfileLoader().digest(profile)

    kit = profile.drum_kits.get(request.target_kit_id)
    target_drum = kit.notes.get(request.target_note) if kit is not None else None
    if kit is None:
        blockers.append(f"target drum kit is not present in profile: {request.target_kit_id}")
        kit_name = None
        drum_name = None
    else:
        kit_name = kit.display_name
        if target_drum is None:
            blockers.append(
                f"target note {request.target_note} is not mapped in kit {request.target_kit_id}"
            )
            drum_name = None
        else:
            drum_name = target_drum.display_name
            status = target_drum.evidence["identity"].status
            if not _status_meets(status, minimum_identity_status):
                blockers.append(
                    f"target drum-note identity status {status} is below required "
                    f"{minimum_identity_status}"
                )

    sound_plan = plan_sound_mapping(
        song,
        profile,
        SoundMappingRequest(request.program_event_id, request.target_kit_id),
        minimum_identity_status=minimum_identity_status,
        target_model=target_model,
        target_os_version=target_os_version,
        target_musical_resources_version=target_musical_resources_version,
    )
    blockers.extend(sound_plan.blockers)
    warnings.extend(sound_plan.warnings)
    if sound_plan.channel is not None and sound_plan.channel != 10:
        blockers.append("drum-note mapping requires MIDI channel 10")

    program_event = next(
        (
            event
            for track in song.tracks
            for event in track.events
            if event.event_id == request.program_event_id
        ),
        None,
    )
    interval_start = program_event.absolute_tick if program_event is not None else None
    interval_end = None
    if interval_start is not None:
        later_programs = sorted(
            event.absolute_tick
            for track in song.tracks
            for event in track.events
            if event.channel == 10
            and event.message_type == 0xC0
            and event.absolute_tick > interval_start
        )
        interval_end = later_programs[0] if later_programs else song.end_tick + 1

    notes, unmatched = pair_notes(song)
    selected_notes = []
    if interval_start is not None and interval_end is not None:
        event_map = {
            event.event_id: event for track in song.tracks for event in track.events
        }
        program_track = program_event.track_index
        interval_source_notes = [
            note
            for note in notes
            if note.channel == 10
            and note.note == request.source_note
            and interval_start <= note.start_tick < interval_end
        ]
        selected_notes = [
            note
            for note in interval_source_notes
            if event_map[note.on_event_id].track_index == program_track
        ]
        if len(selected_notes) != len(interval_source_notes):
            blockers.append("source drum note spans more than one MIDI track")
        cross_track_pairs = [
            note
            for note in selected_notes
            if event_map[note.off_event_id].track_index != program_track
        ]
        if cross_track_pairs:
            blockers.append("source drum Note On/Off pair spans multiple tracks")
        ambiguous = [note for note in selected_notes if note.ambiguous_pairing]
        if ambiguous:
            blockers.append("source drum note has ambiguous overlapping Note On events")
        crossing = [note for note in selected_notes if note.end_tick >= interval_end]
        if crossing:
            blockers.append("source drum note crosses the next Program Change boundary")
        relevant_unmatched = [
            event
            for event in unmatched
            if event.channel == 10
            and len(event.data) >= 1
            and event.data[0] == request.source_note
            and interval_start <= event.absolute_tick < interval_end
        ]
        if relevant_unmatched:
            blockers.append("source drum note contains unmatched Note On/Off events")
        if request.source_note != request.target_note:
            target_conflicts = [
                note
                for note in notes
                if note.channel == 10
                and note.note == request.target_note
                and interval_start <= note.start_tick < interval_end
            ]
            if target_conflicts:
                blockers.append(
                    "target drum note already occurs in the selected kit interval"
                )

    updates = [
        DrumMappingUpdate(item.role, item.event_id, item.old_value, item.new_value)
        for item in sound_plan.updates
    ]
    if not blockers and request.source_note != request.target_note:
        for note in selected_notes:
            updates.extend(
                (
                    DrumMappingUpdate(
                        "note_on", note.on_event_id, request.source_note, request.target_note
                    ),
                    DrumMappingUpdate(
                        "note_off", note.off_event_id, request.source_note, request.target_note
                    ),
                )
            )
    if blockers:
        status = "blocked"
    elif not updates:
        status = "no_changes"
        warnings.append("no drum-kit address or note-number changes are required")
    else:
        status = "ready"
        if not selected_notes:
            warnings.append("source drum note does not occur in the selected kit interval")
    return DrumMappingPlan(
        status=status,
        source_revision=revision,
        profile_id=profile.profile_id,
        profile_sha256=profile_digest,
        request=request,
        target_kit_name=kit_name,
        target_drum_name=drum_name,
        interval_start_tick=interval_start,
        interval_end_tick=interval_end,
        mapped_note_count=len(selected_notes),
        updates=tuple(updates),
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def preview_drum_mapping(
    song: Song, profile: DeviceProfile, plan: DrumMappingPlan
) -> DrumMappingPreview:
    transaction = _build_transaction(song, profile, plan)
    projected = ChangeEngine().apply(song, transaction)
    return DrumMappingPreview(
        original_revision=song_revision(song),
        projected_revision=song_revision(projected),
        original_event_count=song.event_count,
        projected_event_count=projected.event_count,
        mapped_note_count=plan.mapped_note_count,
        updates=plan.updates,
    )


def build_drum_mapping_transaction(
    song: Song,
    profile: DeviceProfile,
    plan: DrumMappingPlan,
    *,
    approved: bool = False,
) -> ChangeTransaction:
    if not approved:
        raise PermissionError("drum mapping requires explicit approval")
    return _build_transaction(song, profile, plan)


def _build_transaction(
    song: Song, profile: DeviceProfile, plan: DrumMappingPlan
) -> ChangeTransaction:
    if plan.status != "ready" or plan.blockers or not plan.updates:
        raise ValueError("blocked or empty drum mapping plan cannot be applied")
    if song_revision(song) != plan.source_revision:
        raise ValueError("drum mapping preview is stale; analyze the current song again")
    if DeviceProfileLoader().digest(profile) != plan.profile_sha256:
        raise ValueError("drum mapping profile changed after preview")
    refreshed = plan_drum_mapping(
        song,
        profile,
        plan.request,
        minimum_identity_status="hypothesis",
    )
    if (
        refreshed.updates != plan.updates
        or refreshed.mapped_note_count != plan.mapped_note_count
        or refreshed.profile_sha256 != plan.profile_sha256
    ):
        raise ValueError("drum mapping preview no longer matches the current inputs")
    changes = tuple(
        Change(
            change_id=f"drum-mapping:{update.event_id}",
            module="drum_mapping",
            reason=f"map to {plan.target_kit_name}: {plan.target_drum_name} ({update.role})",
            risk=RiskLevel.HIGH,
            event_id=update.event_id,
            field=(
                "program"
                if update.role == "program"
                else "controller_value"
                if update.role in ("bank_msb", "bank_lsb")
                else "note_number"
            ),
            old_value=update.old_value,
            new_value=update.new_value,
            approved=True,
        )
        for update in plan.updates
    )
    return ChangeTransaction(
        transaction_id=f"drum-mapping:{plan.request.program_event_id}:{plan.request.source_note}",
        groups=(
            ChangeGroup(
                group_id=(
                    f"drum-mapping:{plan.request.program_event_id}:"
                    f"{plan.request.source_note}"
                ),
                changes=changes,
                reason="atomically update drum-kit address and paired drum note events",
            ),
        ),
        module="drum_mapping",
        reason="explicitly approved Pa800 per-note drum mapping",
        base_revision=plan.source_revision,
    )


def _midi_note(value: int, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 127:
        raise ValueError(f"{label} must be an integer in range 0--127")


def _status_meets(actual: str, required: str) -> bool:
    levels = {
        "hypothesis": 0,
        "documented": 1,
        "software_verified": 2,
        "hardware_confirmed": 3,
    }
    if required not in levels:
        raise ValueError(f"unknown minimum identity status: {required}")
    return levels.get(actual, -1) >= levels[required]