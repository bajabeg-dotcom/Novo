from dataclasses import dataclass

from ..analysis.programs import ProgramSelection, analyze_programs
from ..domain.changes import Change, ChangeGroup, ChangeTransaction, RiskLevel
from ..domain.events import EventKind
from ..domain.song import Song
from ..profiles.catalog import ProfileCatalog
from ..profiles.loader import DeviceProfileLoader
from ..profiles.models import DeviceProfile, DrumKitProfile, SoundProfile
from .engine import ChangeEngine, song_revision


@dataclass(frozen=True, slots=True)
class SoundMappingRequest:
    program_event_id: str
    target_voice_id: str


@dataclass(frozen=True, slots=True)
class SoundMappingUpdate:
    role: str
    event_id: str
    old_value: int
    new_value: int


@dataclass(frozen=True, slots=True)
class SoundMappingPlan:
    status: str
    source_revision: str
    profile_id: str
    profile_sha256: str
    request: SoundMappingRequest
    channel: int | None
    source_address: tuple[int, int, int] | None
    target_kind: str | None
    target_display_name: str | None
    target_address: tuple[int, int, int] | None
    identity_status: str | None
    updates: tuple[SoundMappingUpdate, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SoundMappingPreview:
    original_revision: str
    projected_revision: str
    original_event_count: int
    projected_event_count: int
    updates: tuple[SoundMappingUpdate, ...]


def plan_sound_mapping(
    song: Song,
    profile: DeviceProfile,
    request: SoundMappingRequest,
    *,
    minimum_identity_status: str = "hardware_confirmed",
    target_model: str | None = None,
    target_os_version: str | None = None,
    target_musical_resources_version: str | None = None,
) -> SoundMappingPlan:
    blockers: list[str] = []
    warnings: list[str] = []
    revision = song_revision(song)
    profile_digest = DeviceProfileLoader().digest(profile)
    compatibility = ProfileCatalog.compatibility(
        profile,
        model=target_model,
        os_version=target_os_version,
        musical_resources_version=target_musical_resources_version,
    )
    blockers.extend(compatibility.blockers)
    warnings.extend(compatibility.warnings)

    target_kind, target = _find_target(profile, request.target_voice_id)
    if target is None:
        blockers.append(f"target voice is not present in profile: {request.target_voice_id}")
        target_address = None
        identity_status = None
        target_name = None
    else:
        target_address = (target.bank_msb, target.bank_lsb, target.program)
        target_name = target.display_name
        identity_status = target.evidence["identity"].status
        if not _status_meets(identity_status, minimum_identity_status):
            blockers.append(
                f"target identity status {identity_status} is below required "
                f"{minimum_identity_status}"
            )

    analysis = analyze_programs(song, profile, minimum_identity_status="hypothesis")
    selected = [
        item.selection
        for item in analysis.resolutions
        if request.program_event_id in item.selection.event_ids
        and item.selection.event_ids[-1] == request.program_event_id
    ]
    selection = selected[0] if len(selected) == 1 else None
    if not selected:
        blockers.append(
            f"Program Change event is not present in the song: {request.program_event_id}"
        )
    elif len(selected) > 1:
        blockers.append(f"Program Change event is ambiguous: {request.program_event_id}")

    updates: list[SoundMappingUpdate] = []
    if selection is not None:
        if selection.used_implicit_bank_msb or selection.used_implicit_bank_lsb:
            blockers.append("sound mapping requires explicit CC0 and CC32 events")
        if len(selection.track_indices) != 1:
            blockers.append("CC0, CC32 and Program Change must be in one track")
        if target_kind == "sound" and selection.channel == 10:
            blockers.append("channel 10 requires a drum-kit target")
        if target_kind == "drum_kit" and selection.channel != 10:
            blockers.append("drum-kit mapping is restricted to channel 10")
        if target_address is not None:
            updates.extend(
                _mapping_updates(song, selection, target_address, analysis, blockers)
            )

    if blockers:
        status = "blocked"
    elif not updates:
        status = "no_changes"
        warnings.append("selected Program Change already uses the requested address")
    else:
        status = "ready"
    return SoundMappingPlan(
        status=status,
        source_revision=revision,
        profile_id=profile.profile_id,
        profile_sha256=profile_digest,
        request=request,
        channel=selection.channel if selection else None,
        source_address=selection.address if selection else None,
        target_kind=target_kind,
        target_display_name=target_name,
        target_address=target_address,
        identity_status=identity_status,
        updates=tuple(updates),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )


def preview_sound_mapping(
    song: Song, profile: DeviceProfile, plan: SoundMappingPlan
) -> SoundMappingPreview:
    transaction = _build_transaction(song, profile, plan)
    projected = ChangeEngine().apply(song, transaction)
    return SoundMappingPreview(
        original_revision=song_revision(song),
        projected_revision=song_revision(projected),
        original_event_count=song.event_count,
        projected_event_count=projected.event_count,
        updates=plan.updates,
    )


def build_sound_mapping_transaction(
    song: Song,
    profile: DeviceProfile,
    plan: SoundMappingPlan,
    *,
    approved: bool = False,
) -> ChangeTransaction:
    if not approved:
        raise PermissionError("sound mapping requires explicit approval")
    return _build_transaction(song, profile, plan)


def _build_transaction(
    song: Song, profile: DeviceProfile, plan: SoundMappingPlan
) -> ChangeTransaction:
    if plan.status != "ready" or plan.blockers or not plan.updates:
        raise ValueError("blocked or empty sound mapping plan cannot be applied")
    if song_revision(song) != plan.source_revision:
        raise ValueError("sound mapping preview is stale; analyze the current song again")
    if DeviceProfileLoader().digest(profile) != plan.profile_sha256:
        raise ValueError("sound mapping profile changed after preview")
    refreshed = plan_sound_mapping(
        song,
        profile,
        plan.request,
        minimum_identity_status=plan.identity_status or "hardware_confirmed",
    )
    if (
        refreshed.status != plan.status
        or refreshed.updates != plan.updates
        or refreshed.target_address != plan.target_address
        or refreshed.profile_sha256 != plan.profile_sha256
    ):
        raise ValueError("sound mapping preview no longer matches the current inputs")
    changes = tuple(
        Change(
            change_id=f"sound-mapping:{update.event_id}",
            module="sound_mapping",
            reason=f"map to {plan.target_display_name} ({update.role})",
            risk=RiskLevel.HIGH,
            event_id=update.event_id,
            field="program" if update.role == "program" else "controller_value",
            old_value=update.old_value,
            new_value=update.new_value,
            approved=True,
        )
        for update in plan.updates
    )
    group = ChangeGroup(
        group_id=f"sound-mapping:{plan.request.program_event_id}",
        changes=changes,
        reason="atomically update the linked CC0/CC32/Program Change address",
    )
    return ChangeTransaction(
        transaction_id=f"sound-mapping:{plan.request.program_event_id}",
        groups=(group,),
        module="sound_mapping",
        reason="explicitly approved Pa800 sound mapping",
        base_revision=plan.source_revision,
    )


def _find_target(
    profile: DeviceProfile, voice_id: str
) -> tuple[str | None, SoundProfile | DrumKitProfile | None]:
    sound = profile.sounds.get(voice_id)
    drum = profile.drum_kits.get(voice_id)
    if sound is not None and drum is not None:
        return None, None
    if sound is not None:
        return "sound", sound
    if drum is not None:
        return "drum_kit", drum
    return None, None


def _mapping_updates(
    song: Song,
    selection: ProgramSelection,
    target_address: tuple[int, int, int],
    analysis,
    blockers: list[str],
) -> list[SoundMappingUpdate]:
    event_map = {
        event.event_id: event for track in song.tracks for event in track.events
    }
    events = [event_map[event_id] for event_id in selection.event_ids]
    roles = {}
    for event in events:
        if event.kind is not EventKind.CHANNEL:
            continue
        if event.message_type == 0xB0 and event.data[0] == 0:
            roles["bank_msb"] = event
        elif event.message_type == 0xB0 and event.data[0] == 32:
            roles["bank_lsb"] = event
        elif event.message_type == 0xC0:
            roles["program"] = event
    if set(roles) != {"bank_msb", "bank_lsb", "program"}:
        blockers.append("linked CC0/CC32/Program Change events are incomplete")
        return []

    dependency_counts: dict[str, int] = {}
    for resolution in analysis.resolutions:
        for event_id in resolution.selection.event_ids[:-1]:
            dependency_counts[event_id] = dependency_counts.get(event_id, 0) + 1
    target_values = dict(zip(("bank_msb", "bank_lsb", "program"), target_address))
    updates = []
    for role in ("bank_msb", "bank_lsb", "program"):
        event = roles[role]
        old_value = event.data[0] if role == "program" else event.data[1]
        new_value = target_values[role]
        if old_value == new_value:
            continue
        if role != "program" and dependency_counts.get(event.event_id, 0) > 1:
            blockers.append(
                f"{role} event {event.event_id} is shared by multiple Program Change selections"
            )
            continue
        updates.append(SoundMappingUpdate(role, event.event_id, old_value, new_value))
    return updates


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