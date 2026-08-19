"""Pure-function tests for dna/extraction.py's formulas, against
hand-constructed values with known, hand-computable expected results.
Deliberately does not use any .mid fixtures -- these are pure Python
list-in, number-out tests.
"""

from __future__ import annotations

from korg_optimizer.dna.extraction import (
    NoteEvent,
    WelfordAccumulator,
    compute_accent_ratio,
    compute_activity_ratio,
    compute_co_activity,
    compute_dynamic_contour_slope,
    compute_gate_ratios,
    compute_note_density,
    compute_swing_ratio,
    compute_syncopation_ratio,
    confidence_score,
    confidence_score_categorical,
    fit_subdivision,
    merge_intervals,
    pair_notes,
)

PPQ = 192


def test_fit_subdivision_quarter_grid():
    onsets = [0, 192, 384, 576, 768]
    label, score, _ = fit_subdivision(onsets, PPQ)
    assert label == "quarter"
    assert score == 1.0


def test_fit_subdivision_prefers_coarsest_grid_on_tie():
    # A quarter-grid pattern technically also lies exactly on the
    # sixteenth grid -- the coarsest-first tie-break must pick "quarter".
    onsets = [0, 192, 384, 576]
    label, _, _ = fit_subdivision(onsets, PPQ)
    assert label == "quarter"


def test_fit_subdivision_eighth_grid():
    onsets = [0, 96, 192, 288, 384, 480]
    label, score, _ = fit_subdivision(onsets, PPQ)
    assert label == "eighth"
    assert score == 1.0


def test_fit_subdivision_empty_is_unknown():
    label, score, scores = fit_subdivision([], PPQ)
    assert label == "unknown"
    assert score == 0.0
    assert scores == {}


def test_syncopation_ratio_all_on_beat():
    onsets = [0, 192, 384, 576]
    assert compute_syncopation_ratio(onsets, PPQ) == 0.0


def test_syncopation_ratio_all_off_beat():
    onsets = [48, 240, 432]
    assert compute_syncopation_ratio(onsets, PPQ) == 1.0


def test_swing_ratio_short_long_pattern():
    onsets = []
    t = 0
    for _ in range(6):
        onsets.append(t)
        t += 64  # short
        onsets.append(t)
        t += 128  # long
    ratio = compute_swing_ratio(onsets, PPQ)
    assert ratio is not None
    assert abs(ratio - 2.0) < 0.05


def test_swing_ratio_straight_eighths_is_one():
    onsets = [i * 96 for i in range(10)]
    ratio = compute_swing_ratio(onsets, PPQ)
    assert ratio is not None
    assert abs(ratio - 1.0) < 0.05


def test_swing_ratio_none_below_minimum_pairs():
    onsets = [0, 96, 192]
    assert compute_swing_ratio(onsets, PPQ) is None


def test_note_density():
    assert abs(compute_note_density(note_count=8, span_ticks=768, ppq=192) - 2.0) < 1e-9


def test_note_density_floors_span_at_one_beat():
    # span smaller than one beat must not create a density spike
    d = compute_note_density(note_count=1, span_ticks=1, ppq=192)
    assert d == 1.0


def test_accent_ratio_detects_outlier_velocity():
    velocities = [60] * 10 + [120]
    ratio = compute_accent_ratio(velocities)
    assert 0.0 < ratio <= 1 / 11 + 1e-9


def test_accent_ratio_zero_stddev_is_zero():
    assert compute_accent_ratio([60, 60, 60]) == 0.0


def test_accent_ratio_empty_is_zero():
    assert compute_accent_ratio([]) == 0.0


def test_dynamic_contour_slope_increasing():
    notes = [
        NoteEvent(onset_tick=0, duration_ticks=10, velocity=50, channel=0),
        NoteEvent(onset_tick=100, duration_ticks=10, velocity=60, channel=0),
        NoteEvent(onset_tick=200, duration_ticks=10, velocity=70, channel=0),
        NoteEvent(onset_tick=300, duration_ticks=10, velocity=80, channel=0),
    ]
    slope = compute_dynamic_contour_slope(notes, span_ticks=300)
    assert slope is not None and slope > 0


def test_dynamic_contour_slope_flat_is_near_zero():
    notes = [
        NoteEvent(onset_tick=0, duration_ticks=10, velocity=60, channel=0),
        NoteEvent(onset_tick=100, duration_ticks=10, velocity=60, channel=0),
        NoteEvent(onset_tick=200, duration_ticks=10, velocity=60, channel=0),
    ]
    slope = compute_dynamic_contour_slope(notes, span_ticks=200)
    assert slope is not None and abs(slope) < 1e-9


def test_dynamic_contour_slope_none_for_single_note():
    notes = [NoteEvent(onset_tick=0, duration_ticks=10, velocity=60, channel=0)]
    assert compute_dynamic_contour_slope(notes, span_ticks=100) is None


def test_gate_ratios_legato_vs_staccato():
    # legato: duration nearly fills the IOI to the next onset
    legato_notes = [
        NoteEvent(onset_tick=0, duration_ticks=95, velocity=80, channel=0),
        NoteEvent(onset_tick=100, duration_ticks=95, velocity=80, channel=0),
        NoteEvent(onset_tick=200, duration_ticks=10, velocity=80, channel=0),
    ]
    ratios = compute_gate_ratios(legato_notes)
    assert len(ratios) == 2  # last note excluded (no next onset)
    assert all(r > 0.9 for r in ratios)

    staccato_notes = [
        NoteEvent(onset_tick=0, duration_ticks=10, velocity=80, channel=0),
        NoteEvent(onset_tick=100, duration_ticks=10, velocity=80, channel=0),
    ]
    ratios2 = compute_gate_ratios(staccato_notes)
    assert len(ratios2) == 1
    assert ratios2[0] < 0.2


