"""K02 read-only identity resolution for actual M10 instrument segments.

K02 combines only complete M10 address snapshots with the exact K01 registry.
It never mutates an InstrumentSegment, guesses missing banks, names User slot
contents, or authorizes Sound replacement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from instrument_segmenter import (
    AddressStatus,
    InstrumentSegment,
    SegmentationResult,
    SegmentationStatus,
)
from pa800_registry import (
    DrumRemapEvidence,
    FactoryEntry,
    Pa800FactoryRegistry,
    load_factory_registry,
)


class IdentityStatus(str, Enum):
    FACTORY_CONFIRMED = "FACTORY_CONFIRMED"
    USER_SLOT_CONFIRMED = "USER_SLOT_CONFIRMED"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"
    INCOMPLETE_ADDRESS = "INCOMPLETE_ADDRESS"
    NO_PROGRAM = "NO_PROGRAM"


@dataclass(frozen=True, slots=True)
class ResolvedInstrumentIdentity:
    segment_ordinal: int
    channel: int
    start_tick: int
    end_tick: int
    status: IdentityStatus
    requested_address: str | None
    effective_address: str | None
    official_name: str | None
    item_kind: str | None
    via_remap: bool
    factory_entry: FactoryEntry | None
    remap_evidence: tuple[DrumRemapEvidence, ...]
    candidate_addresses: tuple[str, ...]
    rule_id: str
    evidence_status: str
    selection_event_refs: tuple[tuple[int, int], ...]
    warnings: tuple[str, ...]
    protections: tuple[str, ...]
    original_segment: InstrumentSegment


@dataclass(frozen=True, slots=True)
class IdentityResolutionResult:
    source_sha256: str
    segmentation_status: SegmentationStatus
    identities: tuple[ResolvedInstrumentIdentity, ...]
    warnings: tuple[str, ...]
    protections: tuple[str, ...]
    original_result: SegmentationResult


class InstrumentIdentityResolver:
    """Resolve exact K01 identity without modifying M10 or MIDI state."""

    def __init__(self, registry: Pa800FactoryRegistry | None = None) -> None:
        self.registry = registry or load_factory_registry()

    def resolve(self, result: SegmentationResult) -> IdentityResolutionResult:
        identities = tuple(self.resolve_segment(segment) for segment in result.segments)
        warnings = tuple(
            warning
            for identity in identities
            for warning in identity.warnings
        )
        protections = (
            "K02 je read-only i ne mijenja M10 segment ni MIDI događaje.",
            "K02 rezultat nije dopuštenje za K03 zamjenu Sounda.",
            "Nepotpuna, nepoznata i konfliktna adresa ostaje bez automatske odluke.",
        )
        return IdentityResolutionResult(
            source_sha256=result.source_sha256,
            segmentation_status=result.status,
            identities=identities,
            warnings=warnings,
            protections=protections,
            original_result=result,
        )

    def resolve_segment(self, segment: InstrumentSegment) -> ResolvedInstrumentIdentity:
        address = segment.address
        common = {
            "segment_ordinal": segment.ordinal,
            "channel": segment.channel,
            "start_tick": segment.start_tick,
            "end_tick": segment.end_tick,
            "selection_event_refs": segment.selection_event_refs,
            "original_segment": segment,
        }
        base_protections = (
            "Originalni M10 identity_status ostaje UNRESOLVED.",
            "Rezultat je identitetski dokaz, ne Change Plan.",
        )

        if address.status is AddressStatus.NO_PROGRAM:
            return ResolvedInstrumentIdentity(
                **common,
                status=IdentityStatus.NO_PROGRAM,
                requested_address=None,
                effective_address=None,
                official_name=None,
                item_kind=None,
                via_remap=False,
                factory_entry=None,
                remap_evidence=(),
                candidate_addresses=(),
                rule_id="K02.NO_PROGRAM",
                evidence_status="CONFIRMED",
                warnings=("Segment nema Program Change i ne dobiva zadani program.",),
                protections=base_protections,
            )

        if address.status is AddressStatus.INCOMPLETE or address.value is None:
            return ResolvedInstrumentIdentity(
                **common,
                status=IdentityStatus.INCOMPLETE_ADDRESS,
                requested_address=None,
                effective_address=None,
                official_name=None,
                item_kind=None,
                via_remap=False,
                factory_entry=None,
                remap_evidence=(),
                candidate_addresses=(),
                rule_id="K02.INCOMPLETE_ADDRESS",
                evidence_status="CONFIRMED",
                warnings=(
                    "Program postoji, ali CC00/CC32 adresa nije potpuna; banka se ne pretpostavlja.",
                ),
                protections=base_protections,
            )

        cc00 = int(address.bank_msb)  # guarded by COMPLETE status
        cc32 = int(address.bank_lsb)
        pc = int(address.program)
        requested = address.value
        exact = self.registry.lookup(cc00, cc32, pc)
        remaps = (
            self.registry.remap_evidence_for_pc(pc)
            if cc00 == 120 and cc32 == 0 else ()
        )
        conflicting = tuple(
            rule for rule in remaps if pc in rule.conflicts_with_named_pcs
        )
        applicable = tuple(
            rule for rule in remaps if pc in rule.non_conflicting_source_pcs
        )

        if conflicting:
            candidates = {requested}
            for rule in conflicting:
                candidates.add(f"{rule.cc00}.{rule.cc32}.{rule.target_pc}")
            return ResolvedInstrumentIdentity(
                **common,
                status=IdentityStatus.CONFLICT,
                requested_address=requested,
                effective_address=None,
                official_name=exact.name if exact else None,
                item_kind=exact.kind if exact else None,
                via_remap=False,
                factory_entry=exact,
                remap_evidence=conflicting,
                candidate_addresses=tuple(sorted(candidates, key=self._address_key)),
                rule_id="K02.DRUM_REMAP_CONFLICT",
                evidence_status="CONFLICT",
                warnings=(
                    "Imenovana Drum Kit adresa preklapa se sa službenim remap rasponom; "
                    "nijedna interpretacija nije automatski odabrana.",
                ),
                protections=base_protections + (
                    "Sačuvati traženu adresu i sve remap kandidate.",
                ),
            )

        if exact is not None:
            return ResolvedInstrumentIdentity(
                **common,
                status=IdentityStatus.FACTORY_CONFIRMED,
                requested_address=requested,
                effective_address=requested,
                official_name=exact.name,
                item_kind=exact.kind,
                via_remap=False,
                factory_entry=exact,
                remap_evidence=remaps,
                candidate_addresses=(requested,),
                rule_id="K02.EXACT_FACTORY_ADDRESS",
                evidence_status="CONFIRMED",
                warnings=(),
                protections=base_protections,
            )

        if self.registry.is_user_drum_slot(cc00, cc32, pc):
            return ResolvedInstrumentIdentity(
                **common,
                status=IdentityStatus.USER_SLOT_CONFIRMED,
                requested_address=requested,
                effective_address=requested,
                official_name=None,
                item_kind="USER_DRUM_KIT_SLOT",
                via_remap=False,
                factory_entry=None,
                remap_evidence=(),
                candidate_addresses=(requested,),
                rule_id="K02.USER_DRUM_SLOT_LOCATION",
                evidence_status="CONFIRMED",
                warnings=(
                    "User Drum Kit lokacija je potvrđena, ali naziv i sadržaj slota ostaju UNKNOWN.",
                ),
                protections=base_protections + (
                    "Ne zamijeniti User sadržaj Factory nazivom.",
                ),
            )

        if len(applicable) == 1:
            rule = applicable[0]
            effective = f"{rule.cc00}.{rule.cc32}.{rule.target_pc}"
            target = self.registry.lookup(rule.cc00, rule.cc32, rule.target_pc)
            if target is not None:
                return ResolvedInstrumentIdentity(
                    **common,
                    status=IdentityStatus.FACTORY_CONFIRMED,
                    requested_address=requested,
                    effective_address=effective,
                    official_name=target.name,
                    item_kind=target.kind,
                    via_remap=True,
                    factory_entry=target,
                    remap_evidence=applicable,
                    candidate_addresses=(requested, effective),
                    rule_id="K02.CONFIRMED_DRUM_REMAP",
                    evidence_status="CONFIRMED",
                    warnings=(
                        "Factory identitet je potvrđen službenim remap retkom; "
                        "izvještaj čuva traženu i ciljnu adresu.",
                    ),
                    protections=base_protections + (
                        "Remap je identitetski dokaz i ne prepisuje MIDI adresu.",
                    ),
                )

        warnings = ["Potpuna adresa nije pronađena u K01 Factory registru."]
        if len(applicable) > 1:
            warnings.append("Više remap pravila odgovara istoj adresi; rezultat ostaje UNKNOWN.")
        elif applicable:
            warnings.append("Remap cilj nije imenovana K01 Factory adresa.")
        return ResolvedInstrumentIdentity(
            **common,
            status=IdentityStatus.UNKNOWN,
            requested_address=requested,
            effective_address=None,
            official_name=None,
            item_kind=None,
            via_remap=False,
            factory_entry=None,
            remap_evidence=applicable,
            candidate_addresses=(requested,),
            rule_id="K02.UNKNOWN_COMPLETE_ADDRESS",
            evidence_status="UNKNOWN",
            warnings=tuple(warnings),
            protections=base_protections + (
                "Ne koristiti GM zamjenu niti nagađati instrument.",
            ),
        )

    @staticmethod
    def _address_key(address: str) -> tuple[int, int, int]:
        return tuple(int(part) for part in address.split("."))  # type: ignore[return-value]
