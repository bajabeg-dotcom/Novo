"""K03 user-selected Factory Sound replacement proposal builder.

K03 creates only an immutable Suggest-phase Change Plan. It never inserts an
event, mutates MIDI bytes, or authorizes Apply. Bank changes are proposed only
when the exact Bank Select events belong exclusively to the selected M10
segment and occur at its Program Change boundary.
"""

from __future__ import annotations

from collections import Counter

from change_plan import (
    ChangePlan,
    EvidenceReference,
    EvidenceStatus,
    EventMutation,
    InputMeasurement,
    MutationField,
    RiskLevel,
    create_proposal,
)
from instrument_identity_resolver import (
    IdentityResolutionResult,
    IdentityStatus,
    ResolvedInstrumentIdentity,
)
from instrument_segmenter import AddressStatus, InstrumentSegment, SegmentationResult
from pa800_registry import FactoryEntry, Pa800FactoryRegistry, load_factory_registry
from policy_engine import PolicyEngine, PolicyError, PolicyRule
from style_loader import MidiEvent


class K03ProposalError(ValueError):
    """Raised when a safe exact-event K03 proposal cannot be created."""


K03_RULE = PolicyRule(
    rule_id="K03.USER_SELECTED_FACTORY_REPLACEMENT",
    version="1.0.0",
    description=(
        "Allow an explicitly user-selected exact K01 target to enter Suggest mode "
        "through exclusive existing CC00/CC32/Program Change events."
    ),
    allowed_event_kinds=("control_change", "program_change"),
    allowed_fields=(MutationField.DATA_0, MutationField.DATA_1),
    maximum_risk=RiskLevel.HIGH,
    allow_inferred_evidence=False,
)


