import hashlib
from pathlib import Path

from ..domain.song import Song
from ..smf.errors import PreserveMismatchError
from ..smf.reader import SmfReader
from ..smf.writer import PreserveWriter, SegmentPreserveWriter, SmfWriter
from ..validation.validator import SongValidator
from .report import ExportReport


class ExportService:
    def __init__(self) -> None:
        self.writer = SmfWriter()
        self.preserve_writer = PreserveWriter()
        self.segment_writer = SegmentPreserveWriter()
        self.reader = SmfReader()
        self.validator = SongValidator()

    def export(self, song: Song, path: Path, profile_id: str, write_report: bool = True, mode: str = "auto") -> ExportReport:
        issues = self.validator.validate(song)
        if any(issue.blocks_export for issue in issues):
            raise ValueError("validation error blocks export")
        if mode not in ("auto", "preserve", "segment-preserve", "canonical"):
            raise ValueError(f"unknown export mode {mode}")
        can_preserve = song.raw_document is not None and song.raw_document.matches(song)
        if mode == "preserve" or (mode == "auto" and can_preserve):
            actual_mode = "preserve"
            self.preserve_writer.write(song, path)
        elif mode == "segment-preserve":
            actual_mode = "segment-preserve"
            self.segment_writer.write(song, path)
        elif mode == "auto":
            try:
                self.segment_writer.write(song, path)
                actual_mode = "segment-preserve"
            except PreserveMismatchError:
                self.writer.write(song, path)
                actual_mode = "canonical"
        else:
            actual_mode = "canonical"
            self.writer.write(song, path)
        reparsed = self.reader.read(path)
        post_issues = self.validator.validate(reparsed)
        if any(issue.blocks_export for issue in post_issues):
            path.unlink(missing_ok=True)
            raise ValueError("serialized MIDI failed post-export validation")
        output_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        report = ExportReport(song.source_sha256, output_sha256, str(path), profile_id, actual_mode, warnings=[issue.message for issue in issues + post_issues])
        if write_report:
            report.write_json(path.with_suffix(path.suffix + ".report.json"))
        return report