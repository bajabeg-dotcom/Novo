from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from ..analysis.curves import CurveSimplification
from ..analysis.expression import ExpressionConversionPlan, ExpressionPlanStatus
from ..domain.changes import Change, ChangeTransaction, DeleteEvent, InsertEvent, RiskLevel
from ..domain.events import EventKind, MidiEvent
from ..domain.song import Song
from ..profiles.models import DeviceProfile
from .controller_thinning import build_curve_thinning_transaction
from .drum_mapping import DrumMappingPlan, build_drum_mapping_transaction
from .engine import song_revision
from .expression_conversion import build_expression_conversion_transaction
from .initialization_update import (
    InitializationUpdatePlan,
    build_initialization_update_transaction,
)
from .proposals import Proposal, ProposalRegistry
from .sound_mapping import SoundMappingPlan, build_sound_mapping_transaction


def adapt_initialization_update(
    song: Song, plan: InitializationUpdatePlan
) -> Proposal:
    proposal_id = "initialization-update"
    transaction = (
        build_initialization_update_transaction(song, plan, approved=True)
        if plan.status == "ready" and not plan.blockers and plan.updates
        else _empty_transaction(proposal_id, "initialization_update", plan.source_revision)
    )
    blockers = _non_actionable_blockers(plan.status, plan.blockers, plan.updates)
    finding_ids = tuple(
        sorted(
            {
                f"initialization:ch{item.channel}:{item.role}"
                for item in plan.updates
            }
            or {f"initialization:{plan.analysis.status}"}
        )
    )
    evidence = tuple(
        sorted(
            {f"event:{item.event_id}" for item in plan.updates}
            | {f"analysis:initialization:{plan.analysis.status}"}
        )
    )
    return proposal_from_transaction(
        song,
        proposal_id,
        transaction,
        finding_ids=finding_ids,
        evidence_refs=evidence,
        blockers=blockers,
        warnings=plan.warnings,
        confidence=1.0 if plan.analysis.status == "probable" else 0.0,
        expected_benefit=0.9 if plan.updates else 0.0,
        declared_risk=RiskLevel.HIGH,
        extra_event_ids=tuple(item.event_id for item in plan.updates),
    )


def adapt_controller_thinning(
    song: Song, plans: Iterable[CurveSimplification]
) -> tuple[Proposal, ...]:
    revision = song_revision(song)
    proposals = []
    for plan in plans:
        if not plan.applied or not plan.removed_event_ids:
            continue
        proposal_id = (
            f"controller-thinning:t{plan.curve.track_index}:"
            f"ch{plan.curve.channel}:cc{plan.curve.controller}"
        )
        transaction = build_curve_thinning_transaction(
            song, (plan,), approved=True, transaction_id=proposal_id
        )
        transaction = replace(transaction, base_revision=revision)
        benefit = len(plan.removed_event_ids) / max(1, plan.original_count)
        evidence = tuple(
            sorted(
                {f"event:{event_id}" for event_id in plan.kept_event_ids}
                | {f"event:{event_id}" for event_id in plan.removed_event_ids}
                | {
                    f"metric:tolerance:{plan.tolerance:g}",
                    f"metric:maximum-error:{plan.maximum_error:g}",
                }
            )
        )
        proposals.append(
            proposal_from_transaction(
                song,
                proposal_id,
                transaction,
                finding_ids=(
                    f"controller-curve:t{plan.curve.track_index}:"
                    f"ch{plan.curve.channel}:cc{plan.curve.controller}",
                ),
                evidence_refs=evidence,
                warnings=(plan.reason,),
                confidence=1.0,
                expected_benefit=benefit,
                declared_risk=RiskLevel.HIGH,
            )
        )
    return tuple(proposals)


