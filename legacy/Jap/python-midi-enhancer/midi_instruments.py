"""Instrument and musical-role inference for MIDI tracks and channels."""

from __future__ import annotations

from collections import Counter
from typing import Any


GM_PROGRAMS = (
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba", "Xylophone",
    "Tubular Bells", "Dulcimer", "Drawbar Organ", "Percussive Organ", "Rock Organ",
    "Church Organ", "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)",
    "Electric Guitar (clean)", "Electric Guitar (muted)", "Overdriven Guitar",
    "Distortion Guitar", "Guitar Harmonics", "Acoustic Bass", "Electric Bass (finger)",
    "Electric Bass (pick)", "Fretless Bass", "Slap Bass 1", "Slap Bass 2",
    "Synth Bass 1", "Synth Bass 2", "Violin", "Viola", "Cello", "Contrabass",
    "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2",
    "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit", "Trumpet", "Trombone",
    "Tuba", "Muted Trumpet", "French Horn", "Brass Section", "Synth Brass 1",
    "Synth Brass 2", "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe",
    "English Horn", "Bassoon", "Clarinet", "Piccolo", "Flute", "Recorder", "Pan Flute",
    "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina", "Lead 1 (square)",
    "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)", "Lead 5 (charang)",
    "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass + lead)", "Pad 1 (new age)",
    "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)",
    "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)", "FX 1 (rain)",
    "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)", "FX 5 (brightness)",
    "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)", "Sitar", "Banjo", "Shamisen",
    "Koto", "Kalimba", "Bag Pipe", "Fiddle", "Shanai", "Tinkle Bell", "Agogo",
    "Steel Drums", "Woodblock", "Taiko Drum", "Melodic Tom", "Synth Drum",
    "Reverse Cymbal", "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
    "Telephone Ring", "Helicopter", "Applause", "Gunshot",
)

FAMILIES = (
    (0, 7, "Piano", "🎹"), (8, 15, "Chromatic Percussion", "🔔"),
    (16, 23, "Organ", "🎹"), (24, 31, "Guitar", "🎸"),
    (32, 39, "Bass", "🎸"), (40, 47, "Strings", "🎻"),
    (48, 55, "Ensemble", "🎻"), (56, 63, "Brass", "🎺"),
    (64, 71, "Reed", "🎷"), (72, 79, "Pipe", "🪈"),
    (80, 87, "Synth Lead", "🎛"), (88, 95, "Synth Pad", "🎛"),
    (96, 103, "Synth Effects", "✨"), (104, 111, "Ethnic", "🪕"),
    (112, 119, "Percussive", "🥁"), (120, 127, "Sound Effects", "🔊"),
)

NAME_RULES = (
    (("drum", "drums", "kick", "snare", "perc", "udaralj"), "Drums / Percussion", "🥁"),
    (("piano", "keys", "klavir"), "Piano / Keys", "🎹"),
    (("bass", "bas"), "Bass", "🎸"),
    (("guitar", "gitara"), "Guitar", "🎸"),
    (("violin", "viola", "cello", "string", "strings", "gudac"), "Strings", "🎻"),
    (("trumpet", "trombone", "horn", "brass", "truba"), "Brass", "🎺"),
    (("sax", "clarinet", "oboe", "reed"), "Reed", "🎷"),
    (("flute", "recorder", "pipe", "flauta"), "Flute / Pipe", "🪈"),
    (("lead", "melody", "solo", "melod"), "Lead / Melody", "🎵"),
    (("pad", "atmos", "texture"), "Pad / Atmosphere", "🌊"),
    (("choir", "vocal", "voice", "vox"), "Voice / Choir", "🎤"),
)


def family_for_program(program: int) -> tuple[str, str]:
    for low, high, family, icon in FAMILIES:
        if low <= program <= high:
            return family, icon
    return "Unknown", "🎵"


def _name_hint(name: str) -> tuple[str, str] | None:
    lowered = name.casefold()
    for keywords, label, icon in NAME_RULES:
        if any(keyword in lowered for keyword in keywords):
            return label, icon
    return None


