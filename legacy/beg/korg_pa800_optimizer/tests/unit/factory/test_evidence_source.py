from __future__ import annotations

from korg_optimizer.factory.evidence_source import extract_evidence, parse_style_section
from korg_optimizer.midi.normalized_model import NormalizedMidiFile

from tests.unit.factory.samples import CLEAN_SAMPLE, MISMATCH_3_4, MISMATCH_AM_PM


def test_clean_filename_has_no_mismatch():
    style_name, section, level, mismatch = parse_style_section(CLEAN_SAMPLE)
    assert style_name == "50's  Fox"
    assert section == "Var1"
    assert level == "CONFIRMED"
    assert mismatch is False


def test_am_pm_style_is_flagged_as_mismatch():
    style_name, section, level, mismatch = parse_style_section(MISMATCH_AM_PM)
    assert style_name == "AM "
    assert section == "Break"
    assert level == "CONFIRMED"
    assert mismatch is True


def test_3_4_qualifier_is_flagged_as_mismatch():
    style_name, section, level, mismatch = parse_style_section(MISMATCH_3_4)
    assert style_name == "Acoustic Bld"
    assert section == "Break"
    assert level == "CONFIRMED"
    assert mismatch is True


def test_unparseable_filename_is_unknown_not_guessed(tmp_path):
    fake = tmp_path / "SomeStyle" / "not_a_style_section_file.mid"
    fake.parent.mkdir()
    fake.touch()
    style_name, section, level, mismatch = parse_style_section(fake)
    assert style_name == "SomeStyle"
    assert section is None
    assert level == "UNKNOWN"
    assert mismatch is False


def test_extract_evidence_produces_one_row_per_track_plus_file_level_row():
    normalized = NormalizedMidiFile.from_file(CLEAN_SAMPLE)
    records = extract_evidence(normalized, source_file_id=1, file_path=CLEAN_SAMPLE)

    assert len(records) == len(normalized.tracks) + 1
    file_level = [r for r in records if r.track_index is None]
    assert len(file_level) == 1
    assert file_level[0].style_name == "50's  Fox"
    assert file_level[0].style_section == "Var1"
    assert file_level[0].event_summary["style_name_filename_mismatch"] is False
    assert file_level[0].event_summary["track_count"] == len(normalized.tracks)

    track_rows = [r for r in records if r.track_index is not None]
    assert {r.track_index for r in track_rows} == {t.index for t in normalized.tracks}
    for row in track_rows:
        assert row.style_name is None  # style/section only on the file-level row
        assert "note_count" in row.event_summary


def test_extract_evidence_without_file_path_omits_file_level_row():
    normalized = NormalizedMidiFile.from_file(CLEAN_SAMPLE)
    records = extract_evidence(normalized, source_file_id=1)
    assert len(records) == len(normalized.tracks)
    assert all(r.track_index is not None for r in records)