def adapt_expression_conversion(
    song: Song, plans: Iterable[ExpressionConversionPlan]
) -> tuple[Proposal, ...]:
    revision = song_revision(song)
    proposals = []
    for plan in plans:
        proposal_id = f"cc7-cc11:channel-{plan.channel}"
        ready = (
            plan.status is ExpressionPlanStatus.READY_FOR_REVIEW
            and not plan.blockers
        )
        transaction = (
            replace(
                build_expression_conversion_transaction(song, plan, approved=True),
                base_revision=revision,
            )
            if ready
            else _empty_transaction(proposal_id, "cc7_cc11_conversion", revision)
        )
        blockers = tuple(plan.blockers) if plan.blockers else (() if ready else ("expression plan is not actionable",))
        event_ids = tuple(dict.fromkeys(plan.cc7_event_ids + plan.cc11_event_ids))
        evidence = tuple(
            sorted(
                {f"event:{event_id}" for event_id in event_ids}
                | {
                    f"metric:maximum-gain-error-db:{plan.maximum_gain_error_db:g}",
                    f"metric:allowed-gain-error-db:{plan.maximum_allowed_error_db:g}",
                }
            )
        )
        proposals.append(
            proposal_from_transaction(
                song,
                proposal_id,
                transaction,
                finding_ids=(f"cc7-cc11:channel-{plan.channel}",),
                evidence_refs=evidence,
                blockers=blockers,
                warnings=plan.warnings,
                confidence=1.0 if ready else 0.0,
                expected_benefit=0.7 if ready else 0.0,
                declared_risk=RiskLevel.HIGH,
                extra_event_ids=event_ids,
            )
        )
    return tuple(proposals)


def adapt_sound_mapping(
    song: Song, profile: DeviceProfile, plan: SoundMappingPlan
) -> Proposal:
    proposal_id = f"sound-mapping:{plan.request.program_event_id}"
    ready = plan.status == "ready" and not plan.blockers and bool(plan.updates)
    transaction = (
        build_sound_mapping_transaction(song, profile, plan, approved=True)
        if ready
        else _empty_transaction(proposal_id, "sound_mapping", plan.source_revision)
    )
    blockers = _non_actionable_blockers(plan.status, plan.blockers, plan.updates)
    event_ids = tuple(item.event_id for item in plan.updates)
    evidence = tuple(
        sorted(
            {f"event:{event_id}" for event_id in event_ids}
            | {
                f"profile:{plan.profile_id}:{plan.profile_sha256}",
                f"voice:{plan.request.target_voice_id}",
                f"identity-status:{plan.identity_status or 'unknown'}",
            }
        )
    )
    return proposal_from_transaction(
        song,
        proposal_id,
        transaction,
        finding_ids=(f"program-selection:{plan.request.program_event_id}",),
        evidence_refs=evidence,
        blockers=blockers,
        warnings=plan.warnings,
        confidence=_identity_confidence(plan.identity_status),
        expected_benefit=0.9 if ready else 0.0,
        declared_risk=RiskLevel.HIGH,
        extra_event_ids=event_ids,
    )


def adapt_drum_mapping(
    song: Song, profile: DeviceProfile, plan: DrumMappingPlan
) -> Proposal:
    request = plan.request
    proposal_id = (
        f"drum-mapping:{request.program_event_id}:"
        f"{request.source_note}-to-{request.target_note}"
    )
    ready = plan.status == "ready" and not plan.blockers and bool(plan.updates)
    transaction = (
        build_drum_mapping_transaction(song, profile, plan, approved=True)
        if ready
        else _empty_transaction(proposal_id, "drum_mapping", plan.source_revision)
    )
    blockers = _non_actionable_blockers(plan.status, plan.blockers, plan.updates)
    event_ids = tuple(item.event_id for item in plan.updates)
    kit = profile.drum_kits.get(request.target_kit_id)
    note_profile = kit.notes.get(request.target_note) if kit is not None else None
    identity_status = (
        note_profile.evidence["identity"].status if note_profile is not None else None
    )
    evidence = tuple(
        sorted(
            {f"event:{event_id}" for event_id in event_ids}
            | {
                f"profile:{plan.profile_id}:{plan.profile_sha256}",
                f"drum-kit:{request.target_kit_id}",
                f"drum-note:{request.target_note}",
                f"identity-status:{identity_status or 'unknown'}",
            }
        )
    )
    return proposal_from_transaction(
        song,
        proposal_id,
        transaction,
        finding_ids=(
            f"drum-map:{request.program_event_id}:note-{request.source_note}",
        ),
        evidence_refs=evidence,
        blockers=blockers,
        warnings=plan.warnings,
        confidence=_identity_confidence(identity_status),
        expected_benefit=0.95 if ready else 0.0,
        declared_risk=RiskLevel.HIGH,
        extra_event_ids=event_ids,
        extra_drum_notes=(request.source_note, request.target_note),
    )