class K03SoundReplacementBuilder:
    """Build an exact, policy-checked K03 Suggest plan without applying it."""

    def __init__(
        self,
        registry: Pa800FactoryRegistry | None = None,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        self.registry = registry or load_factory_registry()
        self.policy_engine = policy_engine or PolicyEngine((K03_RULE,))

    def build_plan(
        self,
        *,
        segmentation: SegmentationResult,
        identities: IdentityResolutionResult,
        events: tuple[MidiEvent, ...],
        segment_ordinal: int,
        target_address: str,
        user_selected: bool,
    ) -> ChangePlan:
        if not user_selected:
            raise K03ProposalError("K03 target must be explicitly selected by USER")
        if identities.original_result is not segmentation:
            raise K03ProposalError("K02 result does not reference the supplied M10 result")
        if identities.source_sha256 != segmentation.source_sha256:
            raise K03ProposalError("K02/M10 source SHA-256 mismatch")
        segment = self._segment(segmentation, segment_ordinal)
        identity = self._identity(identities, segment_ordinal)
        if identity.original_segment is not segment:
            raise K03ProposalError("K02 identity does not reference the selected M10 segment")
        if segment.address.status is not AddressStatus.COMPLETE or segment.address.value is None:
            raise K03ProposalError("K03 requires a complete M10 CC00.CC32.PC address")
        if identity.status not in {
            IdentityStatus.FACTORY_CONFIRMED,
            IdentityStatus.USER_SLOT_CONFIRMED,
        }:
            raise K03ProposalError(
                f"K03 first scope blocks identity status {identity.status.value}"
            )

        target = self.registry.lookup_address(target_address)
        if target is None:
            raise K03ProposalError("K03 target must be an exact K01 Factory address")
        self._validate_kind(identity, target)
        requested = segment.address.value
        if requested == target.address:
            raise K03ProposalError("K03 target equals the requested source address")

        event_map = {
            (event.track_index, event.event_index): event for event in events
        }
        if len(event_map) != len(events):
            raise K03ProposalError("duplicate event references in source event set")
        selection_events = []
        for ref in segment.selection_event_refs:
            event = event_map.get(ref)
            if event is None:
                raise K03ProposalError(f"missing M10 selection event: {ref}")
            selection_events.append(event)
        program_events = [event for event in selection_events if event.kind == "program_change"]
        if len(program_events) != 1:
            raise K03ProposalError("selected segment must have exactly one Program Change event")
        program_event = program_events[0]
        if program_event.absolute_tick != segment.start_tick:
            raise K03ProposalError("Program Change event does not match M10 segment boundary")

        controller_events: dict[int, MidiEvent] = {}
        for event in selection_events:
            if event.kind == "control_change" and len(event.data) == 2 and event.data[0] in (0, 32):
                controller = int(event.data[0])
                if controller in controller_events:
                    raise K03ProposalError(f"multiple CC{controller} selection events")
                controller_events[controller] = event

        current = (
            int(segment.address.bank_msb),
            int(segment.address.bank_lsb),
            int(segment.address.program),
        )
        target_values = (target.cc00, target.cc32, target.pc)
        shared_refs = Counter(
            ref for item in segmentation.segments for ref in item.selection_event_refs
        )
        mutations: list[EventMutation] = []

        for controller, current_value, new_value in (
            (0, current[0], target_values[0]),
            (32, current[1], target_values[1]),
        ):
            if current_value == new_value:
                continue
            event = controller_events.get(controller)
            if event is None:
                raise K03ProposalError(
                    f"CC{controller} change would require event insertion; first K03 scope forbids insertion"
                )
            ref = (event.track_index, event.event_index)
            if shared_refs[ref] != 1:
                raise K03ProposalError(
                    f"CC{controller} selection event is shared by multiple M10 segments"
                )
            if event.absolute_tick != segment.start_tick:
                raise K03ProposalError(
                    f"CC{controller} event is inherited from another boundary"
                )
            mutations.append(EventMutation.from_event(event, MutationField.DATA_1, new_value))

        if current[2] != target_values[2]:
            mutations.append(
                EventMutation.from_event(program_event, MutationField.DATA_0, target_values[2])
            )
        if not mutations:
            raise K03ProposalError("K03 proposal has no exact event differences")
        mutations.sort(key=lambda item: (item.event_ref, item.field.value))

        risk = (
            RiskLevel.HIGH
            if identity.status is IdentityStatus.USER_SLOT_CONFIRMED
            else RiskLevel.MEDIUM
        )
        evidence = (
            EvidenceReference(
                source_id="K01",
                status=EvidenceStatus.CONFIRMED,
                detail=f"User-selected target {target.address} — {target.name}",
                path="prism-uploads/Pa800-201UM-ENG.pdf",
                printed_pages=target.printed_pages,
                pdf_pages=target.pdf_pages,
            ),
            EvidenceReference(
                source_id="K02",
                status=EvidenceStatus.CONFIRMED,
                detail=(
                    f"Selected M10 segment {segment.ordinal} identity status "
                    f"{identity.status.value}"
                ),
            ),
            EvidenceReference(
                source_id="USER_SELECTION",
                status=EvidenceStatus.CONFIRMED,
                detail="Target Factory address was explicitly selected by USER.",
            ),
        )
        measurements = (
            InputMeasurement("segment_ordinal", segment.ordinal, None, EvidenceStatus.CONFIRMED),
            InputMeasurement("channel", segment.channel, "MIDI_CHANNEL_1_BASED", EvidenceStatus.CONFIRMED),
            InputMeasurement("start_tick", segment.start_tick, "TICK", EvidenceStatus.CONFIRMED),
            InputMeasurement("end_tick", segment.end_tick, "TICK", EvidenceStatus.CONFIRMED),
            InputMeasurement("note_on_count", segment.note_on_count, "EVENTS", EvidenceStatus.DERIVED),
            InputMeasurement("identity_status", identity.status.value, None, EvidenceStatus.CONFIRMED),
            InputMeasurement("requested_address", requested, "CC00.CC32.PC", EvidenceStatus.CONFIRMED),
            InputMeasurement("target_address", target.address, "CC00.CC32.PC", EvidenceStatus.CONFIRMED),
        )
        mutation_text = ", ".join(
            f"{item.event_ref}:{item.field.value} {item.old_value}->{item.new_value}"
            for item in mutations
        )
        proposal = create_proposal(
            source_sha256=segmentation.source_sha256,
            rule_id=K03_RULE.rule_id,
            rule_version=K03_RULE.version,
            title=f"Replace segment {segment.ordinal} Sound with {target.address} — {target.name}",
            description=(
                "User-selected Factory replacement over existing exclusive selection events only."
            ),
            evidence_status=EvidenceStatus.CONFIRMED,
            confidence_percent=None,
            risk=risk,
            input_measurements=measurements,
            evidence=evidence,
            mutations=tuple(mutations),
            expected_difference=mutation_text,
            protections=(
                "Only listed CC00/CC32/Program Change fields may differ.",
                "Notes, velocity, timing, controllers, SysEx, meta and other segments remain unchanged.",
                "Plan remains Suggest-only; Change Engine and Verifier are required for Apply.",
            ),
        )
        try:
            return self.policy_engine.build_plan(
                source_sha256=segmentation.source_sha256,
                proposals=(proposal,),
                events=event_map,
            )
        except PolicyError as exc:
            raise K03ProposalError(str(exc)) from exc

    @staticmethod
    def _segment(result: SegmentationResult, ordinal: int) -> InstrumentSegment:
        matches = [item for item in result.segments if item.ordinal == ordinal]
        if len(matches) != 1:
            raise K03ProposalError(f"unknown or duplicate M10 segment ordinal: {ordinal}")
        return matches[0]

    @staticmethod
    def _identity(
        result: IdentityResolutionResult, ordinal: int
    ) -> ResolvedInstrumentIdentity:
        matches = [item for item in result.identities if item.segment_ordinal == ordinal]
        if len(matches) != 1:
            raise K03ProposalError(f"unknown or duplicate K02 identity ordinal: {ordinal}")
        return matches[0]

    @staticmethod
    def _validate_kind(identity: ResolvedInstrumentIdentity, target: FactoryEntry) -> None:
        if identity.status is IdentityStatus.USER_SLOT_CONFIRMED:
            expected = "FACTORY_DRUM_KIT"
        else:
            expected = identity.item_kind
        if expected not in {"FACTORY_SOUND", "FACTORY_DRUM_KIT"}:
            raise K03ProposalError("selected source segment has no confirmed replaceable item kind")
        if target.kind != expected:
            raise K03ProposalError(
                f"K03 target kind {target.kind} is incompatible with source kind {expected}"
            )
