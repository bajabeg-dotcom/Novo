from copy import deepcopy
from dataclasses import dataclass

from ..hardware.loader import HardwareTestLoader
from ..hardware.models import HardwareAssertion, HardwareTestCase
from .loader import DeviceProfileLoader, ProfileFormatError
from .models import (
    DeviceProfile,
    DrumKitProfile,
    DrumNoteProfile,
    Evidence,
    ProfileSource,
    SoundProfile,
)


@dataclass(frozen=True, slots=True)
class HardwarePromotion:
    profile: DeviceProfile
    assertion_id: str
    promoted_kind: str
    voice_id: str
    address: tuple[int, int, int]
    evidence_source_id: str
    hardware_manifest_sha256: str


def promote_hardware_case(
    profile: DeviceProfile,
    case: HardwareTestCase,
    *,
    voice_id: str,
    new_profile_id: str,
    new_profile_version: str,
    assertion_id: str | None = None,
    source_locator: str = "",
) -> HardwarePromotion:
    if case.status != "passed":
        raise ValueError("hardware promotion requires a passed two-cycle test case")
    _text(voice_id, "voice_id")
    _text(new_profile_id, "new_profile_id")
    _text(new_profile_version, "new_profile_version")
    if (
        new_profile_id == profile.profile_id
        and new_profile_version == profile.profile_version
    ):
        raise ValueError("hardware promotion requires a new profile identity or version")
    assertion = _select_assertion(case, assertion_id)
    expected = assertion.expected
    address = (
        _midi(expected.get("bank_msb"), "bank_msb"),
        _midi(expected.get("bank_lsb"), "bank_lsb"),
        _midi(expected.get("program"), "program"),
    )
    _require_compatible_identity(profile, case)

    manifest_digest = HardwareTestLoader().digest(case)
    source_id = f"hardware:{case.case_id}:{case.case_version}"
    tested_at = max(cycle.tested_at for cycle in case.cycles if cycle.tested_at)
    source = ProfileSource(
        source_id=source_id,
        kind="device_test",
        title=f"{case.title} ({case.case_id} v{case.case_version})",
        locator=source_locator,
        captured_at=tested_at,
        sha256=manifest_digest,
        notes="Passed two complete import-export-Pa800 cycles.",
    )
    evidence = Evidence(
        source_ids=(source_id,),
        status="hardware_confirmed",
        tested_os_version=case.device.os_version,
        tested_at=tested_at,
        test_reference=f"{case.case_id}@{case.case_version}:{assertion.assertion_id}",
        notes="Promoted only after every assertion passed in both hardware cycles.",
    )

    promoted = deepcopy(profile)
    promoted.profile_id = new_profile_id
    promoted.profile_version = new_profile_version
    promoted.model = case.device.model
    promoted.os_version = case.device.os_version
    promoted.musical_resources_version = case.device.musical_resources_version
    existing_source = promoted.sources.get(source_id)
    if existing_source is not None and existing_source.sha256 != manifest_digest:
        raise ValueError(
            "hardware case identity/version already exists with a different manifest hash"
        )
    promoted.sources[source_id] = source
    extensions = dict(promoted.extensions)
    extensions.pop("status", None)
    extensions.pop("warning", None)
    extensions["derived_from_profile"] = {
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
    }
    raw_references = extensions.get("hardware_test_references", [])
    if not isinstance(raw_references, (list, tuple)):
        raise ValueError("hardware_test_references extension must be an array")
    references = list(raw_references)
    reference = f"{case.case_id}@{case.case_version}"
    if reference not in references:
        references.append(reference)
    extensions["hardware_test_references"] = sorted(references)
    promoted.extensions = extensions

    if assertion.kind == "sound_identity":
        display_name = _text(expected.get("display_name"), "display_name")
        existing = promoted.sounds.get(voice_id)
        if existing is not None and (
            existing.bank_msb,
            existing.bank_lsb,
            existing.program,
            existing.display_name,
        ) != (*address, display_name):
            raise ValueError(f"existing sound {voice_id} conflicts with hardware assertion")
        promoted.sounds[voice_id] = SoundProfile(
            sound_id=voice_id,
            display_name=display_name,
            bank_msb=address[0],
            bank_lsb=address[1],
            program=address[2],
            family=existing.family if existing else "unknown",
            note_range=existing.note_range if existing else None,
            mode=existing.mode if existing else "unknown",
            evidence={**(existing.evidence if existing else {}), "identity": evidence},
            extensions=dict(existing.extensions) if existing else {},
        )
        promoted_kind = "sound"
    else:
        kit_name = _text(expected.get("kit_name"), "kit_name")
        note_number = _midi(expected.get("note"), "note")
        note_name = _text(expected.get("note_name"), "note_name")
        existing_kit = promoted.drum_kits.get(voice_id)
        if existing_kit is not None and (
            existing_kit.bank_msb,
            existing_kit.bank_lsb,
            existing_kit.program,
            existing_kit.display_name,
        ) != (*address, kit_name):
            raise ValueError(f"existing drum kit {voice_id} conflicts with hardware assertion")
        notes = dict(existing_kit.notes) if existing_kit else {}
        existing_note = notes.get(note_number)
        if existing_note is not None and existing_note.display_name != note_name:
            raise ValueError(
                f"existing drum note {note_number} conflicts with hardware assertion"
            )
        velocity = expected.get("velocity")
        velocity_note = (
            f" Identity observed at velocity {_midi(velocity, 'velocity')}."
            if velocity is not None
            else ""
        )
        note_evidence = Evidence(
            source_ids=evidence.source_ids,
            status=evidence.status,
            tested_os_version=evidence.tested_os_version,
            tested_at=evidence.tested_at,
            test_reference=evidence.test_reference,
            notes=evidence.notes + velocity_note,
        )
        notes[note_number] = DrumNoteProfile(
            note=note_number,
            display_name=note_name,
            family=existing_note.family if existing_note else "unknown",
            velocity_layers=existing_note.velocity_layers if existing_note else (),
            choke_group=existing_note.choke_group if existing_note else None,
            evidence={
                **(existing_note.evidence if existing_note else {}),
                "identity": note_evidence,
            },
            extensions=dict(existing_note.extensions) if existing_note else {},
        )
        promoted.drum_kits[voice_id] = DrumKitProfile(
            kit_id=voice_id,
            display_name=kit_name,
            bank_msb=address[0],
            bank_lsb=address[1],
            program=address[2],
            notes=notes,
            evidence={
                **(existing_kit.evidence if existing_kit else {}),
                "identity": evidence,
            },
            extensions=dict(existing_kit.extensions) if existing_kit else {},
        )
        promoted_kind = "drum_kit"

    loader = DeviceProfileLoader()
    try:
        validated = loader.loads(loader.dumps(promoted))
    except ProfileFormatError as error:
        raise ValueError(f"promoted profile is invalid: {error}") from error
    return HardwarePromotion(
        profile=validated,
        assertion_id=assertion.assertion_id,
        promoted_kind=promoted_kind,
        voice_id=voice_id,
        address=address,
        evidence_source_id=source_id,
        hardware_manifest_sha256=manifest_digest,
    )


