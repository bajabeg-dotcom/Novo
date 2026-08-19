from .builtin_rhythms import RHYTHM_PROFILES
from .catalog import ProfileCatalog, ProfileCompatibility, VoiceMatch
from .loader import DeviceProfileLoader, ProfileFormatError
from .models import (
    PROFILE_SCHEMA_VERSION,
    DeviceProfile,
    DrumKitProfile,
    DrumNoteProfile,
    Evidence,
    ProfileSource,
    RhythmProfile,
    SoundProfile,
)
from .schema import DEVICE_PROFILE_SCHEMA
from .hardware_promotion import HardwarePromotion, promote_hardware_case

__all__ = [
    "DEVICE_PROFILE_SCHEMA",
    "PROFILE_SCHEMA_VERSION",
    "DeviceProfile",
    "DeviceProfileLoader",
    "DrumKitProfile",
    "DrumNoteProfile",
    "Evidence",
    "HardwarePromotion",
    "ProfileFormatError",
    "ProfileCatalog",
    "ProfileCompatibility",
    "ProfileSource",
    "RHYTHM_PROFILES",
    "RhythmProfile",
    "SoundProfile",
    "VoiceMatch",
    "promote_hardware_case",
]