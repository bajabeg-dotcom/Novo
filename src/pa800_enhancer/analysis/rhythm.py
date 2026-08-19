from collections import Counter
from dataclasses import dataclass

from ..domain.song import Song
from ..profiles.builtin_rhythms import RHYTHM_PROFILES


@dataclass(frozen=True, slots=True)
class RhythmCandidate:
    profile_id: str
    score: float
    reason: str


class RhythmDetector:
    """Conservative meter/onset detector that never applies a profile itself."""

    def rank(self, song: Song) -> list[RhythmCandidate]:
        meters = {
            tuple(event.data[:2])
            for track in song.tracks
            for event in track.events
            if event.meta_type == 0x58 and len(event.data) >= 2
        }
        ppq = song.header.ppq
        drum_onsets: list[int] = []
        if ppq:
            drum_onsets = [
                event.absolute_tick
                for track in song.tracks
                for event in track.events
                if event.channel == 10 and event.is_note_on
            ]
        candidates: list[RhythmCandidate] = []
        for profile in RHYTHM_PROFILES.values():
            matched = any((num, denominator.bit_length() - 1) in meters for num, denominator in profile.meters)
            score = 0.45 if matched else 0.0
            reasons = ["meter match"] if matched else []
            if ppq and drum_onsets and profile.profile_id == "disco":
                quarter_slots = Counter((tick // ppq) % 4 for tick in drum_onsets)
                if len(quarter_slots) == 4 and min(quarter_slots.values()) > 0:
                    score += 0.15
                    reasons.append("drum events cover all quarter-note positions")
            if not reasons:
                reasons.append("insufficient evidence")
            candidates.append(RhythmCandidate(profile.profile_id, min(score, 1.0), "; ".join(reasons)))
        return sorted(candidates, key=lambda item: (-item.score, item.profile_id))
