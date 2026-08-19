import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

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


SOURCE_KINDS = {
    "official_manual",
    "official_table",
    "device_test",
    "user_capture",
    "community_report",
    "derived",
}
EVIDENCE_STATUSES = {"hypothesis", "documented", "software_verified", "hardware_confirmed"}
SOUND_MODES = {"unknown", "poly", "mono"}
TOP_LEVEL_KEYS = {
    "schema_version",
    "profile_version",
    "profile_id",
    "model",
    "os_version",
    "musical_resources_version",
    "sources",
    "sounds",
    "drum_kits",
    "rhythms",
    "evidence",
    "extensions",
}


class ProfileFormatError(ValueError):
    pass


class DeviceProfileLoader:
    def load(self, path: Path) -> DeviceProfile:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise ProfileFormatError(f"cannot read profile {path}: {error}") from error
        return self.loads(text)

    def loads(self, text: str) -> DeviceProfile:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise ProfileFormatError(f"invalid profile JSON: {error}") from error
        return self.from_data(data)

    def from_data(self, data: object) -> DeviceProfile:
        root = self._object(data, "profile root")
        unknown = set(root) - TOP_LEVEL_KEYS
        if unknown:
            raise ProfileFormatError(f"unknown top-level fields: {', '.join(sorted(unknown))}")
        version = self._integer(root.get("schema_version"), "schema_version")
        if version != PROFILE_SCHEMA_VERSION:
            relation = "newer" if version > PROFILE_SCHEMA_VERSION else "older"
            raise ProfileFormatError(
                f"profile schema {version} is {relation} than supported schema {PROFILE_SCHEMA_VERSION}"
            )

        sources = self._sources(root.get("sources", []))
        evidence = self._evidence_map(root.get("evidence", {}), sources, "evidence")
        sounds = self._sounds(root.get("sounds", []), sources)
        drum_kits = self._drum_kits(root.get("drum_kits", []), sources)
        rhythms = self._rhythms(root.get("rhythms", []))
        profile = DeviceProfile(
            profile_id=self._text(root.get("profile_id"), "profile_id"),
            model=self._text(root.get("model"), "model"),
            os_version=self._optional_text(root.get("os_version"), "os_version"),
            profile_version=self._text(root.get("profile_version"), "profile_version"),
            schema_version=version,
            musical_resources_version=self._optional_text(
                root.get("musical_resources_version"), "musical_resources_version"
            ),
            sources=sources,
            sounds=sounds,
            drum_kits=drum_kits,
            rhythm_profiles=rhythms,
            evidence=evidence,
            extensions=self._object(root.get("extensions", {}), "extensions"),
        )
        self._validate_unique_voice_addresses(profile)
        return profile

    def dumps(self, profile: DeviceProfile, *, indent: int = 2) -> str:
        return json.dumps(self.to_data(profile), indent=indent, ensure_ascii=False, sort_keys=True) + "\n"

    def dump(self, profile: DeviceProfile, path: Path) -> None:
        path.write_text(self.dumps(profile), encoding="utf-8")

    def digest(self, profile: DeviceProfile) -> str:
        canonical = json.dumps(
            self.to_data(profile), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def to_data(self, profile: DeviceProfile) -> dict[str, object]:
        def evidence_map(value: dict[str, Evidence]) -> dict[str, object]:
            return {key: asdict(item) for key, item in sorted(value.items())}

        sounds = []
        for item in sorted(profile.sounds.values(), key=lambda value: value.sound_id):
            row = asdict(item)
            row["note_range"] = list(item.note_range) if item.note_range else None
            row["evidence"] = evidence_map(item.evidence)
            sounds.append(row)
        kits = []
        for item in sorted(profile.drum_kits.values(), key=lambda value: value.kit_id):
            row = asdict(item)
            row["evidence"] = evidence_map(item.evidence)
            row["notes"] = []
            for note in sorted(item.notes.values(), key=lambda value: value.note):
                note_row = asdict(note)
                note_row["velocity_layers"] = [list(layer) for layer in note.velocity_layers]
                note_row["evidence"] = evidence_map(note.evidence)
                row["notes"].append(note_row)
            kits.append(row)
        rhythms = []
        for item in sorted(profile.rhythm_profiles.values(), key=lambda value: value.profile_id):
            row = asdict(item)
            row["meters"] = [list(meter) for meter in item.meters]
            rhythms.append(row)
        return {
            "schema_version": profile.schema_version,
            "profile_version": profile.profile_version,
            "profile_id": profile.profile_id,
            "model": profile.model,
            "os_version": profile.os_version,
            "musical_resources_version": profile.musical_resources_version,
            "sources": [asdict(item) for item in sorted(profile.sources.values(), key=lambda value: value.source_id)],
            "sounds": sounds,
            "drum_kits": kits,
            "rhythms": rhythms,
            "evidence": evidence_map(profile.evidence),
            "extensions": profile.extensions,
        }

    def _sources(self, value: object) -> dict[str, ProfileSource]:
        result: dict[str, ProfileSource] = {}
        for index, raw in enumerate(self._array(value, "sources")):
            item = self._object(raw, f"sources[{index}]")
            source_id = self._text(item.get("source_id"), f"sources[{index}].source_id")
            kind = self._text(item.get("kind"), f"sources[{index}].kind")
            if kind not in SOURCE_KINDS:
                raise ProfileFormatError(f"sources[{index}].kind is not recognized: {kind}")
            if source_id in result:
                raise ProfileFormatError(f"duplicate source_id: {source_id}")
            sha256 = self._optional_text(item.get("sha256"), f"sources[{index}].sha256")
            if sha256 is not None and (len(sha256) != 64 or any(char not in "0123456789abcdefABCDEF" for char in sha256)):
                raise ProfileFormatError(f"sources[{index}].sha256 must contain 64 hexadecimal characters")
            result[source_id] = ProfileSource(
                source_id=source_id,
                kind=kind,
                title=self._text(item.get("title"), f"sources[{index}].title"),
                locator=self._optional_text(item.get("locator"), f"sources[{index}].locator") or "",
                captured_at=self._optional_text(item.get("captured_at"), f"sources[{index}].captured_at"),
                sha256=sha256.lower() if sha256 else None,
                notes=self._optional_text(item.get("notes"), f"sources[{index}].notes") or "",
            )
        return result

    def _evidence_map(self, value: object, sources: dict[str, ProfileSource], path: str) -> dict[str, Evidence]:
        raw_map = self._object(value, path)
        result: dict[str, Evidence] = {}
        for field_name, raw in raw_map.items():
            item = self._object(raw, f"{path}.{field_name}")
            source_ids = tuple(self._text(entry, f"{path}.{field_name}.source_ids") for entry in self._array(item.get("source_ids"), f"{path}.{field_name}.source_ids"))
            if not source_ids:
                raise ProfileFormatError(f"{path}.{field_name}.source_ids must not be empty")
            missing = sorted(set(source_ids) - set(sources))
            if missing:
                raise ProfileFormatError(f"{path}.{field_name} references unknown sources: {', '.join(missing)}")
            status = self._optional_text(item.get("status"), f"{path}.{field_name}.status") or "documented"
            if status not in EVIDENCE_STATUSES:
                raise ProfileFormatError(f"{path}.{field_name}.status is not recognized: {status}")
            tested_os = self._optional_text(item.get("tested_os_version"), f"{path}.{field_name}.tested_os_version")
            tested_at = self._optional_text(item.get("tested_at"), f"{path}.{field_name}.tested_at")
            test_reference = self._optional_text(item.get("test_reference"), f"{path}.{field_name}.test_reference")
            if status == "hardware_confirmed":
                if not (tested_os and tested_at and test_reference):
                    raise ProfileFormatError(
                        f"{path}.{field_name} hardware confirmation requires tested_os_version, tested_at and test_reference"
                    )
                if not any(sources[source_id].kind in {"device_test", "user_capture"} for source_id in source_ids):
                    raise ProfileFormatError(f"{path}.{field_name} hardware confirmation requires a device_test or user_capture source")
            result[field_name] = Evidence(
                source_ids=source_ids,
                status=status,
                tested_os_version=tested_os,
                tested_at=tested_at,
                test_reference=test_reference,
                notes=self._optional_text(item.get("notes"), f"{path}.{field_name}.notes") or "",
            )
        return result

    def _sounds(self, value: object, sources: dict[str, ProfileSource]) -> dict[str, SoundProfile]:
        result: dict[str, SoundProfile] = {}
        for index, raw in enumerate(self._array(value, "sounds")):
            path = f"sounds[{index}]"
            item = self._object(raw, path)
            sound_id = self._text(item.get("sound_id"), f"{path}.sound_id")
            if sound_id in result:
                raise ProfileFormatError(f"duplicate sound_id: {sound_id}")
            note_range = self._note_range(item.get("note_range"), f"{path}.note_range")
            mode = self._optional_text(item.get("mode"), f"{path}.mode") or "unknown"
            if mode not in SOUND_MODES:
                raise ProfileFormatError(f"{path}.mode is not recognized: {mode}")
            evidence = self._evidence_map(item.get("evidence", {}), sources, f"{path}.evidence")
            self._require_identity_evidence(evidence, path)
            result[sound_id] = SoundProfile(
                sound_id=sound_id,
                display_name=self._text(item.get("display_name"), f"{path}.display_name"),
                bank_msb=self._midi(item.get("bank_msb"), f"{path}.bank_msb"),
                bank_lsb=self._midi(item.get("bank_lsb"), f"{path}.bank_lsb"),
                program=self._midi(item.get("program"), f"{path}.program"),
                family=self._optional_text(item.get("family"), f"{path}.family") or "unknown",
                note_range=note_range,
                mode=mode,
                evidence=evidence,
                extensions=self._object(item.get("extensions", {}), f"{path}.extensions"),
            )
        return result

    def _drum_kits(self, value: object, sources: dict[str, ProfileSource]) -> dict[str, DrumKitProfile]:
        result: dict[str, DrumKitProfile] = {}
        for index, raw in enumerate(self._array(value, "drum_kits")):
            path = f"drum_kits[{index}]"
            item = self._object(raw, path)
            kit_id = self._text(item.get("kit_id"), f"{path}.kit_id")
            if kit_id in result:
                raise ProfileFormatError(f"duplicate kit_id: {kit_id}")
            evidence = self._evidence_map(item.get("evidence", {}), sources, f"{path}.evidence")
            self._require_identity_evidence(evidence, path)
            notes: dict[int, DrumNoteProfile] = {}
            for note_index, raw_note in enumerate(self._array(item.get("notes", []), f"{path}.notes")):
                note_path = f"{path}.notes[{note_index}]"
                note_item = self._object(raw_note, note_path)
                note_number = self._midi(note_item.get("note"), f"{note_path}.note")
                if note_number in notes:
                    raise ProfileFormatError(f"duplicate drum note {note_number} in {kit_id}")
                note_evidence = self._evidence_map(note_item.get("evidence", {}), sources, f"{note_path}.evidence")
                if "identity" not in note_evidence:
                    raise ProfileFormatError(f"{note_path}.evidence requires an identity entry")
                layers = self._velocity_layers(note_item.get("velocity_layers", []), f"{note_path}.velocity_layers")
                notes[note_number] = DrumNoteProfile(
                    note=note_number,
                    display_name=self._text(note_item.get("display_name"), f"{note_path}.display_name"),
                    family=self._optional_text(note_item.get("family"), f"{note_path}.family") or "unknown",
                    velocity_layers=layers,
                    choke_group=self._optional_text(note_item.get("choke_group"), f"{note_path}.choke_group"),
                    evidence=note_evidence,
                    extensions=self._object(note_item.get("extensions", {}), f"{note_path}.extensions"),
                )
            result[kit_id] = DrumKitProfile(
                kit_id=kit_id,
                display_name=self._text(item.get("display_name"), f"{path}.display_name"),
                bank_msb=self._midi(item.get("bank_msb"), f"{path}.bank_msb"),
                bank_lsb=self._midi(item.get("bank_lsb"), f"{path}.bank_lsb"),
                program=self._midi(item.get("program"), f"{path}.program"),
                notes=notes,
                evidence=evidence,
                extensions=self._object(item.get("extensions", {}), f"{path}.extensions"),
            )
        return result

    def _rhythms(self, value: object) -> dict[str, RhythmProfile]:
        result: dict[str, RhythmProfile] = {}
        for index, raw in enumerate(self._array(value, "rhythms")):
            path = f"rhythms[{index}]"
            item = self._object(raw, path)
            profile_id = self._text(item.get("profile_id"), f"{path}.profile_id")
            if profile_id in result:
                raise ProfileFormatError(f"duplicate rhythm profile_id: {profile_id}")
            meters = []
            for meter_index, meter in enumerate(self._array(item.get("meters"), f"{path}.meters")):
                pair = self._array(meter, f"{path}.meters[{meter_index}]")
                if len(pair) != 2:
                    raise ProfileFormatError(f"{path}.meters[{meter_index}] must have numerator and denominator")
                numerator = self._integer(pair[0], f"{path}.meters[{meter_index}][0]")
                denominator = self._integer(pair[1], f"{path}.meters[{meter_index}][1]")
                if numerator < 1 or denominator < 1 or denominator & (denominator - 1):
                    raise ProfileFormatError(f"{path}.meters[{meter_index}] is not a valid MIDI meter")
                meters.append((numerator, denominator))
            if not meters:
                raise ProfileFormatError(f"{path}.meters must not be empty")
            result[profile_id] = RhythmProfile(
                profile_id=profile_id,
                display_name=self._text(item.get("display_name"), f"{path}.display_name"),
                meters=tuple(meters),
                groupings=tuple(self._string_array(item.get("groupings", []), f"{path}.groupings")),
                aliases=tuple(self._string_array(item.get("aliases", []), f"{path}.aliases")),
                notes=self._optional_text(item.get("notes"), f"{path}.notes") or "",
            )
        return result

    @staticmethod
    def _require_identity_evidence(evidence: dict[str, Evidence], path: str) -> None:
        if "identity" not in evidence:
            raise ProfileFormatError(f"{path}.evidence requires an identity entry for CC0/CC32/PC")

    @staticmethod
    def _validate_unique_voice_addresses(profile: DeviceProfile) -> None:
        addresses: dict[tuple[int, int, int], str] = {}
        for sound in profile.sounds.values():
            address = (sound.bank_msb, sound.bank_lsb, sound.program)
            if address in addresses:
                raise ProfileFormatError(f"duplicate voice address {address}: {addresses[address]} and {sound.sound_id}")
            addresses[address] = sound.sound_id
        for kit in profile.drum_kits.values():
            address = (kit.bank_msb, kit.bank_lsb, kit.program)
            if address in addresses:
                raise ProfileFormatError(f"duplicate voice address {address}: {addresses[address]} and {kit.kit_id}")
            addresses[address] = kit.kit_id

    def _velocity_layers(self, value: object, path: str) -> tuple[tuple[int, int, str], ...]:
        result = []
        previous_end = -1
        for index, raw in enumerate(self._array(value, path)):
            layer = self._array(raw, f"{path}[{index}]")
            if len(layer) != 3:
                raise ProfileFormatError(f"{path}[{index}] must contain start, end and label")
            start = self._midi(layer[0], f"{path}[{index}][0]")
            end = self._midi(layer[1], f"{path}[{index}][1]")
            label = self._text(layer[2], f"{path}[{index}][2]")
            if start < 1 or start > end or start <= previous_end:
                raise ProfileFormatError(f"{path}[{index}] must be ordered, non-overlapping and within velocity 1--127")
            previous_end = end
            result.append((start, end, label))
        return tuple(result)

    def _note_range(self, value: object, path: str) -> tuple[int, int] | None:
        if value is None:
            return None
        pair = self._array(value, path)
        if len(pair) != 2:
            raise ProfileFormatError(f"{path} must contain low and high note")
        low = self._midi(pair[0], f"{path}[0]")
        high = self._midi(pair[1], f"{path}[1]")
        if low > high:
            raise ProfileFormatError(f"{path} low note must not exceed high note")
        return low, high

    @staticmethod
    def _object(value: object, path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ProfileFormatError(f"{path} must be a JSON object")
        return value

    @staticmethod
    def _array(value: object, path: str) -> list[Any]:
        if not isinstance(value, list):
            raise ProfileFormatError(f"{path} must be a JSON array")
        return value

    def _string_array(self, value: object, path: str) -> list[str]:
        return [self._text(item, f"{path}[{index}]") for index, item in enumerate(self._array(value, path))]

    @staticmethod
    def _text(value: object, path: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ProfileFormatError(f"{path} must be a non-empty string")
        return value

    @staticmethod
    def _optional_text(value: object, path: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ProfileFormatError(f"{path} must be a string or null")
        return value

    @staticmethod
    def _integer(value: object, path: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ProfileFormatError(f"{path} must be an integer")
        return value

    def _midi(self, value: object, path: str) -> int:
        result = self._integer(value, path)
        if not 0 <= result <= 127:
            raise ProfileFormatError(f"{path} must be in MIDI range 0--127")
        return result