def _profile_hint(notes: list[Any], maximum_polyphony: int) -> tuple[str, str, str]:
    if not notes:
        return "Empty", "·", "nema nota"
    pitches = [note.pitch for note in notes]
    average = sum(pitches) / len(pitches)
    durations = [max(0, note.duration_ticks) for note in notes]
    average_duration = sum(durations) / len(durations)
    if average < 48:
        return "Bass role", "🎸", "nizak prosjecni tonski raspon"
    if maximum_polyphony >= 4:
        return "Chordal / accompaniment", "🎹", "visoka polifonija"
    if average >= 72 and maximum_polyphony <= 2:
        return "Lead / melody", "🎵", "visok raspon i niska polifonija"
    if average_duration and max(durations) < average_duration * 2 and maximum_polyphony <= 2:
        return "Rhythmic / motif", "♪", "kratak i ujednacen profil nota"
    return "Melodic instrument", "🎵", "opci tonski i polifoni profil"


def _onset_groups(notes: list[Any]) -> list[list[int]]:
    grouped: dict[int, set[int]] = {}
    for note in notes:
        grouped.setdefault(note.start_tick, set()).add(note.pitch)
    return [sorted(pitches) for _, pitches in sorted(grouped.items())]


def _is_power_chord(pitches: list[int]) -> bool:
    """Recognize root/fifth/octave structures while rejecting major/minor thirds."""
    if len(pitches) < 2:
        return False
    for root in pitches:
        intervals = {(pitch - root) % 12 for pitch in pitches}
        if 7 in intervals and intervals.issubset({0, 7}):
            return True
    return False


