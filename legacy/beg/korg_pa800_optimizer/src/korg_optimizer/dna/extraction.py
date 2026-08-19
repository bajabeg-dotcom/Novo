"""Factory DNA extraction: Rhythm, Velocity, Timing, and Arrangement
DNA computed from real Factory Style evidence in evidence.db.

Melody DNA and true Harmony DNA (key/chord relations over time) are
explicitly OUT OF SCOPE here -- they require note-sequence/interval and
harmonic-context analysis that belongs to Solo DNA (Phase 9) and
Harmony (Phase 10), not implemented yet.

No instrument identity exists yet (Phase 7), so every metric here is
grouped only by structural, already-CONFIRMED facts: the
filename-derived Style Element section, and the raw 0-indexed MIDI
channel number -- never by an assumed instrument role. See
docs/DATABASE_ARCHITECTURE.md "factory_dna grouping keys" and
docs/GOLD_DNA_MODEL.md for the exact formulas implemented below.

Two passes:
  - "cheap" pass: pure SQL over already-stored factory_evidence
    summaries (arrangement.section_behavior only -- no MIDI re-parse).
  - "expensive" pass: re-parses every real Factory Style .mid file,
    since per-note onset/duration/velocity sequences are not stored
    anywhere in evidence.db (only summaries are). Covers rhythm,
    velocity, timing, and arrangement.channel_profile/layer_interaction.

Owning vertical: B.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Iterator

from .factory_dna import FactoryDNARecord, save_factory_dna
from ..infrastructure import config
from ..midi.normalized_model import NormalizedMidiFile, NormalizedTrack

EXTRACTOR_VERSION = "0.1.0"

# A group (style_section[, channel[, channel_b]]) must have contributions
# from at least this many distinct source files before it emits any
# factory_dna row at all -- below this there isn't enough data to call
# it a "pattern" (variance is meaningless with 1 sample).
MIN_GROUP_SOURCE_FILES = 2

# Candidate rhythmic grids, as a divisor of one quarter-note (ppq ticks).
# Ordered coarsest-first so fit_subdivision() picks the simplest grid
# that adequately explains the onsets, not the finest one that always
# "fits" almost anything.
SUBDIVISION_GRID_DIVISORS: dict[str, int] = {
    "quarter": 1,
    "eighth": 2,
    "eighth_triplet": 3,
    "sixteenth": 4,
    "sixteenth_triplet": 6,
}
SWING_ELIGIBLE_SUBDIVISIONS = {"eighth", "eighth_triplet", "sixteenth", "sixteenth_triplet"}
SUBDIVISION_FIT_THRESHOLD = 0.8

ACCENT_Z_THRESHOLD = 1.0
DYNAMIC_CONTOUR_MEANINGFUL_SLOPE = 10.0
SWING_MIN_PAIRS = 4

SATURATION_N = {
    "note_level": 5000,
    "track_level": 100,
    "pair_level": 50,
}

# Default duration (ticks-independent of ppq handled by caller) assumed
# for a note with no matching note_off, purely so it contributes a
# non-zero-length interval to activity/co-activity calculations. This
# never affects duration/gate statistics (those explicitly exclude
# unterminated notes).
_UNTERMINATED_NOTE_FRACTION_OF_BEAT = 1 / 8


# ---------------------------------------------------------------------------
# Pure formula functions -- no DB or file I/O, unit-tested directly.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NoteEvent:
    onset_tick: int
    duration_ticks: int | None  # None if unterminated (no matching note_off)
    velocity: int
    channel: int


class WelfordAccumulator:
    """Exact, O(1)-memory streaming mean/variance (Welford's algorithm)."""

    __slots__ = ("n", "mean", "m2")

    def __init__(self) -> None:
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0

    def add(self, x: float) -> None:
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (x - self.mean)

    @property
    def variance(self) -> float:
        return self.m2 / self.n if self.n else 0.0

    @property
    def stddev(self) -> float:
        return self.variance**0.5


def pair_notes(track: NormalizedTrack) -> list[NoteEvent]:
    """Pair note_on/note_off messages FIFO per (channel, pitch).

    A note_off (or a note_on with velocity 0, the standard MIDI
    running-status idiom) closes the oldest still-open note_on for the
    same channel+pitch. Any note_on left open at the end of the track
    becomes a ``NoteEvent`` with ``duration_ticks=None``.
    """
    notes: list[NoteEvent] = []
    open_notes: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)

    for event in track.events:
        msg = event.message
        if getattr(msg, "is_meta", False):
            continue
        if msg.type == "note_on" and msg.velocity > 0:
            open_notes[(msg.channel, msg.note)].append((event.abs_tick, msg.velocity))
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            key = (msg.channel, msg.note)
            queue = open_notes.get(key)
            if queue:
                onset_tick, velocity = queue.pop(0)
                notes.append(
                    NoteEvent(
                        onset_tick=onset_tick,
                        duration_ticks=event.abs_tick - onset_tick,
                        velocity=velocity,
                        channel=msg.channel,
                    )
                )
            # else: note_off with no matching note_on -- malformed input,
            # ignore rather than crash the whole extraction batch.

    for (channel, _pitch), queue in open_notes.items():
        for onset_tick, velocity in queue:
            notes.append(
                NoteEvent(onset_tick=onset_tick, duration_ticks=None, velocity=velocity, channel=channel)
            )

    notes.sort(key=lambda n: n.onset_tick)
    return notes