def test_gate_ratios_excludes_unterminated_notes():
    notes = [
        NoteEvent(onset_tick=0, duration_ticks=None, velocity=80, channel=0),
        NoteEvent(onset_tick=100, duration_ticks=50, velocity=80, channel=0),
    ]
    assert compute_gate_ratios(notes) == []


def test_gate_ratios_grouped_by_channel():
    # a channel-1 note between two channel-0 notes must not be treated
    # as channel 0's "next onset"
    notes = [
        NoteEvent(onset_tick=0, duration_ticks=100, velocity=80, channel=0),
        NoteEvent(onset_tick=50, duration_ticks=10, velocity=80, channel=1),
        NoteEvent(onset_tick=200, duration_ticks=10, velocity=80, channel=0),
    ]
    ratios = compute_gate_ratios(notes)
    # channel 0: onset 0 -> next onset (channel 0) at 200, duration 100 -> ratio 0.5
    assert len(ratios) == 1
    assert abs(ratios[0] - 0.5) < 1e-9


def test_merge_intervals():
    assert merge_intervals([(0, 100), (50, 150), (200, 300)]) == [(0, 150), (200, 300)]
    assert merge_intervals([]) == []


def test_activity_ratio():
    ratio = compute_activity_ratio([(0, 100), (150, 200)], file_duration_ticks=200)
    assert abs(ratio - 0.75) < 1e-9


def test_activity_ratio_empty_intervals_is_zero():
    assert compute_activity_ratio([], file_duration_ticks=100) == 0.0


def test_co_activity_partial_overlap():
    co = compute_co_activity([(0, 100)], [(50, 150)])
    assert abs(co - (50 / 150)) < 1e-9


def test_co_activity_disjoint_is_zero():
    assert compute_co_activity([(0, 50)], [(100, 150)]) == 0.0


def test_co_activity_identical_is_one():
    assert compute_co_activity([(0, 100)], [(0, 100)]) == 1.0


def test_confidence_score_monotonic_in_occurrence_count():
    low = confidence_score(occurrence_count=10, saturation_n=100, mean=1.0, stddev=0.0)
    high = confidence_score(occurrence_count=100, saturation_n=100, mean=1.0, stddev=0.0)
    assert high > low
    assert high == 1.0


def test_confidence_score_monotonic_decreasing_in_variability():
    consistent = confidence_score(occurrence_count=100, saturation_n=100, mean=10.0, stddev=1.0)
    noisy = confidence_score(occurrence_count=100, saturation_n=100, mean=10.0, stddev=10.0)
    assert consistent > noisy


def test_confidence_score_clamped_and_no_div_by_zero():
    score = confidence_score(occurrence_count=1000, saturation_n=100, mean=0.0, stddev=0.0)
    assert 0.0 <= score <= 1.0


def test_confidence_score_categorical():
    score = confidence_score_categorical(occurrence_count=100, saturation_n=100, mode_count=90, total_count=100)
    assert abs(score - 0.9) < 1e-9


def test_welford_accumulator_matches_naive_stats():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    acc = WelfordAccumulator()
    for v in values:
        acc.add(v)
    naive_mean = sum(values) / len(values)
    naive_var = sum((v - naive_mean) ** 2 for v in values) / len(values)
    assert abs(acc.mean - naive_mean) < 1e-9
    assert abs(acc.variance - naive_var) < 1e-9


def test_pair_notes_basic_pairing():
    import mido

    track = _make_track(
        [
            (0, mido.Message("note_on", channel=0, note=60, velocity=90)),
            (100, mido.Message("note_off", channel=0, note=60, velocity=0)),
        ]
    )
    notes = pair_notes(track)
    assert len(notes) == 1
    assert notes[0].onset_tick == 0
    assert notes[0].duration_ticks == 100
    assert notes[0].velocity == 90


def test_pair_notes_velocity_zero_note_on_closes_note():
    import mido

    track = _make_track(
        [
            (0, mido.Message("note_on", channel=0, note=60, velocity=90)),
            (50, mido.Message("note_on", channel=0, note=60, velocity=0)),
        ]
    )
    notes = pair_notes(track)
    assert len(notes) == 1
    assert notes[0].duration_ticks == 50


def test_pair_notes_unterminated_note_has_none_duration():
    import mido

    track = _make_track([(0, mido.Message("note_on", channel=0, note=60, velocity=90))])
    notes = pair_notes(track)
    assert len(notes) == 1
    assert notes[0].duration_ticks is None


def test_pair_notes_fifo_for_retriggered_notes():
    import mido

    track = _make_track(
        [
            (0, mido.Message("note_on", channel=0, note=60, velocity=90)),
            (10, mido.Message("note_on", channel=0, note=60, velocity=100)),
            (50, mido.Message("note_off", channel=0, note=60, velocity=0)),
            (60, mido.Message("note_off", channel=0, note=60, velocity=0)),
        ]
    )
    notes = pair_notes(track)
    assert len(notes) == 2
    assert notes[0].onset_tick == 0 and notes[0].duration_ticks == 50
    assert notes[1].onset_tick == 10 and notes[1].duration_ticks == 50


def _make_track(events):
    from korg_optimizer.midi.normalized_model import NormalizedEvent, NormalizedTrack

    return NormalizedTrack(
        index=0, name="test", events=[NormalizedEvent(abs_tick=t, message=m) for t, m in events]
    )
