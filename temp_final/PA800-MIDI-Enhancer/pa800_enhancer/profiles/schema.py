from .models import PROFILE_SCHEMA_VERSION


# Public, dependency-free description used by editors and future UI forms.
DEVICE_PROFILE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://pa800-enhancer.invalid/schema/device-profile-v1.json",
    "title": "Pa800 Enhancer device profile",
    "type": "object",
    "required": [
        "schema_version",
        "profile_version",
        "profile_id",
        "model",
        "sources",
        "sounds",
        "drum_kits",
    ],
    "properties": {
        "schema_version": {"const": PROFILE_SCHEMA_VERSION},
        "profile_version": {"type": "string", "minLength": 1},
        "profile_id": {"type": "string", "minLength": 1},
        "model": {"type": "string", "minLength": 1},
        "os_version": {"type": ["string", "null"]},
        "musical_resources_version": {"type": ["string", "null"]},
        "sources": {"type": "array"},
        "sounds": {"type": "array"},
        "drum_kits": {"type": "array"},
        "rhythms": {"type": "array"},
        "evidence": {"type": "object"},
        "extensions": {"type": "object"},
    },
    "additionalProperties": False,
}