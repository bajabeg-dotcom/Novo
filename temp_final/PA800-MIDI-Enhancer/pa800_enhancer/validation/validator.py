from ..analysis.notes import pair_notes
from ..domain.song import Song
from .issues import Severity, ValidationIssue


class SongValidator:
    def validate(self, song: Song) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if song.raw_document:
            for chunk in song.raw_document.unknown_chunks:
                issues.append(ValidationIssue("UNKNOWN_CHUNK", f"Unknown chunk {chunk.chunk_id!r} preserved", Severity.INFO))
            if song.raw_document.trailing_span:
                issues.append(ValidationIssue("TRAILING_BYTES", f"{song.raw_document.trailing_span.length} trailing bytes preserved", Severity.WARNING))
        if song.header.format_type == 0 and len(song.tracks) != 1:
            issues.append(ValidationIssue("FORMAT0_TRACKS", "SMF format 0 must contain one track", Severity.CRITICAL))
        if song.header.division == 0:
            issues.append(ValidationIssue("ZERO_DIVISION", "SMF time division cannot be zero", Severity.CRITICAL))
        if song.header.track_count != len(song.tracks):
            issues.append(ValidationIssue("SMF_TRACK_COUNT", "Header track count differs from parsed tracks", Severity.CRITICAL))
        for track in song.tracks:
            previous = -1
            eot_seen = False
            for event in sorted(track.events, key=lambda item: item.order):
                if event.absolute_tick < 0:
                    issues.append(ValidationIssue("NEGATIVE_TICK", "Event has a negative tick", Severity.CRITICAL, track.index, event.absolute_tick))
                if event.absolute_tick < previous:
                    issues.append(ValidationIssue("NON_MONOTONIC", "Track event order is not monotonic", Severity.ERROR, track.index, event.absolute_tick))
                if eot_seen:
                    issues.append(ValidationIssue("EVENT_AFTER_EOT", "Event appears after End of Track", Severity.ERROR, track.index, event.absolute_tick))
                if event.meta_type == 0x2F:
                    eot_seen = True
                    if event.data:
                        issues.append(ValidationIssue("EOT_PAYLOAD", "End of Track must have an empty payload", Severity.ERROR, track.index, event.absolute_tick))
                if event.meta_type == 0x51 and len(event.data) != 3:
                    issues.append(ValidationIssue("TEMPO_LENGTH", "Tempo meta event must contain three bytes", Severity.ERROR, track.index, event.absolute_tick))
                elif event.meta_type == 0x51 and int.from_bytes(event.data, "big") == 0:
                    issues.append(ValidationIssue("TEMPO_ZERO", "Tempo value cannot be zero", Severity.ERROR, track.index, event.absolute_tick))
                if event.meta_type == 0x58 and len(event.data) != 4:
                    issues.append(ValidationIssue("METER_LENGTH", "Time Signature meta event must contain four bytes", Severity.ERROR, track.index, event.absolute_tick))
                elif event.meta_type == 0x58 and (event.data[0] == 0 or event.data[1] > 7):
                    issues.append(ValidationIssue("METER_VALUE", "Time Signature contains an unsupported numerator or denominator", Severity.ERROR, track.index, event.absolute_tick))
                previous = event.absolute_tick
            if not eot_seen:
                issues.append(ValidationIssue("MISSING_EOT", "Track has no End of Track event", Severity.WARNING, track.index, track.end_tick))
        notes, unmatched = pair_notes(song)
        for event in unmatched:
            issues.append(ValidationIssue("UNPAIRED_NOTE", f"Unpaired note event {event.event_id}", Severity.WARNING, event.track_index, event.absolute_tick))
        for note in notes:
            if note.end_tick <= note.start_tick:
                issues.append(ValidationIssue("NOTE_NON_POSITIVE_DURATION", f"Note {note.note} on channel {note.channel} has non-positive key duration", Severity.ERROR, tick=note.start_tick))
            if note.ambiguous_pairing:
                issues.append(ValidationIssue("AMBIGUOUS_NOTE_PAIR", f"Overlapping note {note.note} on channel {note.channel} has ambiguous pairing", Severity.WARNING, tick=note.start_tick))
            if note.sustained_to_end:
                issues.append(ValidationIssue("SUSTAIN_HELD_AT_END", f"Sustain remains active for note {note.note} on channel {note.channel}", Severity.WARNING, tick=note.end_tick))
        return issues