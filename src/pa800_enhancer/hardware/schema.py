from .models import HARDWARE_TEST_SCHEMA_VERSION


HARDWARE_TEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://pa800-enhancer.invalid/schema/hardware-test-v1.json",
    "title": "Pa800 two-cycle hardware test",
    "type": "object",
    "required": [
        "schema_version",
        "case_version",
        "case_id",
        "title",
        "fixture",
        "device",
        "assertions",
        "cycles",
    ],
    "properties": {
        "schema_version": {"const": HARDWARE_TEST_SCHEMA_VERSION},
        "case_version": {"type": "string", "minLength": 1},
        "case_id": {"type": "string", "minLength": 1},
        "title": {"type": "string", "minLength": 1},
        "fixture": {"type": "object"},
        "device": {"type": "object"},
        "assertions": {"type": "array", "minItems": 1},
        "cycles": {"type": "array", "minItems": 2, "maxItems": 2},
        "extensions": {"type": "object"},
    },
    "additionalProperties": False,
}