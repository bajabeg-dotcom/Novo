"""Testable backend controller for the bounded GUI K03 workflow.

The Tk layer may display options and ask the user for decisions, but all source
loading, eligibility, planning, execution, verification, save and rollback
rules remain in this module and the underlying tested engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from change_engine import BytePreservingChangeEngine, ChangeExecutionResult, create_execution_request
from change_plan import ChangePlan, UserDecision
from change_verifier import IndependentChangeVerifier, VerificationResult, VerificationStatus
from instrument_identity_resolver import (
    IdentityResolutionResult,
    IdentityStatus,
    InstrumentIdentityResolver,
    ResolvedInstrumentIdentity,
)
from instrument_segmenter import InstrumentSegment, InstrumentSegmenter, SegmentationInput, SegmentationResult
from k03_sound_replacement import K03ProposalError, K03SoundReplacementBuilder
from pa800_registry import FactoryEntry, Pa800FactoryRegistry, load_factory_registry
from style_loader import MidiEvent, MidiFileModel, StandardMidiLoader
from verified_writer import AtomicVerifiedWriter, VerifiedWriteResult, WriteStatus


class GuiWorkflowError(ValueError):
    """Raised when the bounded GUI workflow is invoked out of order or unsafely."""


@dataclass(frozen=True, slots=True)
class GuiSegmentOption:
    ordinal: int
    channel: int
    start_tick: int
    end_tick: int
    requested_address: str
    effective_address: str | None
    official_name: str | None
    item_kind: str
    identity_status: IdentityStatus
    note_on_count: int
    label: str


@dataclass(frozen=True, slots=True)
class GuiTargetOption:
    address: str
    name: str
    kind: str
    printed_pages: tuple[int, ...]
    label: str


@dataclass(frozen=True, slots=True)
class GuiChangePreview:
    segment: GuiSegmentOption
    target: GuiTargetOption
    plan: ChangePlan
    mutation_lines: tuple[str, ...]
    risk: str
    expected_difference: str


class GuiChangeWorkflow:
    """Stateful orchestration for one imported source; no automatic suggestion."""

    def __init__(
        self,
        source_path: str | Path,
        *,
        registry: Pa800FactoryRegistry | None = None,
    ) -> None:
        self.source_path = Path(source_path)
        self.source_bytes = self.source_path.read_bytes()
        self.model: MidiFileModel = StandardMidiLoader().load_path(self.source_path)
        self.events: tuple[MidiEvent, ...] = tuple(
            event for track in self.model.tracks for event in track.events
        )
        end_tick = max(
            (event.absolute_tick + 1 for event in self.events), default=1
        )
        self.segmentation: SegmentationResult = InstrumentSegmenter().segment(
            SegmentationInput(
                source_sha256=self.model.sha256,
                events=self.events,
                ticks_per_beat=self.model.ticks_per_beat,
                window_end_tick=end_tick,
            )
        )
        self.registry = registry or load_factory_registry()
        self.identities: IdentityResolutionResult = InstrumentIdentityResolver(
            self.registry
        ).resolve(self.segmentation)
        self._preview: GuiChangePreview | None = None
        self._approved_plan: ChangePlan | None = None
        self._execution: ChangeExecutionResult | None = None
        self._verification: VerificationResult | None = None
        self._write_result: VerifiedWriteResult | None = None

    @property
    def preview(self) -> GuiChangePreview | None:
        return self._preview

    @property
    def verification(self) -> VerificationResult | None:
        return self._verification

    @property
    def write_result(self) -> VerifiedWriteResult | None:
        return self._write_result

    @property
    def segment_options(self) -> tuple[GuiSegmentOption, ...]:
        options: list[GuiSegmentOption] = []
        by_ordinal = {item.segment_ordinal: item for item in self.identities.identities}
        for segment in self.segmentation.segments:
            identity = by_ordinal[segment.ordinal]
            if identity.status not in {
                IdentityStatus.FACTORY_CONFIRMED,
                IdentityStatus.USER_SLOT_CONFIRMED,
            }:
                continue
            if identity.requested_address is None or identity.item_kind not in {
                "FACTORY_SOUND", "FACTORY_DRUM_KIT", "USER_DRUM_KIT_SLOT",
            }:
                continue
            name = identity.official_name or "User Drum Kit content UNKNOWN"
            label = (
                f"Segment {segment.ordinal} | Ch {segment.channel} | "
                f"{identity.requested_address} — {name} | ticks "
                f"{segment.start_tick}-{segment.end_tick}"
            )
            options.append(GuiSegmentOption(
                ordinal=segment.ordinal,
                channel=segment.channel,
                start_tick=segment.start_tick,
                end_tick=segment.end_tick,
                requested_address=identity.requested_address,
                effective_address=identity.effective_address,
                official_name=identity.official_name,
                item_kind=identity.item_kind,
                identity_status=identity.status,
                note_on_count=segment.note_on_count,
                label=label,
            ))
        return tuple(options)

    def target_options(self, segment_ordinal: int) -> tuple[GuiTargetOption, ...]:
        identity = self._identity(segment_ordinal)
        if identity.status is IdentityStatus.USER_SLOT_CONFIRMED:
            target_kind = "FACTORY_DRUM_KIT"
        elif identity.item_kind in {"FACTORY_SOUND", "FACTORY_DRUM_KIT"}:
            target_kind = identity.item_kind
        else:
            raise GuiWorkflowError("selected segment has no compatible Factory target kind")
        return tuple(
            GuiTargetOption(
                address=entry.address,
                name=entry.name,
                kind=entry.kind,
                printed_pages=entry.printed_pages,
                label=f"{entry.address} — {entry.name}",
            )
            for entry in self.registry.entries
            if entry.kind == target_kind
        )

    def create_preview(
        self,
        *,
        segment_ordinal: int,
        target_address: str,
        user_selected: bool,
    ) -> GuiChangePreview:
        segment_option = self._segment_option(segment_ordinal)
        target_entry = self.registry.lookup_address(target_address)
        if target_entry is None:
            raise GuiWorkflowError("target is not an exact K01 Factory address")
        try:
            plan = K03SoundReplacementBuilder(self.registry).build_plan(
                segmentation=self.segmentation,
                identities=self.identities,
                events=self.events,
                segment_ordinal=segment_ordinal,
                target_address=target_address,
                user_selected=user_selected,
            )
        except K03ProposalError as exc:
            raise GuiWorkflowError(str(exc)) from exc
        target = GuiTargetOption(
            address=target_entry.address,
            name=target_entry.name,
            kind=target_entry.kind,
            printed_pages=target_entry.printed_pages,
            label=f"{target_entry.address} — {target_entry.name}",
        )
        proposal = plan.proposals[0]
        lines = tuple(
            f"track {mutation.event_ref[0] + 1}, event {mutation.event_ref[1]}, "
            f"tick {mutation.absolute_tick}, {mutation.event_kind} "
            f"{mutation.field.value}: {mutation.old_value} -> {mutation.new_value}"
            for mutation in proposal.mutations
        )
        preview = GuiChangePreview(
            segment=segment_option,
            target=target,
            plan=plan,
            mutation_lines=lines,
            risk=proposal.risk.value,
            expected_difference=proposal.expected_difference,
        )
        self._preview = preview
        self._approved_plan = None
        self._execution = None
        self._verification = None
        self._write_result = None
        return preview

    def approve_and_verify(
        self,
        *,
        decision_time: str,
        execution_time: str,
        user_confirmed: bool,
    ) -> VerificationResult:
        if not user_confirmed:
            raise GuiWorkflowError("USER confirmation is required")
        if self._preview is None:
            raise GuiWorkflowError("create a preview before approval")
        proposal_id = self._preview.plan.proposals[0].proposal_id
        plan = self._preview.plan.record_decision(
            proposal_id,
            UserDecision.APPROVE,
            decided_at=decision_time,
        )
        request = create_execution_request(
            plan, requested_at=execution_time, actor="USER"
        )
        execution = BytePreservingChangeEngine().execute(
            plan=plan,
            request=request,
            source_bytes=self.source_bytes,
        )
        verification = IndependentChangeVerifier().verify(
            plan=plan,
            result=execution,
        )
        if verification.status is not VerificationStatus.PASS:
            raise GuiWorkflowError(
                "Verifier FAIL: " + "; ".join(verification.reasons)
            )
        self._approved_plan = plan
        self._execution = execution
        self._verification = verification
        self._write_result = None
        return verification

    def save(
        self,
        *,
        output_midi_path: str | Path,
        saved_at: str,
    ) -> VerifiedWriteResult:
        if (
            self._approved_plan is None
            or self._execution is None
            or self._verification is None
            or self._verification.status is not VerificationStatus.PASS
        ):
            raise GuiWorkflowError("Verifier PASS is required before save")
        output = Path(output_midi_path)
        report = output.with_suffix(".json")
        try:
            result = AtomicVerifiedWriter().write(
                source_path=self.source_path,
                output_midi_path=output,
                output_report_path=report,
                plan=self._approved_plan,
                execution=self._execution,
                verification=self._verification,
                saved_at=saved_at,
            )
        except Exception as exc:
            raise GuiWorkflowError(str(exc)) from exc
        self._write_result = result
        return result

    def rollback_saved(self, *, user_confirmed: bool) -> VerifiedWriteResult:
        if not user_confirmed:
            raise GuiWorkflowError("USER confirmation is required for rollback")
        if self._write_result is None or self._write_result.status is not WriteStatus.SAVED:
            raise GuiWorkflowError("no saved writer result is available for rollback")
        try:
            result = AtomicVerifiedWriter().rollback(self._write_result)
        except Exception as exc:
            raise GuiWorkflowError(str(exc)) from exc
        self._write_result = result
        return result

    def _segment_option(self, ordinal: int) -> GuiSegmentOption:
        matches = [item for item in self.segment_options if item.ordinal == ordinal]
        if len(matches) != 1:
            raise GuiWorkflowError(f"segment {ordinal} is not eligible for bounded K03")
        return matches[0]

    def _identity(self, ordinal: int) -> ResolvedInstrumentIdentity:
        matches = [
            item for item in self.identities.identities
            if item.segment_ordinal == ordinal
        ]
        if len(matches) != 1:
            raise GuiWorkflowError(f"unknown K02 identity ordinal: {ordinal}")
        return matches[0]