def fit_subdivision(onset_ticks: list[int], ppq: int) -> tuple[str, float, dict[str, float]]:
    """Find the coarsest rhythmic grid that adequately explains
    ``onset_ticks``. Returns ``(label, score, all_scores)``.

    For each candidate grid spacing ``g``, ``fit_score = 1 -
    mean(deviation)/(g/2)`` (1.0 = onsets land exactly on the grid, 0.0
    = as bad as a uniformly random onset). Picks the coarsest grid
    whose score clears ``SUBDIVISION_FIT_THRESHOLD``; if none does,
    picks the single best-scoring grid.
    """
    if not onset_ticks or ppq <= 0:
        return "unknown", 0.0, {}

    scores: dict[str, float] = {}
    for label, divisor in SUBDIVISION_GRID_DIVISORS.items():
        spacing = ppq / divisor
        if spacing <= 0:
            scores[label] = 0.0
            continue
        deviations = [min(t % spacing, spacing - (t % spacing)) for t in onset_ticks]
        mean_deviation = sum(deviations) / len(deviations)
        scores[label] = max(0.0, 1.0 - (mean_deviation / (spacing / 2)))

    coarsest_first = sorted(SUBDIVISION_GRID_DIVISORS, key=lambda label: SUBDIVISION_GRID_DIVISORS[label])
    for label in coarsest_first:
        if scores[label] >= SUBDIVISION_FIT_THRESHOLD:
            return label, scores[label], scores

    best_label = max(scores, key=lambda label: scores[label])
    return best_label, scores[best_label], scores


def compute_syncopation_ratio(onset_ticks: list[int], ppq: int) -> float:
    """Fraction of onsets that do not land on a quarter-note beat
    (``onset % ppq != 0``) -- a simplified proxy for syncopation. True
    metrical-weight syncopation (e.g. Longuet-Higgins/Lee-style) is out
    of scope for this session.
    """
    if not onset_ticks or ppq <= 0:
        return 0.0
    off_beat = sum(1 for t in onset_ticks if t % ppq != 0)
    return off_beat / len(onset_ticks)


def compute_swing_ratio(onset_ticks: list[int], ppq: int) -> float | None:
    """Mean ratio of consecutive eighth-note-scale inter-onset
    intervals: ``IOI(2k+1->2k+2) / IOI(2k->2k+1)``. 1.0 = straight
    eighths, ~2.0 = triplet-feel swing (per this project's documented
    convention -- see docs/GOLD_DNA_MODEL.md). Returns ``None`` when
    fewer than ``SWING_MIN_PAIRS`` valid pairs are found (not enough
    signal to report a value).
    """
    ticks = sorted(onset_ticks)
    if len(ticks) < 3 or ppq <= 0:
        return None

    ratios: list[float] = []
    i = 0
    while i + 2 < len(ticks):
        ioi1 = ticks[i + 1] - ticks[i]
        ioi2 = ticks[i + 2] - ticks[i + 1]
        combined = ioi1 + ioi2
        if ioi1 > 0 and ioi2 > 0 and abs(combined - ppq) <= ppq * 0.25:
            ratios.append(ioi2 / ioi1)
        i += 2

    if len(ratios) < SWING_MIN_PAIRS:
        return None
    return sum(ratios) / len(ratios)


