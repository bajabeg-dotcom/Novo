import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..smf.vlq import encode_vlq
from .loader import HardwareTestLoader


@dataclass(frozen=True, slots=True)
class GeneratedHardwareProbe:
    manifest_path: Path
    fixture_path: Path
    fixture_sha256: str
    manifest_sha256: str


class HardwareProbeGenerator:
    """Create deterministic, pending Pa800 sound and drum test cases."""

    PPQ = 384
    INITIALIZATION_TICKS = PPQ * 4
    NOTE_TICKS = PPQ

    def __init__(self) -> None:
        self.loader = HardwareTestLoader()

    def generate(
        self,
        output_directory: Path,
        *,
        kind: str,
        case_id: str,
        bank_msb: int,
        bank_lsb: int,
        program: int,
        note: int,
        velocity: int,
        expected_name: str,
        os_version: str,
        musical_resources_version: str | None,
        channel: int | None = None,
        expected_kit_name: str | None = None,
        overwrite: bool = False,
    ) -> GeneratedHardwareProbe:
        if kind not in {"sound", "drum"}:
            raise ValueError("probe kind must be 'sound' or 'drum'")
        self._text(case_id, "case_id")
        self._text(expected_name, "expected_name")
        self._text(os_version, "os_version")
        self._midi_value(bank_msb, "bank_msb")
        self._midi_value(bank_lsb, "bank_lsb")
        self._midi_value(program, "program")
        self._midi_value(note, "note")
        if not 1 <= velocity <= 127:
            raise ValueError("velocity must be in the range 1..127")
        resolved_channel = channel if channel is not None else (10 if kind == "drum" else 1)
        if not 1 <= resolved_channel <= 16:
            raise ValueError("channel must be in the range 1..16")
        if kind == "drum" and resolved_channel != 10:
            raise ValueError("drum probes must use MIDI channel 10")
        if kind == "drum":
            self._text(expected_kit_name, "expected_kit_name")

        fixture_relative = Path("fixtures") / f"{case_id}.mid"
        manifest_path = output_directory / f"{case_id}.json"
        fixture_path = output_directory / fixture_relative
        if not overwrite:
            existing = [path for path in (manifest_path, fixture_path) if path.exists()]
            if existing:
                raise FileExistsError(f"refusing to overwrite {existing[0]}")

        midi = self._build_midi(
            case_id=case_id,
            channel=resolved_channel,
            bank_msb=bank_msb,
            bank_lsb=bank_lsb,
            program=program,
            note=note,
            velocity=velocity,
        )
        fixture_sha256 = hashlib.sha256(midi).hexdigest()
        data = self._manifest_data(
            kind=kind,
            case_id=case_id,
            fixture_path=fixture_relative,
            fixture_sha256=fixture_sha256,
            channel=resolved_channel,
            bank_msb=bank_msb,
            bank_lsb=bank_lsb,
            program=program,
            note=note,
            velocity=velocity,
            expected_name=expected_name,
            expected_kit_name=expected_kit_name,
            os_version=os_version,
            musical_resources_version=musical_resources_version,
        )
        case = self.loader.from_data(data)
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        output_directory.mkdir(parents=True, exist_ok=True)
        fixture_path.write_bytes(midi)
        manifest_path.write_text(self.loader.dumps(case), encoding="utf-8")
        return GeneratedHardwareProbe(
            manifest_path=manifest_path,
            fixture_path=fixture_path,
            fixture_sha256=fixture_sha256,
            manifest_sha256=self.loader.digest(case),
        )

    def _build_midi(
        self,
        *,
        case_id: str,
        channel: int,
        bank_msb: int,
        bank_lsb: int,
        program: int,
        note: int,
        velocity: int,
    ) -> bytes:
        channel_index = channel - 1
        name = case_id.encode("ascii", "replace")
        events = [
            self._event(0, b"\xFF\x03" + encode_vlq(len(name)) + name),
            self._event(0, b"\xFF\x51\x03\x07\xA1\x20"),
            self._event(0, b"\xFF\x58\x04\x04\x02\x18\x08"),
            self._event(0, bytes((0xB0 | channel_index, 0, bank_msb))),
            self._event(0, bytes((0xB0 | channel_index, 32, bank_lsb))),
            self._event(0, bytes((0xC0 | channel_index, program))),
            self._event(0, bytes((0xB0 | channel_index, 7, 100))),
            self._event(0, bytes((0xB0 | channel_index, 10, 64))),
            self._event(0, bytes((0xB0 | channel_index, 11, 127))),
            self._event(
                self.INITIALIZATION_TICKS,
                bytes((0x90 | channel_index, note, velocity)),
            ),
            self._event(self.NOTE_TICKS, bytes((0x80 | channel_index, note, 64))),
            self._event(0, b"\xFF\x2F\x00"),
        ]
        track = b"".join(events)
        header = (
            b"MThd"
            + (6).to_bytes(4, "big")
            + (0).to_bytes(2, "big")
            + (1).to_bytes(2, "big")
            + self.PPQ.to_bytes(2, "big")
        )
        return header + b"MTrk" + len(track).to_bytes(4, "big") + track

    def _manifest_data(
        self,
        *,
        kind: str,
        case_id: str,
        fixture_path: Path,
        fixture_sha256: str,
        channel: int,
        bank_msb: int,
        bank_lsb: int,
        program: int,
        note: int,
        velocity: int,
        expected_name: str,
        expected_kit_name: str | None,
        os_version: str,
        musical_resources_version: str | None,
    ) -> dict[str, object]:
        address = {
            "channel": channel,
            "bank_msb": bank_msb,
            "bank_lsb": bank_lsb,
            "program": program,
        }
        if kind == "sound":
            title = f"Verify sound {expected_name} at {bank_msb}.{bank_lsb}.{program}"
            identity_assertion = {
                "assertion_id": "sound_identity",
                "kind": "sound_identity",
                "description": "Confirm the displayed and audible sound identity on the Pa800",
                "expected": {**address, "display_name": expected_name},
            }
        else:
            title = f"Verify drum note {note} ({expected_name}) in {expected_kit_name}"
            identity_assertion = {
                "assertion_id": "drum_note",
                "kind": "drum_note",
                "description": "Confirm the selected kit and audible identity of one drum note",
                "expected": {
                    **address,
                    "kit_name": expected_kit_name,
                    "note": note,
                    "note_name": expected_name,
                    "velocity": velocity,
                },
            }
        return {
            "schema_version": 1,
            "case_version": "1.0.0",
            "case_id": case_id,
            "title": title,
            "fixture": {
                "path": fixture_path.as_posix(),
                "sha256": fixture_sha256,
                "license": "project_generated",
                "description": (
                    "Deterministic format-0 probe with one 4/4 initialization bar "
                    "and one quarter-note test event"
                ),
            },
            "device": {
                "model": "Korg Pa800",
                "os_version": os_version,
                "musical_resources_version": musical_resources_version,
                "serial_number": None,
                "state": {
                    "global_midi_preset": "Factory Default",
                    "song_play_mode": "default",
                    "transpose": "0",
                },
            },
            "assertions": [
                identity_assertion,
                {
                    "assertion_id": "initialization",
                    "kind": "initialization",
                    "description": "Confirm bank/program selection occurs before the test note",
                    "expected": {**address, "first_note_tick": self.INITIALIZATION_TICKS},
                },
                {
                    "assertion_id": "round_trip",
                    "kind": "round_trip",
                    "description": "Confirm identity survives Pa800 import, save and reload",
                    "expected": {"cycles": 2, "identity_unchanged": True},
                },
            ],
            "cycles": [
                {"cycle": 1, "status": "pending", "observations": {}, "log": []},
                {"cycle": 2, "status": "pending", "observations": {}, "log": []},
            ],
            "extensions": {
                "generator": "pa800-enhancer",
                "probe_kind": kind,
                "hypothesis_only": True,
            },
        }

    @staticmethod
    def _event(delta: int, message: bytes) -> bytes:
        return encode_vlq(delta) + message

    @staticmethod
    def _text(value: str | None, field: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")

    @staticmethod
    def _midi_value(value: int, field: str) -> None:
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 127:
            raise ValueError(f"{field} must be in the range 0..127")