def _select_assertion(
    case: HardwareTestCase, assertion_id: str | None
) -> HardwareAssertion:
    supported = [
        assertion
        for assertion in case.assertions
        if assertion.kind in {"sound_identity", "drum_note"}
    ]
    if assertion_id is not None:
        supported = [item for item in supported if item.assertion_id == assertion_id]
        if not supported:
            raise ValueError(f"supported hardware assertion not found: {assertion_id}")
    if len(supported) != 1:
        raise ValueError(
            "hardware promotion requires exactly one sound_identity or drum_note assertion; "
            "select one explicitly"
        )
    return supported[0]


def _require_compatible_identity(profile: DeviceProfile, case: HardwareTestCase) -> None:
    if profile.model != case.device.model:
        raise ValueError(
            f"device model mismatch: profile={profile.model}, test={case.device.model}"
        )
    if profile.os_version is not None and profile.os_version != case.device.os_version:
        raise ValueError(
            f"OS mismatch: profile={profile.os_version}, test={case.device.os_version}"
        )
    if (
        profile.musical_resources_version is not None
        and profile.musical_resources_version != case.device.musical_resources_version
    ):
        raise ValueError(
            "Musical Resources mismatch: "
            f"profile={profile.musical_resources_version}, "
            f"test={case.device.musical_resources_version}"
        )


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"hardware assertion {field} must be a non-empty string")
    return value


def _midi(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 127:
        raise ValueError(f"hardware assertion {field} must be in range 0--127")
    return value