def compute_note_density(note_count: int, span_ticks: int, ppq: int) -> float:
    """Notes per quarter-note beat, normalized against ``span_ticks``
    (never dividing by less than one beat, to avoid a spike from a
    near-zero span).
    """
    if ppq <= 0:
        return 0.0
    span = max(span_ticks, ppq)
    return note_count / span * ppq


def compute_accent_ratio(velocities: list[int], z_threshold: float = ACCENT_Z_THRESHOLD) -> float:
    """Fraction of notes whose velocity exceeds the track's own mean by
    more than ``z_threshold`` standard deviations -- an own-track
    baseline, so a generally-loud track isn't conflated with one that
    has internal accents.
    """
    if not velocities:
        return 0.0
    mean = sum(velocities) / len(velocities)
    variance = sum((v - mean) ** 2 for v in velocities) / len(velocities)
    stddev = variance**0.5
    if stddev == 0:
        return 0.0
    threshold = mean + z_threshold * stddev
    accents = sum(1 for v in velocities if v > threshold)
    return accents / len(velocities)


def compute_dynamic_contour_slope(notes: list[NoteEvent], span_ticks: int) -> float | None:
    """OLS slope of velocity vs. onset position normalized to [0, 1]
    across ``span_ticks`` -- total velocity change from the start to
    the end of the track. ``None`` when there are fewer than 2 notes or
    the track has zero span.
    """
    if len(notes) < 2 or span_ticks <= 0:
        return None
    xs = [n.onset_tick / span_ticks for n in notes]
    ys = [float(n.velocity) for n in notes]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return None
    return numerator / denominator


def compute_gate_ratios(notes: list[NoteEvent]) -> list[float]:
    """Per note (grouped by channel, excluding each channel's final
    note whose next-onset is undefined, and any unterminated note):
    ``duration_ticks / IOI to the next onset on the same channel``.
    ~1.0 = legato, ~0 = staccato.
    """
    by_channel: dict[int, list[NoteEvent]] = defaultdict(list)
    for note in notes:
        by_channel[note.channel].append(note)

    ratios: list[float] = []
    for channel_notes in by_channel.values():
        channel_notes = sorted(channel_notes, key=lambda n: n.onset_tick)
        for i in range(len(channel_notes) - 1):
            note = channel_notes[i]
            if note.duration_ticks is None:
                continue
            ioi = channel_notes[i + 1].onset_tick - note.onset_tick
            if ioi > 0:
                ratios.append(note.duration_ticks / ioi)
    return ratios


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def compute_activity_ratio(intervals: list[tuple[int, int]], file_duration_ticks: int) -> float:
    """Fraction of the file's duration during which at least one note
    is sounding on this channel (merged interval coverage / total
    duration). Explicitly NOT instrument "role" -- a structural proxy
    only, since no instrument identity exists yet.
    """
    if file_duration_ticks <= 0 or not intervals:
        return 0.0
    covered = sum(end - start for start, end in merge_intervals(intervals))
    return min(1.0, covered / file_duration_ticks)


def _intersection_length(a: list[tuple[int, int]], b: list[tuple[int, int]]) -> int:
    i = j = 0
    total = 0
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if start < end:
            total += end - start
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def compute_co_activity(intervals_a: list[tuple[int, int]], intervals_b: list[tuple[int, int]]) -> float:
    """Jaccard index (intersection/union of covered ticks) between two
    channels' active-interval sets within one file.
    """
    merged_a = merge_intervals(intervals_a)
    merged_b = merge_intervals(intervals_b)
    if not merged_a or not merged_b:
        return 0.0
    intersection = _intersection_length(merged_a, merged_b)
    union = sum(end - start for start, end in merge_intervals(merged_a + merged_b))
    if union == 0:
        return 0.0
    return intersection / union


def confidence_score(occurrence_count: int, saturation_n: int, mean: float, stddev: float) -> float:
    """size_component (saturating with occurrence_count) times
    consistency_component (inverse of coefficient of variation),
    clamped to [0, 1]. See docs/GOLD_DNA_MODEL.md.
    """
    size_component = min(1.0, occurrence_count / saturation_n) if saturation_n > 0 else 0.0
    if abs(mean) > 1e-9:
        cv = abs(stddev / mean)
    else:
        cv = 0.0 if stddev < 1e-9 else 1.0
    cv = max(0.0, min(cv, 5.0))
    consistency_component = 1 / (1 + cv)
    return round(max(0.0, min(size_component * consistency_component, 1.0)), 4)