def infer_role(
    *, name: str, notes: list[Any], programs: Counter[int], channels: Counter[int],
    maximum_polyphony: int, pitch_bends: int, ticks_per_beat: int,
) -> dict[str, Any]:
    """Classify a musical role using explicit, rhythmic and harmonic evidence."""
    if not notes:
        return {
            "role": "Empty", "role_confidence": 0,
            "role_evidence": ["nema nota"], "role_metrics": {},
        }

    groups = _onset_groups(notes)
    chord_groups = [group for group in groups if len(group) >= 2]
    power_groups = [group for group in chord_groups if _is_power_chord(group)]
    monophonic_ratio = sum(len(group) == 1 for group in groups) / len(groups)
    chord_ratio = len(chord_groups) / len(groups)
    power_ratio = len(power_groups) / len(chord_groups) if chord_groups else 0.0
    average_pitch = sum(note.pitch for note in notes) / len(notes)
    beat_unit = ticks_per_beat or 480
    average_duration_beats = (
        sum(max(0, note.duration_ticks) for note in notes) / len(notes) / beat_unit
    )
    span = max(note.end_tick for note in notes) - min(note.start_tick for note in notes)
    span_beats = max(span / beat_unit, 0.25)
    density = len(notes) / span_beats
    percussion_ratio = channels.get(9, 0) / len(notes)
    guitar_program = any(24 <= program <= 31 for program in programs)
    guitar_name = "guitar" in name.casefold() or "gitara" in name.casefold()
    guitar = guitar_program or guitar_name

    metrics = {
        "monophonic_onset_ratio": round(monophonic_ratio, 3),
        "chord_onset_ratio": round(chord_ratio, 3),
        "power_chord_ratio": round(power_ratio, 3),
        "power_chord_groups": len(power_groups),
        "average_pitch": round(average_pitch, 2),
        "average_duration_beats": round(average_duration_beats, 3),
        "note_density_per_beat": round(density, 3),
        "pitch_bend_events": pitch_bends,
    }

    if percussion_ratio >= 0.5:
        return {
            "role": "Drum / percussion groove", "role_confidence": 98,
            "role_evidence": ["najmanje 50% nota nalazi se na percussion kanalu 10"],
            "role_metrics": metrics,
        }

    if guitar:
        if len(power_groups) >= 2 and power_ratio >= 0.5:
            confidence = min(97, 82 + min(len(power_groups), 5) * 3)
            return {
                "role": "Power-chord guitar", "role_confidence": confidence,
                "role_evidence": [
                    "guitar je potvrđena nazivom ili Program Change porukom",
                    "najmanje dva akordska udara sadrže root–fifth strukturu bez terce",
                    f"power-chord udio među akordskim udarima: {power_ratio:.0%}",
                ],
                "role_metrics": metrics,
            }
        if monophonic_ratio >= 0.75 and maximum_polyphony <= 2 and chord_ratio <= 0.25:
            confidence = 88 if pitch_bends else 80
            evidence = [
                "guitar je potvrđena nazivom ili Program Change porukom",
                f"monofoni udio početaka nota: {monophonic_ratio:.0%}",
                "najveća polifonija nije veća od 2",
            ]
            if pitch_bends:
                evidence.append(f"pitch-bend događaji podržavaju solo interpretaciju: {pitch_bends}")
            return {
                "role": "Solo guitar", "role_confidence": confidence,
                "role_evidence": evidence, "role_metrics": metrics,
            }
        if chord_ratio >= 0.30 or maximum_polyphony >= 3:
            return {
                "role": "Rhythm guitar", "role_confidence": 84,
                "role_evidence": [
                    "guitar je potvrđena nazivom ili Program Change porukom",
                    f"akordski udio početaka nota: {chord_ratio:.0%}",
                    f"najveća polifonija: {maximum_polyphony}",
                ],
                "role_metrics": metrics,
            }
        return {
            "role": "Guitar part (uncertain role)", "role_confidence": 62,
            "role_evidence": ["guitar je potvrđena, ali obrazac nije dovoljno jasan"],
            "role_metrics": metrics,
        }

    if average_pitch < 48 and monophonic_ratio >= 0.65:
        role, confidence, reason = "Bass line", 80, "nizak raspon i pretežno monofona linija"
    elif average_duration_beats >= 2.0 and maximum_polyphony >= 3:
        role, confidence, reason = "Pad / sustained harmony", 78, "duge note i višeglasna tekstura"
    elif chord_ratio >= 0.35 or maximum_polyphony >= 4:
        role, confidence, reason = "Chordal accompaniment", 78, "učestali istodobni akordski počeci"
    elif density >= 2.0 and monophonic_ratio >= 0.75 and average_duration_beats <= 0.75:
        role, confidence, reason = "Arpeggio / fast motif", 74, "gusta monofona mreža kraćih nota"
    elif average_pitch >= 60 and monophonic_ratio >= 0.75:
        role, confidence, reason = "Lead / melody", 74, "viši raspon i pretežno monofona linija"
    else:
        role, confidence, reason = "Melodic / rhythmic part", 58, "mješoviti profil bez dominantnog pravila"
    return {
        "role": role, "role_confidence": confidence,
        "role_evidence": [reason], "role_metrics": metrics,
    }


def infer_instrument(
    *, name: str, notes: list[Any], programs: Counter[int], channels: Counter[int],
    maximum_polyphony: int,
) -> dict[str, Any]:
    """Combine explicit MIDI data and heuristics into an explainable conclusion."""
    evidence: list[str] = []
    scores: Counter[tuple[str, str]] = Counter()

    percussion_notes = channels.get(9, 0)
    if notes and percussion_notes / len(notes) >= 0.5:
        scores[("Drums / Percussion", "🥁")] += 12
        evidence.append("vecina nota koristi standardni percussion kanal 10")

    if programs:
        program, count = programs.most_common(1)[0]
        label = GM_PROGRAMS[program]
        _, icon = family_for_program(program)
        scores[(label, icon)] += 10
        evidence.append(f"Program Change {program + 1}: {label} ({count}x)")

    hint = _name_hint(name)
    if hint:
        scores[hint] += 5
        evidence.append(f"naziv tracka: {name}")

    profile_label, profile_icon, profile_reason = _profile_hint(notes, maximum_polyphony)
    if notes:
        scores[(profile_label, profile_icon)] += 2
        evidence.append(profile_reason)

    if not scores:
        return {
            "instrument": "Empty" if not notes else "Unknown",
            "icon": "·" if not notes else "?",
            "confidence": 0,
            "evidence": evidence or ["nema dovoljno podataka"],
        }

    (instrument, icon), score = scores.most_common(1)[0]
    explicit = bool(programs) or (notes and percussion_notes / len(notes) >= 0.5)
    confidence = min(99, 55 + score * 4) if explicit else min(75, 35 + score * 7)
    return {
        "instrument": instrument,
        "icon": icon,
        "confidence": confidence,
        "evidence": evidence,
        "profile": profile_label,
    }