def proposal_from_transaction(
    song: Song,
    proposal_id: str,
    transaction: ChangeTransaction,
    *,
    finding_ids: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...] = (),
    dependencies: tuple[str, ...] = (),
    blockers: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    confidence: float = 1.0,
    expected_benefit: float = 0.0,
    declared_risk: RiskLevel | None = None,
    extra_event_ids: tuple[str, ...] = (),
    extra_drum_notes: tuple[int, ...] = (),
) -> Proposal:
    context = _transaction_context(song, transaction, extra_event_ids)
    return Proposal(
        proposal_id=proposal_id,
        transaction=transaction,
        finding_ids=tuple(dict.fromkeys(finding_ids)),
        dependencies=tuple(dict.fromkeys(dependencies)),
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        confidence=confidence,
        expected_benefit=expected_benefit,
        declared_risk=declared_risk,
        evidence_refs=tuple(dict.fromkeys(evidence_refs)),
        track_indices=context[0],
        channels=context[1],
        drum_notes=tuple(sorted(set(context[2]) | set(extra_drum_notes))),
        message_kinds=context[3],
    )


def register_all(registry: ProposalRegistry, proposals: Iterable[Proposal]) -> None:
    for proposal in proposals:
        registry.register(proposal)


def _empty_transaction(
    transaction_id: str, module: str, revision: str
) -> ChangeTransaction:
    return ChangeTransaction(
        transaction_id=transaction_id,
        groups=(),
        module=module,
        reason="non-actionable analysis proposal",
        base_revision=revision,
    )


def _non_actionable_blockers(status: str, blockers, updates) -> tuple[str, ...]:
    result = list(blockers)
    if not result and (status != "ready" or not updates):
        result.append(f"plan is not actionable: {status}")
    return tuple(dict.fromkeys(result))


def _identity_confidence(status: str | None) -> float:
    return {
        "hardware_confirmed": 1.0,
        "software_verified": 0.9,
        "documented": 0.75,
        "hypothesis": 0.4,
    }.get(status, 0.0)


def _transaction_context(
    song: Song,
    transaction: ChangeTransaction,
    extra_event_ids: tuple[str, ...],
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], tuple[str, ...]]:
    event_map = {
        event.event_id: event for track in song.tracks for event in track.events
    }
    tracks: set[int] = set()
    channels: set[int] = set()
    drum_notes: set[int] = set()
    kinds: set[str] = set()
    changes_by_event = {change.event_id: change for change in transaction.changes}
    for event_id in tuple(changes_by_event) + tuple(extra_event_ids):
        change = changes_by_event.get(event_id)
        event = _event_for_change(change, event_map.get(event_id))
        if event is None:
            continue
        tracks.add(event.track_index)
        if event.channel is not None:
            channels.add(event.channel)
        kinds.add(_message_kind(event))
        if event.channel == 10 and (event.is_note_on or event.is_note_off):
            if event.data:
                drum_notes.add(event.data[0])
        if isinstance(change, Change) and change.field == "note_number":
            drum_notes.update((change.old_value, change.new_value))
    return (
        tuple(sorted(tracks)),
        tuple(sorted(channels)),
        tuple(sorted(drum_notes)),
        tuple(sorted(kinds)),
    )


def _event_for_change(change, existing: MidiEvent | None) -> MidiEvent | None:
    if isinstance(change, InsertEvent):
        return change.event
    if isinstance(change, DeleteEvent):
        return change.expected_event
    return existing


def _message_kind(event: MidiEvent) -> str:
    if event.kind is EventKind.META:
        return "meta"
    if event.kind is EventKind.SYSEX:
        return "sysex"
    return {
        0x80: "note",
        0x90: "note",
        0xA0: "poly_aftertouch",
        0xB0: "control_change",
        0xC0: "program_change",
        0xD0: "channel_pressure",
        0xE0: "pitch_bend",
    }.get(event.message_type, "channel")