def confidence_score_categorical(occurrence_count: int, saturation_n: int, mode_count: int, total_count: int) -> float:
    """Variant of ``confidence_score`` for categorical metrics (e.g.
    subdivision label), where consistency = the winning label's share
    of all observations.
    """
    size_component = min(1.0, occurrence_count / saturation_n) if saturation_n > 0 else 0.0
    consistency_component = (mode_count / total_count) if total_count else 0.0
    return round(max(0.0, min(size_component * consistency_component, 1.0)), 4)


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = max(0, min(len(sorted_values) - 1, int(round(p * (len(sorted_values) - 1)))))
    return sorted_values[idx]


def _median(sorted_values: list[float]) -> float:
    return _percentile(sorted_values, 0.5)


def _stats_from_list(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0, "median": 0.0, "p95": 0.0}
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    ordered = sorted(values)
    return {
        "mean": mean,
        "stddev": variance**0.5,
        "min": ordered[0],
        "max": ordered[-1],
        "median": _median(ordered),
        "p95": _percentile(ordered, 0.95),
    }


# ---------------------------------------------------------------------------
# Group accumulators (all financial/statistical state lives here; the
# extraction passes below only fold per-track/per-file values into them)
# ---------------------------------------------------------------------------


@dataclass
class _NoteGroup:
    """One (style_section, channel) group -- Group A. Backs the
    rhythm, velocity, timing, and arrangement.channel_profile rows.
    """

    style_section: str
    channel: int
    density_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    subdivision_counts: Counter = field(default_factory=Counter)
    syncopation_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    swing_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    groove_bias_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    groove_looseness_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    velocities: list[int] = field(default_factory=list)
    accent_ratio_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    dynamic_contour_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    durations_beats: list[float] = field(default_factory=list)
    gate_ratios: list[float] = field(default_factory=list)
    activity_ratio_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    total_note_count: int = 0
    track_count: int = 0
    source_file_ids: set[int] = field(default_factory=set)
    evidence_ids: set[int] = field(default_factory=set)
    source_kinds: Counter = field(default_factory=Counter)


@dataclass
class _PairGroup:
    """One (style_section, channel_a, channel_b) group -- Group A'.
    Backs arrangement.layer_interaction rows.
    """

    style_section: str
    channel_a: int
    channel_b: int
    co_activity_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    pair_instance_count: int = 0
    source_file_ids: set[int] = field(default_factory=set)
    evidence_ids: set[int] = field(default_factory=set)
    source_kinds: Counter = field(default_factory=Counter)


@dataclass
class _SectionBehaviorGroup:
    """One style_section group -- Group B. Backs
    arrangement.section_behavior rows.
    """

    style_section: str
    density_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    track_count_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    channels_used_count_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    duration_beats_acc: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    file_count: int = 0
    source_file_ids: set[int] = field(default_factory=set)
    evidence_ids: set[int] = field(default_factory=set)
    source_kinds: Counter = field(default_factory=Counter)