def build_display_tracks(analyzer: Any) -> list[dict[str, Any]]:
    """Return 16 UI slots without merging independent SMF Format 2 sequences."""
    views: list[dict[str, Any]] = []
    format_zero = analyzer.format == 0
    format_two = analyzer.format == 2

    for slot in range(16):
        if format_zero:
            notes = [note for note in analyzer.notes if note.channel == slot]
            programs = Counter({
                program: count for (track, channel, program), count in analyzer.track_programs.items()
                if channel == slot
            })
            channels = Counter({slot: len(notes)}) if notes else Counter()
            source_index = 0
            title = f"Channel {slot + 1}"
            physical_track = 1
            pitch_bends = analyzer.pitch_bends[slot]
        else:
            notes = [note for note in analyzer.notes if note.track == slot]
            programs = Counter()
            for (track, channel, program), count in analyzer.track_programs.items():
                if track == slot:
                    programs[program] += count
            channels = Counter(note.channel for note in notes)
            source_index = slot
            default_title = f"Sequence {slot + 1}" if format_two else f"Track {slot + 1}"
            title = analyzer.track_names.get(slot, default_title)
            physical_track = slot + 1 if slot < analyzer.track_count else None
            pitch_bends = analyzer.track_pitch_bends[slot]

        maximum_polyphony = analyzer.maximum_polyphony(notes)
        conclusion = infer_instrument(
            name=title,
            notes=notes,
            programs=programs,
            channels=channels,
            maximum_polyphony=maximum_polyphony,
        )
        role = infer_role(
            name=title,
            notes=notes,
            programs=programs,
            channels=channels,
            maximum_polyphony=maximum_polyphony,
            pitch_bends=pitch_bends,
            ticks_per_beat=analyzer.ticks_per_beat or 480,
        )
        if not format_zero and slot < analyzer.track_count and not notes and analyzer.track_meta_counts[slot]:
            conclusion = {
                "instrument": "Conductor / Meta",
                "icon": "⏱",
                "confidence": 99,
                "evidence": ["track sadrzi meta dogadjaje, ali nema nota"],
                "profile": "tempo i struktura",
            }
            role = {
                "role": "Conductor / structure",
                "role_confidence": 99,
                "role_evidence": ["meta događaji bez note događaja"],
                "role_metrics": {},
            }

        pitches = [note.pitch for note in notes]
        velocities = [note.velocity for note in notes]
        views.append({
            "slot": slot + 1,
            "title": title,
            "source": (
                f"Channel {slot + 1}" if format_zero
                else f"Sequence {slot + 1}" if format_two
                else f"Track {slot + 1}"
            ),
            "physical_track": physical_track,
            "notes": len(notes),
            "channels": [channel + 1 for channel in sorted(channels)],
            "pitch_low": min(pitches) if pitches else None,
            "pitch_high": max(pitches) if pitches else None,
            "velocity_min": min(velocities) if velocities else None,
            "velocity_max": max(velocities) if velocities else None,
            "velocity_mean": round(sum(velocities) / len(velocities), 2) if velocities else None,
            "maximum_polyphony": maximum_polyphony,
            **conclusion,
            **role,
        })
    return views