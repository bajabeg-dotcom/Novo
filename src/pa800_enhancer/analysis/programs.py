from dataclasses import dataclass

from ..domain.events import EventKind
from ..domain.song import Song
from ..profiles.catalog import ProfileCatalog, ProfileCompatibility, VoiceMatch
from ..profiles.models import DeviceProfile


@dataclass(frozen=True, slots=True)
class ProgramSelection:
    channel: int
    absolute_tick: int
    track_index: int
    bank_msb: int
    bank_lsb: int
    program: int
    event_ids: tuple[str, ...]
    track_indices: tuple[int, ...]
    used_implicit_bank_msb: bool
    used_implicit_bank_lsb: bool

    @property
    def address(self) -> tuple[int, int, int]:
        return self.bank_msb, self.bank_lsb, self.program


@dataclass(frozen=True, slots=True)
class ProgramResolution:
    selection: ProgramSelection
    status: str
    matches: tuple[VoiceMatch, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProgramAnalysis:
    profile_id: str
    compatibility: ProfileCompatibility
    resolutions: tuple[ProgramResolution, ...]


@dataclass(slots=True)
class _BankValue:
    value: int = 0
    event_id: str | None = None
    track_index: int | None = None


@dataclass(slots=True)
class _ChannelBank:
    msb: _BankValue
    lsb: _BankValue


def analyze_programs(
    song: Song,
    profile: DeviceProfile,
    *,
    target_model: str | None = None,
    target_os_version: str | None = None,
    target_musical_resources_version: str | None = None,
    minimum_identity_status: str = "documented",
) -> ProgramAnalysis:
    catalog = ProfileCatalog((profile,))
    compatibility = catalog.compatibility(
        profile,
        model=target_model,
        os_version=target_os_version,
        musical_resources_version=target_musical_resources_version,
    )
    states = {
        channel: _ChannelBank(_BankValue(), _BankValue())
        for channel in range(1, 17)
    }
    resolutions: list[ProgramResolution] = []
    events = sorted(
        (event for track in song.tracks for event in track.events),
        key=lambda event: (event.absolute_tick, event.track_index, event.order),
    )
    for event in events:
        if event.kind is not EventKind.CHANNEL or event.channel is None:
            continue
        state = states[event.channel]
        if event.message_type == 0xB0 and len(event.data) == 2 and event.data[0] in (0, 32):
            target = state.msb if event.data[0] == 0 else state.lsb
            target.value = event.data[1]
            target.event_id = event.event_id
            target.track_index = event.track_index
            continue
        if event.message_type != 0xC0 or len(event.data) != 1:
            continue
        dependency_ids = tuple(
            item for item in (state.msb.event_id, state.lsb.event_id, event.event_id) if item is not None
        )
        tracks = tuple(
            sorted(
                item
                for item in {state.msb.track_index, state.lsb.track_index, event.track_index}
                if item is not None
            )
        )
        selection = ProgramSelection(
            event.channel,
            event.absolute_tick,
            event.track_index,
            state.msb.value,
            state.lsb.value,
            event.data[0],
            dependency_ids,
            tracks,
            state.msb.event_id is None,
            state.lsb.event_id is None,
        )
        matches = catalog.match_address(*selection.address, profile_ids=(profile.profile_id,))
        blockers = list(compatibility.blockers)
        warnings = list(compatibility.warnings)
        if selection.used_implicit_bank_msb or selection.used_implicit_bank_lsb:
            components = []
            if selection.used_implicit_bank_msb:
                components.append("CC0")
            if selection.used_implicit_bank_lsb:
                components.append("CC32")
            warnings.append(f"implicit default bank value used for {' and '.join(components)}")
        if len(tracks) > 1:
            blockers.append("bank selection and Program Change span multiple tracks")
        if not matches:
            status = "unknown"
            blockers.append("address is not present in the selected profile")
        elif len(matches) > 1:
            status = "ambiguous"
            blockers.append("address resolves to more than one profile entry")
        else:
            status = "resolved"
            if not _status_meets(matches[0].identity_status, minimum_identity_status):
                blockers.append(
                    f"identity status {matches[0].identity_status} is below required {minimum_identity_status}"
                )
                status = "insufficient_evidence"
        if blockers and status == "resolved":
            status = "blocked"
        resolutions.append(
            ProgramResolution(selection, status, matches, tuple(blockers), tuple(warnings))
        )
    return ProgramAnalysis(profile.profile_id, compatibility, tuple(resolutions))


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