def _finalize_note_group(group: _NoteGroup, now: str) -> list[FactoryDNARecord]:
    evidence_ids = sorted(group.evidence_ids)
    source_kind_composition = dict(group.source_kinds)
    section, channel = group.style_section, group.channel

    subdivision_mode, mode_count = group.subdivision_counts.most_common(1)[0]
    subdivision_confidence = confidence_score_categorical(
        group.track_count, SATURATION_N["track_level"], mode_count, group.track_count
    )
    rhythm_metrics: dict[str, Any] = {
        "density": {"mean": round(group.density_acc.mean, 4), "stddev": round(group.density_acc.stddev, 4)},
        "subdivision": {
            "mode": subdivision_mode,
            "confidence": subdivision_confidence,
            "histogram": dict(group.subdivision_counts),
        },
        "syncopation_ratio": {
            "mean": round(group.syncopation_acc.mean, 4),
            "stddev": round(group.syncopation_acc.stddev, 4),
        },
        "groove": {
            "bias_mean": round(group.groove_bias_acc.mean, 4),
            "bias_stddev": round(group.groove_bias_acc.stddev, 4),
            "looseness_mean": round(group.groove_looseness_acc.mean, 4),
            "looseness_stddev": round(group.groove_looseness_acc.stddev, 4),
        },
    }
    if group.swing_acc.n > 0:
        rhythm_metrics["swing_ratio"] = {
            "mean": round(group.swing_acc.mean, 4),
            "stddev": round(group.swing_acc.stddev, 4),
            "track_count": group.swing_acc.n,
        }
    rhythm_confidence = confidence_score(
        group.total_note_count, SATURATION_N["note_level"], group.density_acc.mean, group.density_acc.stddev
    )

    velocity_stats = _stats_from_list([float(v) for v in group.velocities])
    velocity_metrics: dict[str, Any] = {
        **{k: round(v, 4) for k, v in velocity_stats.items()},
        "accent_ratio": {
            "mean": round(group.accent_ratio_acc.mean, 4),
            "stddev": round(group.accent_ratio_acc.stddev, 4),
        },
    }
    if group.dynamic_contour_acc.n > 0:
        velocity_metrics["dynamic_contour_slope"] = {
            "mean": round(group.dynamic_contour_acc.mean, 4),
            "stddev": round(group.dynamic_contour_acc.stddev, 4),
            "meaningful_fraction_threshold": DYNAMIC_CONTOUR_MEANINGFUL_SLOPE,
        }
    velocity_confidence = confidence_score(
        group.total_note_count, SATURATION_N["note_level"], velocity_stats["mean"], velocity_stats["stddev"]
    )

    duration_stats = _stats_from_list(group.durations_beats)
    gate_stats = _stats_from_list(group.gate_ratios)
    timing_metrics: dict[str, Any] = {
        "duration_beats": {k: round(v, 4) for k, v in duration_stats.items()},
        "gate_ratio": {"mean": round(gate_stats["mean"], 4), "median": round(gate_stats["median"], 4)},
        "onset_deviation": {
            "bias_mean": round(group.groove_bias_acc.mean, 4),
            "bias_stddev": round(group.groove_bias_acc.stddev, 4),
            "note": "identical computation to rhythm.groove -- shared, not re-derived",
        },
    }
    timing_confidence = confidence_score(
        group.total_note_count, SATURATION_N["note_level"], duration_stats["mean"], duration_stats["stddev"]
    )

    arrangement_metrics: dict[str, Any] = {
        "sub_category": "channel_profile",
        "density": {"mean": round(group.density_acc.mean, 4), "stddev": round(group.density_acc.stddev, 4)},
        "activity_ratio": {
            "mean": round(group.activity_ratio_acc.mean, 4),
            "stddev": round(group.activity_ratio_acc.stddev, 4),
        },
    }
    arrangement_confidence = confidence_score(
        group.track_count,
        SATURATION_N["track_level"],
        group.activity_ratio_acc.mean,
        group.activity_ratio_acc.stddev,
    )

    return [
        FactoryDNARecord(
            rule_id=f"dna.rhythm.section.{section}.ch{channel}",
            category="rhythm",
            style_section=section,
            channel=channel,
            channel_b=None,
            metrics=rhythm_metrics,
            derived_from_evidence_ids=evidence_ids,
            source_kind_composition=source_kind_composition,
            occurrence_count=group.total_note_count,
            confidence=rhythm_confidence,
            computed_at=now,
        ),
        FactoryDNARecord(
            rule_id=f"dna.velocity.section.{section}.ch{channel}",
            category="velocity",
            style_section=section,
            channel=channel,
            channel_b=None,
            metrics=velocity_metrics,
            derived_from_evidence_ids=evidence_ids,
            source_kind_composition=source_kind_composition,
            occurrence_count=group.total_note_count,
            confidence=velocity_confidence,
            computed_at=now,
        ),
        FactoryDNARecord(
            rule_id=f"dna.timing.section.{section}.ch{channel}",
            category="timing",
            style_section=section,
            channel=channel,
            channel_b=None,
            metrics=timing_metrics,
            derived_from_evidence_ids=evidence_ids,
            source_kind_composition=source_kind_composition,
            occurrence_count=group.total_note_count,
            confidence=timing_confidence,
            computed_at=now,
        ),
        FactoryDNARecord(
            rule_id=f"dna.arrangement.channel_profile.section.{section}.ch{channel}",
            category="arrangement",
            style_section=section,
            channel=channel,
            channel_b=None,
            metrics=arrangement_metrics,
            derived_from_evidence_ids=evidence_ids,
            source_kind_composition=source_kind_composition,
            occurrence_count=group.track_count,
            confidence=arrangement_confidence,
            computed_at=now,
        ),
    ]


