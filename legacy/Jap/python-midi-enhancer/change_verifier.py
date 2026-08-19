"""Independent byte/event verifier for in-memory Change Engine results.

The verifier reparses original and working bytes, independently locates every
approved event field, compares the complete byte diff and blocks save on any
unexpected difference. It does not call Change Engine offset helpers.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from change_engine import ChangeExecutionResult, ChangeExecutionStatus
from change_plan import ChangePlan, EventMutation, MutationField, PlanState
from style_loader import MidiEvent, MidiFileModel, StandardMidiLoader


class VerificationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    status: VerificationStatus
    plan_id: str
    source_sha256: str
    output_sha256: str
    expected_mutation_count: int
    actual_changed_byte_count: int
    changed_byte_offsets: tuple[int, ...]
    verified_mutation_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    verified_bytes: bytes | None
    save_authorized: bool


class IndependentChangeVerifier:
    """Reparse and prove that only approved exact event data bytes changed."""

    def verify(
        self,
        *,
        plan: ChangePlan,
        result: ChangeExecutionResult,
    ) -> VerificationResult:
        reasons: list[str] = []
        if plan.state is not PlanState.APPROVED:
            reasons.append("Plan is not fully USER-approved.")
        if result.status is not ChangeExecutionStatus.PENDING_VERIFICATION:
            reasons.append("Change result is not pending verification.")
        if result.plan_id != plan.plan_id or result.request.plan_id != plan.plan_id:
            reasons.append("Plan/result/request ID mismatch.")
        if result.verified or result.save_authorized:
            reasons.append("Engine result must not self-declare verification or save authorization.")
        source_hash = hashlib.sha256(result.original_bytes).hexdigest()
        output_hash = hashlib.sha256(result.working_bytes).hexdigest()
        if source_hash != plan.source_sha256 or source_hash != result.source_sha256:
            reasons.append("Original/source SHA-256 mismatch.")
        if output_hash != result.output_sha256:
            reasons.append("Working output SHA-256 mismatch.")

        try:
            original = StandardMidiLoader().load_bytes(
                result.original_bytes, source_name="<verify-original>"
            )
            output = StandardMidiLoader().load_bytes(
                result.working_bytes, source_name="<verify-output>"
            )
        except Exception as exc:
            reasons.append(f"Output reparse failed: {type(exc).__name__}: {exc}")
            return self._result(plan, result, (), (), reasons)

        self._compare_structure(original, output, reasons)
        original_events = _event_map(original)
        output_events = _event_map(output)
        expected_mutations = tuple(
            mutation for proposal in plan.proposals for mutation in proposal.mutations
        )
        rule_by_mutation = {
            mutation.mutation_id: proposal.rule_id
            for proposal in plan.proposals
            for mutation in proposal.mutations
        }
        if len(expected_mutations) != plan.expected_mutation_count:
            reasons.append("Plan mutation count is internally inconsistent.")
        if len(result.applied_mutations) != len(expected_mutations):
            reasons.append("Engine applied mutation count mismatch.")

        original_offsets = _track_body_offsets(result.original_bytes, original)
        expected_by_offset: dict[int, EventMutation] = {}
        expected_by_event: dict[tuple[int, int], dict[MutationField, EventMutation]] = {}
        verified_ids: list[str] = []
        for mutation in expected_mutations:
            source_event = original_events.get(mutation.event_ref)
            output_event = output_events.get(mutation.event_ref)
            if source_event is None or output_event is None:
                reasons.append(f"Missing parsed event for {mutation.mutation_id}.")
                continue
            source_errors = mutation.verify_event(source_event)
            if source_errors:
                reasons.append(
                    f"Original event mismatch for {mutation.mutation_id}: {', '.join(source_errors)}."
                )
            self._verify_specialized_authorization(
                source_event,
                mutation,
                rule_by_mutation[mutation.mutation_id],
                result,
                reasons,
            )
            if len(output_event.data) <= mutation.field.index:
                reasons.append(f"Output event lacks field for {mutation.mutation_id}.")
                continue
            if output_event.data[mutation.field.index] != mutation.new_value:
                reasons.append(f"Output new value mismatch for {mutation.mutation_id}.")
            local_offset = _event_data_offset(source_event, mutation.field)
            absolute_offset = (
                original_offsets[source_event.track_index]
                + source_event.byte_start
                + local_offset
            )
            if absolute_offset in expected_by_offset:
                reasons.append("Two approved mutations map to the same absolute byte.")
            expected_by_offset[absolute_offset] = mutation
            expected_by_event.setdefault(mutation.event_ref, {})[mutation.field] = mutation
            verified_ids.append(mutation.mutation_id)

        actual_offsets = tuple(
            index
            for index, (old, new) in enumerate(
                zip(result.original_bytes, result.working_bytes, strict=True)
            )
            if old != new
        ) if len(result.original_bytes) == len(result.working_bytes) else ()
        if len(result.original_bytes) != len(result.working_bytes):
            reasons.append("Working byte length differs from original.")
        if set(actual_offsets) != set(expected_by_offset):
            unexpected = sorted(set(actual_offsets) - set(expected_by_offset))
            missing = sorted(set(expected_by_offset) - set(actual_offsets))
            if unexpected:
                reasons.append(f"Unexpected changed byte offsets: {unexpected}.")
            if missing:
                reasons.append(f"Approved byte offsets did not change: {missing}.")
        for offset, mutation in expected_by_offset.items():
            if offset >= len(result.working_bytes):
                reasons.append(f"Approved offset outside output for {mutation.mutation_id}.")
                continue
            if result.original_bytes[offset] != mutation.old_value:
                reasons.append(f"Original byte mismatch at offset {offset}.")
            if result.working_bytes[offset] != mutation.new_value:
                reasons.append(f"Output byte mismatch at offset {offset}.")

        applied_by_id = {item.mutation_id: item for item in result.applied_mutations}
        if len(applied_by_id) != len(result.applied_mutations):
            reasons.append("Duplicate applied mutation IDs.")
        for offset, mutation in expected_by_offset.items():
            applied = applied_by_id.get(mutation.mutation_id)
            if applied is None:
                reasons.append(f"Missing applied record for {mutation.mutation_id}.")
            elif (
                applied.absolute_byte_offset != offset
                or applied.old_value != mutation.old_value
                or applied.new_value != mutation.new_value
                or applied.event_ref != mutation.event_ref
                or applied.field is not mutation.field
            ):
                reasons.append(f"Applied record mismatch for {mutation.mutation_id}.")

        self._compare_events(
            original_events,
            output_events,
            expected_by_event,
            reasons,
        )
        status = VerificationStatus.FAIL if reasons else VerificationStatus.PASS
        return VerificationResult(
            status=status,
            plan_id=plan.plan_id,
            source_sha256=source_hash,
            output_sha256=output_hash,
            expected_mutation_count=len(expected_mutations),
            actual_changed_byte_count=len(actual_offsets),
            changed_byte_offsets=actual_offsets,
            verified_mutation_ids=tuple(sorted(verified_ids)),
            reasons=tuple(reasons),
            verified_bytes=result.working_bytes if status is VerificationStatus.PASS else None,
            save_authorized=status is VerificationStatus.PASS,
        )

    @staticmethod
    def _verify_specialized_authorization(
        event: MidiEvent,
        mutation: EventMutation,
        rule_id: str,
        result: ChangeExecutionResult,
        reasons: list[str],
    ) -> None:
        if event.kind != "note_on" or mutation.field is not MutationField.DATA_1:
            return
        request = result.request
        if rule_id != "S01.PROFILE_VELOCITY_OUTLIER":
            reasons.append(f"{mutation.mutation_id}: Note On rule is not S01.")
        if rule_id not in request.authorized_rule_ids:
            reasons.append(f"{mutation.mutation_id}: S01 rule authorization missing.")
        if (
            "UNKNOWN_VELOCITY_SWITCH_RX_THRESHOLDS"
            not in request.risk_acknowledgements
        ):
            reasons.append(f"{mutation.mutation_id}: velocity-switch/RX acknowledgement missing.")
        if not event.is_note_on or mutation.old_value == 0 or mutation.new_value == 0:
            reasons.append(f"{mutation.mutation_id}: Note On zero/off semantics changed.")
        if abs(mutation.new_value - mutation.old_value) > 8:
            reasons.append(f"{mutation.mutation_id}: S01 adjustment exceeds 8 units.")

    @staticmethod
    def _compare_structure(
        original: MidiFileModel,
        output: MidiFileModel,
        reasons: list[str],
    ) -> None:
        fields = (
            "format", "declared_track_count", "division", "ticks_per_beat",
            "smpte", "header_extra", "trailing_bytes",
        )
        for field in fields:
            if getattr(original, field) != getattr(output, field):
                reasons.append(f"MIDI structure field changed: {field}.")
        if len(original.tracks) != len(output.tracks):
            reasons.append("Parsed track count changed.")
            return
        for left, right in zip(original.tracks, output.tracks, strict=True):
            if left.index != right.index or left.end_tick != right.end_tick:
                reasons.append(f"Track structure changed for track {left.index}.")
            if len(left.events) != len(right.events):
                reasons.append(f"Event count changed for track {left.index}.")

    @staticmethod
    def _compare_events(
        original: dict[tuple[int, int], MidiEvent],
        output: dict[tuple[int, int], MidiEvent],
        expected: dict[tuple[int, int], dict[MutationField, EventMutation]],
        reasons: list[str],
    ) -> None:
        if set(original) != set(output):
            reasons.append("Parsed event reference set changed.")
            return
        immutable_fields = (
            "track_index", "event_index", "delta_tick", "absolute_tick", "kind",
            "status", "status_explicit", "channel", "meta_type", "payload",
            "byte_start", "byte_end",
        )
        for ref in sorted(original):
            left = original[ref]
            right = output[ref]
            for field in immutable_fields:
                if getattr(left, field) != getattr(right, field):
                    reasons.append(f"Event {ref} immutable field changed: {field}.")
            event_mutations = expected.get(ref, {})
            if len(left.data) != len(right.data):
                reasons.append(f"Event {ref} data length changed.")
                continue
            for index, (old, new) in enumerate(zip(left.data, right.data, strict=True)):
                field = MutationField.DATA_0 if index == 0 else MutationField.DATA_1
                mutation = event_mutations.get(field)
                expected_value = mutation.new_value if mutation else old
                if new != expected_value:
                    reasons.append(f"Event {ref} unexpected {field.value} value.")
            if not event_mutations and left.raw != right.raw:
                reasons.append(f"Unapproved raw event changed: {ref}.")

    @staticmethod
    def _result(
        plan: ChangePlan,
        result: ChangeExecutionResult,
        offsets: tuple[int, ...],
        verified_ids: tuple[str, ...],
        reasons: list[str],
    ) -> VerificationResult:
        return VerificationResult(
            status=VerificationStatus.FAIL,
            plan_id=plan.plan_id,
            source_sha256=hashlib.sha256(result.original_bytes).hexdigest(),
            output_sha256=hashlib.sha256(result.working_bytes).hexdigest(),
            expected_mutation_count=plan.expected_mutation_count,
            actual_changed_byte_count=len(offsets),
            changed_byte_offsets=offsets,
            verified_mutation_ids=verified_ids,
            reasons=tuple(reasons),
            verified_bytes=None,
            save_authorized=False,
        )


def _event_map(model: MidiFileModel) -> dict[tuple[int, int], MidiEvent]:
    return {
        (event.track_index, event.event_index): event
        for track in model.tracks
        for event in track.events
    }


def _track_body_offsets(source: bytes, model: MidiFileModel) -> tuple[int, ...]:
    if source[:4] != b"MThd" or len(source) < 14:
        raise ValueError("invalid source header")
    header_length = int.from_bytes(source[4:8], "big")
    offset = 8 + header_length
    results: list[int] = []
    for _ in range(model.declared_track_count):
        if source[offset:offset + 4] != b"MTrk":
            raise ValueError("missing MTrk")
        length = int.from_bytes(source[offset + 4:offset + 8], "big")
        body_start = offset + 8
        results.append(body_start)
        offset = body_start + length
    return tuple(results)


def _event_data_offset(event: MidiEvent, field: MutationField) -> int:
    offset = 0
    for _ in range(4):
        value = event.raw[offset]
        offset += 1
        if value & 0x80 == 0:
            break
    else:
        raise ValueError("invalid event delta VLQ")
    if event.status_explicit:
        if event.raw[offset] != event.status:
            raise ValueError("status mismatch")
        offset += 1
    return offset + field.index
