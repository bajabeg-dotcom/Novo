"""In-memory byte-preserving Change Engine with explicit rollback.

The engine consumes an approved immutable Change Plan plus a separate USER
execution request. It patches only exact channel-event data bytes in a working
copy and returns PENDING_VERIFICATION. It never writes a file and never marks
its own output as verified.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from change_plan import (
    ChangePlan,
    EventMutation,
    MutationField,
    PlanState,
)
from style_loader import MidiEvent, MidiFileModel, StandardMidiLoader


class ChangeExecutionError(ValueError):
    """Raised when an approved plan cannot be executed safely."""


class ChangeExecutionStatus(str, Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(frozen=True, slots=True)
class ChangeExecutionRequest:
    request_id: str
    plan_id: str
    source_sha256: str
    approved_proposal_ids: tuple[str, ...]
    requested_at: str
    actor: str
    authorized_rule_ids: tuple[str, ...] = ()
    risk_acknowledgements: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AppliedMutation:
    mutation_id: str
    proposal_id: str
    event_ref: tuple[int, int]
    field: MutationField
    absolute_byte_offset: int
    old_value: int
    new_value: int


@dataclass(frozen=True, slots=True)
class ChangeExecutionResult:
    request: ChangeExecutionRequest
    plan_id: str
    source_sha256: str
    output_sha256: str
    original_bytes: bytes
    working_bytes: bytes
    applied_mutations: tuple[AppliedMutation, ...]
    status: ChangeExecutionStatus
    original_preserved: bool
    verified: bool = False
    save_authorized: bool = False

    def rollback(self) -> "ChangeExecutionResult":
        return ChangeExecutionResult(
            request=self.request,
            plan_id=self.plan_id,
            source_sha256=self.source_sha256,
            output_sha256=self.source_sha256,
            original_bytes=self.original_bytes,
            working_bytes=self.original_bytes,
            applied_mutations=(),
            status=ChangeExecutionStatus.ROLLED_BACK,
            original_preserved=True,
            verified=False,
            save_authorized=False,
        )


def create_execution_request(
    plan: ChangePlan,
    *,
    requested_at: str,
    actor: str = "USER",
    authorized_rule_ids: tuple[str, ...] = (),
    risk_acknowledgements: tuple[str, ...] = (),
) -> ChangeExecutionRequest:
    if actor != "USER":
        raise ChangeExecutionError("Change execution request actor must be USER")
    if plan.state is not PlanState.APPROVED:
        raise ChangeExecutionError("Change execution requires a fully approved plan")
    _validate_timestamp(requested_at)
    approved = plan.approved_proposal_ids
    if approved != tuple(sorted(item.proposal_id for item in plan.proposals)):
        raise ChangeExecutionError("approved proposal set does not match the plan")
    if len(authorized_rule_ids) != len(set(authorized_rule_ids)):
        raise ChangeExecutionError("duplicate authorized rule ID")
    plan_rule_ids = {item.rule_id for item in plan.proposals}
    if not set(authorized_rule_ids).issubset(plan_rule_ids):
        raise ChangeExecutionError("execution authorizes a rule not present in plan")
    if len(risk_acknowledgements) != len(set(risk_acknowledgements)) or any(
        not item.strip() for item in risk_acknowledgements
    ):
        raise ChangeExecutionError("invalid risk acknowledgement set")
    payload = {
        "plan_id": plan.plan_id,
        "source_sha256": plan.source_sha256,
        "approved_proposal_ids": list(approved),
        "requested_at": requested_at,
        "actor": actor,
        "authorized_rule_ids": list(authorized_rule_ids),
        "risk_acknowledgements": list(risk_acknowledgements),
    }
    request_id = "EXEC-" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20].upper()
    return ChangeExecutionRequest(
        request_id=request_id,
        plan_id=plan.plan_id,
        source_sha256=plan.source_sha256,
        approved_proposal_ids=approved,
        requested_at=requested_at,
        actor=actor,
        authorized_rule_ids=authorized_rule_ids,
        risk_acknowledgements=risk_acknowledgements,
    )


class BytePreservingChangeEngine:
    """Patch exact existing MIDI data bytes in memory; do not save or verify."""

    def execute(
        self,
        *,
        plan: ChangePlan,
        request: ChangeExecutionRequest,
        source_bytes: bytes,
    ) -> ChangeExecutionResult:
        if plan.state is not PlanState.APPROVED:
            raise ChangeExecutionError("plan is not fully USER-approved")
        if request.actor != "USER":
            raise ChangeExecutionError("execution request actor is not USER")
        if request.plan_id != plan.plan_id or request.source_sha256 != plan.source_sha256:
            raise ChangeExecutionError("execution request does not match plan/source")
        if request.approved_proposal_ids != plan.approved_proposal_ids:
            raise ChangeExecutionError("execution request approval set mismatch")
        source_hash = hashlib.sha256(source_bytes).hexdigest()
        if source_hash != plan.source_sha256:
            raise ChangeExecutionError("source bytes SHA-256 does not match Change Plan")

        model = StandardMidiLoader().load_bytes(source_bytes, source_name="<change-source>")
        event_map = _event_map(model)
        body_offsets = _track_body_offsets(source_bytes, model)
        working = bytearray(source_bytes)
        applied: list[AppliedMutation] = []
        used_offsets: set[int] = set()

        proposal_by_mutation = {
            mutation.mutation_id: proposal.proposal_id
            for proposal in plan.proposals
            for mutation in proposal.mutations
        }
        s01_mutation_count = sum(
            len(proposal.mutations)
            for proposal in plan.proposals
            if proposal.rule_id == "S01.PROFILE_VELOCITY_OUTLIER"
        )
        if s01_mutation_count > 32:
            raise ChangeExecutionError("S01 execution exceeds 32 Note On mutations")
        for proposal in plan.proposals:
            for mutation in proposal.mutations:
                event = event_map.get(mutation.event_ref)
                if event is None:
                    raise ChangeExecutionError(f"missing source event {mutation.event_ref}")
                errors = mutation.verify_event(event)
                if errors:
                    raise ChangeExecutionError(
                        f"source event mismatch for {mutation.mutation_id}: {', '.join(errors)}"
                    )
                self._validate_supported_mutation(
                    event, mutation, proposal.rule_id, request
                )
                data_offset = _event_data_offset(event, mutation.field)
                absolute_offset = (
                    body_offsets[event.track_index] + event.byte_start + data_offset
                )
                if absolute_offset in used_offsets:
                    raise ChangeExecutionError("multiple mutations target the same source byte")
                if working[absolute_offset] != mutation.old_value:
                    raise ChangeExecutionError("source byte does not match expected old value")
                working[absolute_offset] = mutation.new_value
                used_offsets.add(absolute_offset)
                applied.append(AppliedMutation(
                    mutation_id=mutation.mutation_id,
                    proposal_id=proposal_by_mutation[mutation.mutation_id],
                    event_ref=mutation.event_ref,
                    field=mutation.field,
                    absolute_byte_offset=absolute_offset,
                    old_value=mutation.old_value,
                    new_value=mutation.new_value,
                ))

        if len(applied) != plan.expected_mutation_count:
            raise ChangeExecutionError("applied mutation count mismatch")
        output = bytes(working)
        output_hash = hashlib.sha256(output).hexdigest()
        if output_hash == source_hash:
            raise ChangeExecutionError("Change Engine produced no byte difference")
        # Structural parse is an engine gate, not independent verification.
        StandardMidiLoader().load_bytes(output, source_name="<change-working-copy>")
        return ChangeExecutionResult(
            request=request,
            plan_id=plan.plan_id,
            source_sha256=source_hash,
            output_sha256=output_hash,
            original_bytes=source_bytes,
            working_bytes=output,
            applied_mutations=tuple(applied),
            status=ChangeExecutionStatus.PENDING_VERIFICATION,
            original_preserved=(hashlib.sha256(source_bytes).hexdigest() == source_hash),
            verified=False,
            save_authorized=False,
        )

    @staticmethod
    def _validate_supported_mutation(
        event: MidiEvent,
        mutation: EventMutation,
        rule_id: str,
        request: ChangeExecutionRequest,
    ) -> None:
        supported = (
            event.kind == "control_change" and mutation.field is MutationField.DATA_1
        ) or (
            event.kind == "program_change" and mutation.field is MutationField.DATA_0
        )
        if supported:
            return
        if event.kind == "note_on" and mutation.field is MutationField.DATA_1:
            if rule_id != "S01.PROFILE_VELOCITY_OUTLIER":
                raise ChangeExecutionError("Note On velocity rule is not S01")
            if rule_id not in request.authorized_rule_ids:
                raise ChangeExecutionError("S01 Note On Apply lacks rule authorization")
            if (
                "UNKNOWN_VELOCITY_SWITCH_RX_THRESHOLDS"
                not in request.risk_acknowledgements
            ):
                raise ChangeExecutionError(
                    "S01 Note On Apply lacks velocity-switch/RX risk acknowledgement"
                )
            if not event.is_note_on or mutation.old_value == 0 or mutation.new_value == 0:
                raise ChangeExecutionError("Note On velocity zero/off semantics cannot be changed")
            if not 1 <= mutation.old_value <= 127 or not 1 <= mutation.new_value <= 127:
                raise ChangeExecutionError("Note On velocity must remain in 1..127")
            if abs(mutation.new_value - mutation.old_value) > 8:
                raise ChangeExecutionError("S01 velocity adjustment exceeds 8 units")
            return
        raise ChangeExecutionError(
            f"first Change Engine scope does not support {event.kind} {mutation.field.value}"
        )


def _event_map(model: MidiFileModel) -> dict[tuple[int, int], MidiEvent]:
    events = {
        (event.track_index, event.event_index): event
        for track in model.tracks
        for event in track.events
    }
    if len(events) != sum(len(track.events) for track in model.tracks):
        raise ChangeExecutionError("duplicate parsed event references")
    return events


def _track_body_offsets(source: bytes, model: MidiFileModel) -> tuple[int, ...]:
    if source[:4] != b"MThd" or len(source) < 14:
        raise ChangeExecutionError("invalid source header while locating track bodies")
    header_length = int.from_bytes(source[4:8], "big")
    offset = 8 + header_length
    results: list[int] = []
    for track_index in range(model.declared_track_count):
        if source[offset:offset + 4] != b"MTrk":
            raise ChangeExecutionError(f"missing MTrk while locating track {track_index}")
        length = int.from_bytes(source[offset + 4:offset + 8], "big")
        body_start = offset + 8
        if body_start + length > len(source):
            raise ChangeExecutionError("track body exceeds source bytes")
        results.append(body_start)
        offset = body_start + length
    return tuple(results)


def _event_data_offset(event: MidiEvent, field: MutationField) -> int:
    raw = event.raw
    offset = 0
    for _ in range(4):
        if offset >= len(raw):
            raise ChangeExecutionError("truncated event delta VLQ")
        value = raw[offset]
        offset += 1
        if value & 0x80 == 0:
            break
    else:
        raise ChangeExecutionError("invalid event delta VLQ")
    if event.status_explicit:
        if offset >= len(raw) or raw[offset] != event.status:
            raise ChangeExecutionError("event status byte mismatch")
        offset += 1
    data_offset = offset + field.index
    if data_offset >= len(raw):
        raise ChangeExecutionError("event data field exceeds raw event")
    return data_offset


def _validate_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ChangeExecutionError("invalid execution request timestamp") from exc
    if parsed.tzinfo is None:
        raise ChangeExecutionError("execution request timestamp requires timezone")