def _finalize_pair_group(group: _PairGroup, now: str) -> FactoryDNARecord:
    metrics = {
        "sub_category": "layer_interaction",
        "co_activity": {"mean": round(group.co_activity_acc.mean, 4), "stddev": round(group.co_activity_acc.stddev, 4)},
    }
    confidence = confidence_score(
        group.pair_instance_count,
        SATURATION_N["pair_level"],
        group.co_activity_acc.mean,
        group.co_activity_acc.stddev,
    )
    return FactoryDNARecord(
        rule_id=f"dna.arrangement.layer_interaction.section.{group.style_section}.ch{group.channel_a}-ch{group.channel_b}",
        category="arrangement",
        style_section=group.style_section,
        channel=group.channel_a,
        channel_b=group.channel_b,
        metrics=metrics,
        derived_from_evidence_ids=sorted(group.evidence_ids),
        source_kind_composition=dict(group.source_kinds),
        occurrence_count=group.pair_instance_count,
        confidence=confidence,
        computed_at=now,
    )


def _finalize_section_behavior_group(group: _SectionBehaviorGroup, now: str) -> FactoryDNARecord:
    metrics = {
        "sub_category": "section_behavior",
        "density": {"mean": round(group.density_acc.mean, 4), "stddev": round(group.density_acc.stddev, 4)},
        "track_count": {
            "mean": round(group.track_count_acc.mean, 4),
            "stddev": round(group.track_count_acc.stddev, 4),
        },
        "channels_used_count": {
            "mean": round(group.channels_used_count_acc.mean, 4),
            "stddev": round(group.channels_used_count_acc.stddev, 4),
        },
        "duration_beats": {
            "mean": round(group.duration_beats_acc.mean, 4),
            "stddev": round(group.duration_beats_acc.stddev, 4),
        },
    }
    confidence = confidence_score(
        group.file_count, SATURATION_N["track_level"], group.density_acc.mean, group.density_acc.stddev
    )
    return FactoryDNARecord(
        rule_id=f"dna.arrangement.section_behavior.section.{group.style_section}",
        category="arrangement",
        style_section=group.style_section,
        channel=None,
        channel_b=None,
        metrics=metrics,
        derived_from_evidence_ids=sorted(group.evidence_ids),
        source_kind_composition=dict(group.source_kinds),
        occurrence_count=group.file_count,
        confidence=confidence,
        computed_at=now,
    )


# ---------------------------------------------------------------------------
# Extraction passes -- read from the evidence.db connection, return
# in-memory FactoryDNARecord lists. Never write to any database
# themselves; see extract_and_save() for the write step.
# ---------------------------------------------------------------------------


def _iter_real_style_files(
    evidence_conn: sqlite3.Connection,
) -> Iterator[tuple[int, Path, str, int]]:
    """Yield ``(source_file_id, absolute_path, style_section,
    file_level_evidence_id)`` for every REAL Factory Style source file
    with a CONFIRMED filename-derived section.
    """
    rows = evidence_conn.execute(
        """
        SELECT sf.id AS source_file_id, sf.file_path AS file_path,
               fe.id AS evidence_id, fe.style_section AS style_section
        FROM source_files sf
        JOIN factory_evidence fe ON fe.source_file_id = sf.id AND fe.track_index IS NULL
        WHERE sf.source_kind = 'REAL'
          AND fe.section_evidence_level = 'CONFIRMED'
          AND fe.style_section IS NOT NULL
        ORDER BY sf.id
        """
    ).fetchall()
    for row in rows:
        yield (
            row["source_file_id"],
            config.PACKAGE_ROOT / row["file_path"],
            row["style_section"],
            row["evidence_id"],
        )


