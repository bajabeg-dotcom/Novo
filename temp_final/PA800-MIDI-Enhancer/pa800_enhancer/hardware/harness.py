import hashlib
from pathlib import Path

from ..smf.errors import SmfError
from ..smf.reader import SmfReader
from ..validation.validator import SongValidator
from .loader import HardwareTestLoader
from .models import HardwarePreflight


class HardwareTestHarness:
    def __init__(self) -> None:
        self.loader = HardwareTestLoader()
        self.reader = SmfReader()
        self.validator = SongValidator()

    def preflight(self, manifest_path: Path) -> HardwarePreflight:
        case = self.loader.load(manifest_path)
        fixture_path = manifest_path.parent / case.fixture.path
        blockers = []
        warnings = []
        digest = None
        song = None
        try:
            payload = fixture_path.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            if digest != case.fixture.sha256:
                blockers.append(
                    f"fixture SHA-256 mismatch: expected {case.fixture.sha256}, got {digest}"
                )
            song = self.reader.parse(payload)
        except OSError as error:
            blockers.append(f"cannot read fixture: {error}")
        except SmfError as error:
            blockers.append(f"invalid SMF fixture: {error}")

        if song is not None:
            for issue in self.validator.validate(song):
                message = f"{issue.code}: {issue.message}"
                if issue.blocks_export:
                    blockers.append(message)
                else:
                    warnings.append(message)
        return HardwarePreflight(
            case_id=case.case_id,
            case_version=case.case_version,
            case_status=case.status,
            manifest_sha256=self.loader.digest(case),
            device_model=case.device.model,
            os_version=case.device.os_version,
            musical_resources_version=case.device.musical_resources_version,
            fixture_path=str(fixture_path),
            fixture_sha256=digest,
            smf_format=song.header.format_type if song else None,
            division=song.header.division if song else None,
            track_count=len(song.tracks) if song else None,
            event_count=song.event_count if song else None,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )