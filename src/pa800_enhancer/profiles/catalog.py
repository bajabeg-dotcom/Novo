from dataclasses import dataclass
from pathlib import Path

from .loader import DeviceProfileLoader, ProfileFormatError
from .models import DeviceProfile, DrumKitProfile, SoundProfile


@dataclass(frozen=True, slots=True)
class ProfileCompatibility:
    compatible: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VoiceMatch:
    kind: str
    profile_id: str
    voice_id: str
    display_name: str
    identity_status: str
    voice: SoundProfile | DrumKitProfile


class ProfileCatalog:
    def __init__(self, profiles: tuple[DeviceProfile, ...] = ()) -> None:
        self._profiles: dict[str, DeviceProfile] = {}
        for profile in profiles:
            self.add(profile)

    @property
    def profiles(self) -> tuple[DeviceProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))

    def add(self, profile: DeviceProfile) -> None:
        if profile.profile_id in self._profiles:
            raise ProfileFormatError(f"duplicate profile_id in catalog: {profile.profile_id}")
        self._profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> DeviceProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as error:
            raise KeyError(f"profile not found: {profile_id}") from error

    @classmethod
    def load_directory(cls, directory: Path, loader: DeviceProfileLoader | None = None) -> "ProfileCatalog":
        loader = loader or DeviceProfileLoader()
        catalog = cls()
        for path in sorted(directory.glob("*.json")):
            catalog.add(loader.load(path))
        return catalog

    @staticmethod
    def compatibility(
        profile: DeviceProfile,
        *,
        model: str | None = None,
        os_version: str | None = None,
        musical_resources_version: str | None = None,
    ) -> ProfileCompatibility:
        blockers: list[str] = []
        warnings: list[str] = []
        if model is not None and profile.model != model:
            blockers.append(f"model mismatch: profile={profile.model}, target={model}")
        _compare_version("OS", profile.os_version, os_version, blockers, warnings)
        _compare_version(
            "Musical Resources",
            profile.musical_resources_version,
            musical_resources_version,
            blockers,
            warnings,
        )
        return ProfileCompatibility(not blockers, tuple(blockers), tuple(warnings))

    def match_address(
        self,
        bank_msb: int,
        bank_lsb: int,
        program: int,
        *,
        profile_ids: tuple[str, ...] | None = None,
    ) -> tuple[VoiceMatch, ...]:
        selected = profile_ids or tuple(sorted(self._profiles))
        matches: list[VoiceMatch] = []
        for profile_id in selected:
            profile = self.get(profile_id)
            for kind, voices in (("sound", profile.sounds), ("drum_kit", profile.drum_kits)):
                for voice_id, voice in voices.items():
                    if (voice.bank_msb, voice.bank_lsb, voice.program) != (bank_msb, bank_lsb, program):
                        continue
                    evidence = voice.evidence["identity"]
                    matches.append(
                        VoiceMatch(
                            kind,
                            profile_id,
                            voice_id,
                            voice.display_name,
                            evidence.status,
                            voice,
                        )
                    )
        return tuple(sorted(matches, key=lambda item: (item.profile_id, item.kind, item.voice_id)))


def _compare_version(
    label: str,
    profile_value: str | None,
    target_value: str | None,
    blockers: list[str],
    warnings: list[str],
) -> None:
    if target_value is None:
        if profile_value is not None:
            warnings.append(f"target {label} version is unspecified; profile expects {profile_value}")
        return
    if profile_value is None:
        warnings.append(f"profile does not declare a {label} version for target {target_value}")
    elif profile_value != target_value:
        blockers.append(f"{label} mismatch: profile={profile_value}, target={target_value}")