def _cheap_pass(evidence_conn: sqlite3.Connection) -> list[FactoryDNARecord]:
    """arrangement.section_behavior only -- pure SQL over
    factory_evidence's already-stored summaries, no MIDI re-parse.
    """
    file_rows = evidence_conn.execute(
        """
        SELECT
            fe.style_section AS style_section,
            fe.source_file_id AS source_file_id,
            fe.id AS evidence_id,
            json_extract(fe.event_summary_json, '$.track_count') AS track_count,
            json_extract(fe.event_summary_json, '$.duration_ticks') AS duration_ticks,
            json_extract(fe.event_summary_json, '$.channels_used') AS channels_used_json,
            json_extract(fe.event_summary_json, '$.ppq') AS ppq
        FROM factory_evidence fe
        JOIN source_files sf ON sf.id = fe.source_file_id
        WHERE sf.source_kind = 'REAL'
          AND fe.track_index IS NULL
          AND fe.section_evidence_level = 'CONFIRMED'
          AND fe.style_section IS NOT NULL
        """
    ).fetchall()

    note_count_rows = evidence_conn.execute(
        """
        SELECT
            fe.source_file_id AS source_file_id,
            SUM(json_extract(fe.event_summary_json, '$.note_count')) AS total_notes
        FROM factory_evidence fe
        JOIN source_files sf ON sf.id = fe.source_file_id
        WHERE sf.source_kind = 'REAL' AND fe.track_index IS NOT NULL
        GROUP BY fe.source_file_id
        """
    ).fetchall()
    notes_by_file = {row["source_file_id"]: (row["total_notes"] or 0) for row in note_count_rows}

    groups: dict[str, _SectionBehaviorGroup] = {}
    for row in file_rows:
        section = row["style_section"]
        group = groups.setdefault(section, _SectionBehaviorGroup(style_section=section))
        duration_ticks = row["duration_ticks"] or 0
        ppq = row["ppq"] or 1
        total_notes = notes_by_file.get(row["source_file_id"], 0)
        density = compute_note_density(total_notes, duration_ticks, ppq)
        channels_used = json.loads(row["channels_used_json"]) if row["channels_used_json"] else []

        group.density_acc.add(density)
        group.track_count_acc.add(row["track_count"] or 0)
        group.channels_used_count_acc.add(len(channels_used))
        group.duration_beats_acc.add((duration_ticks / ppq) if ppq else 0.0)
        group.file_count += 1
        group.source_file_ids.add(row["source_file_id"])
        group.evidence_ids.add(row["evidence_id"])
        group.source_kinds["REAL"] += 1

    now = datetime.now(timezone.utc).isoformat()
    return [
        _finalize_section_behavior_group(group, now)
        for group in groups.values()
        if len(group.source_file_ids) >= MIN_GROUP_SOURCE_FILES
    ]


def _expensive_pass(evidence_conn: sqlite3.Connection) -> list[FactoryDNARecord]:
    """rhythm, velocity, timing, and arrangement.channel_profile /
    layer_interaction -- requires re-parsing every real Factory Style
    .mid file, since per-note onset/duration/velocity sequences are
    not stored anywhere in evidence.db (only summaries are).
    """
    note_groups: dict[tuple[str, int], _NoteGroup] = {}
    pair_groups: dict[tuple[str, int, int], _PairGroup] = {}

    for source_file_id, path, style_section, evidence_id in _iter_real_style_files(evidence_conn):
        try:
            normalized = NormalizedMidiFile.from_file(path)
        except Exception:
            continue  # one bad file must not abort the whole extraction

        ppq = normalized.ppq
        file_duration_ticks = max(
            (event.abs_tick for track in normalized.tracks for event in track.events), default=0
        )
        channel_intervals: dict[int, list[tuple[int, int]]] = defaultdict(list)

        for track in normalized.tracks:
            notes = pair_notes(track)
            if not notes:
                continue

            channel = Counter(n.channel for n in notes).most_common(1)[0][0]
            onset_ticks = [n.onset_tick for n in notes]
            velocities = [n.velocity for n in notes]

            if len(notes) >= 2:
                last_off = max(n.onset_tick + (n.duration_ticks or 0) for n in notes)
                span_ticks = max(last_off - notes[0].onset_tick, 1)
            else:
                span_ticks = file_duration_ticks or ppq

            subdivision_label, _score, _all_scores = fit_subdivision(onset_ticks, ppq)
            syncopation = compute_syncopation_ratio(onset_ticks, ppq)
            swing = (
                compute_swing_ratio(onset_ticks, ppq)
                if subdivision_label in SWING_ELIGIBLE_SUBDIVISIONS
                else None
            )

            divisor = SUBDIVISION_GRID_DIVISORS.get(subdivision_label, 1)
            spacing = ppq / divisor if divisor else ppq
            signed_deviations = []
            if spacing > 0:
                for t in onset_ticks:
                    remainder = t % spacing
                    signed = remainder if remainder <= spacing / 2 else remainder - spacing
                    signed_deviations.append(signed / ppq)
            groove_bias = sum(signed_deviations) / len(signed_deviations) if signed_deviations else 0.0
            groove_variance = (
                sum((d - groove_bias) ** 2 for d in signed_deviations) / len(signed_deviations)
                if signed_deviations
                else 0.0
            )
            groove_looseness = groove_variance**0.5

            density = compute_note_density(len(notes), span_ticks, ppq)
            accent_ratio = compute_accent_ratio(velocities)
            dynamic_slope = compute_dynamic_contour_slope(notes, span_ticks)
            gate_ratios = compute_gate_ratios(notes)
            durations_beats = [n.duration_ticks / ppq for n in notes if n.duration_ticks is not None]

            unterminated_default = max(int(ppq * _UNTERMINATED_NOTE_FRACTION_OF_BEAT), 1)
            intervals = [
                (n.onset_tick, n.onset_tick + (n.duration_ticks or unterminated_default)) for n in notes
            ]
            activity = compute_activity_ratio(intervals, file_duration_ticks)
            channel_intervals[channel].extend(intervals)

            group = note_groups.setdefault(
                (style_section, channel), _NoteGroup(style_section=style_section, channel=channel)
            )
            group.density_acc.add(density)
            group.subdivision_counts[subdivision_label] += 1
            group.syncopation_acc.add(syncopation)
            if swing is not None:
                group.swing_acc.add(swing)
            group.groove_bias_acc.add(groove_bias)
            group.groove_looseness_acc.add(groove_looseness)
            group.velocities.extend(velocities)
            group.accent_ratio_acc.add(accent_ratio)
            if dynamic_slope is not None:
                group.dynamic_contour_acc.add(dynamic_slope)
            group.durations_beats.extend(durations_beats)
            group.gate_ratios.extend(gate_ratios)
            group.activity_ratio_acc.add(activity)
            group.total_note_count += len(notes)
            group.track_count += 1
            group.source_file_ids.add(source_file_id)
            group.evidence_ids.add(evidence_id)
            group.source_kinds["REAL"] += 1

        active_channels = sorted(channel_intervals)
        for channel_a, channel_b in combinations(active_channels, 2):
            co_activity = compute_co_activity(channel_intervals[channel_a], channel_intervals[channel_b])
            pair_group = pair_groups.setdefault(
                (style_section, channel_a, channel_b),
                _PairGroup(style_section=style_section, channel_a=channel_a, channel_b=channel_b),
            )
            pair_group.co_activity_acc.add(co_activity)
            pair_group.pair_instance_count += 1
            pair_group.source_file_ids.add(source_file_id)
            pair_group.evidence_ids.add(evidence_id)
            pair_group.source_kinds["REAL"] += 1

    now = datetime.now(timezone.utc).isoformat()
    records: list[FactoryDNARecord] = []
    for group in note_groups.values():
        if len(group.source_file_ids) >= MIN_GROUP_SOURCE_FILES:
            records.extend(_finalize_note_group(group, now))
    for pair_group in pair_groups.values():
        if len(pair_group.source_file_ids) >= MIN_GROUP_SOURCE_FILES:
            records.append(_finalize_pair_group(pair_group, now))
    return records


def run_full_extraction(evidence_conn: sqlite3.Connection) -> list[FactoryDNARecord]:
    """Run both passes against ``evidence_conn`` and return every
    FactoryDNARecord produced. Does not touch knowledge.db -- see
    ``extract_and_save`` for the write step.
    """
    records = _cheap_pass(evidence_conn)
    records.extend(_expensive_pass(evidence_conn))
    return records


def extract_and_save(evidence_conn: sqlite3.Connection, knowledge_conn: sqlite3.Connection) -> int:
    """Run full extraction against ``evidence_conn`` and replace
    knowledge.db's factory_dna table (via ``knowledge_conn``) with the
    result. Returns the number of rows written.
    """
    records = run_full_extraction(evidence_conn)
    save_factory_dna(knowledge_conn, records)
    return len(records)


if __name__ == "__main__":
    from ..infrastructure.database import connection as db_connection
    from ..infrastructure.database.schema import KNOWLEDGE_DB_DDL, KNOWLEDGE_DB_SCHEMA_VERSION

    evidence_connection = db_connection.get_connection(config.EVIDENCE_DB_PATH)
    knowledge_connection = db_connection.get_connection(config.KNOWLEDGE_DB_PATH)
    db_connection.ensure_schema(
        knowledge_connection, KNOWLEDGE_DB_DDL, schema_version=KNOWLEDGE_DB_SCHEMA_VERSION
    )

    row_count = extract_and_save(evidence_connection, knowledge_connection)
    print(f"factory_dna: wrote {row_count} rows")

    evidence_connection.close()
    knowledge_connection.close()
