"""RX-aware zastita velocity izmjena -- stavke 2.2 i 3.1 iz spiska.

Zatvara rupu N2 iz NEDOVRSENO.md: do sada nijedan optimizer nije citao
oscillator konfiguraciju, pa je izmjena velocityja mogla tiho promijeniti
artikulaciju na RX zvuku.

Sloj je namjerno **odvojen** od postojecih modula. Ne mijenja njihovu logiku
nego filtrira ono sto predloze:

    prijedlozi -> RxVelocityGuard.review() -> (dozvoljeno, blokirano)

Tri pravila, po vaznosti:

1. **Apsolutni okidaci se ne diraju.** Nota u zoni C7-G9 je fret/slide/noise
   okidac, ne muzika. Nikakva izmjena velocityja, visine ni trajanja.
2. **Artikulacija se ne mijenja precutno.** Ako bi novi velocity presao u
   drugi oscilator, prijedlog se blokira ili se skrati na granicu zone.
3. **Bez dokaza nema automatske izmjene.** Profil ispod `documented` ne
   moze odobriti izmjenu.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from ..profiles.rx import (
    RxProfileSet,
    RxSoundProfile,
    builtin_rx_profiles,
    is_absolute_trigger_note,
)


class GuardVerdict(StrEnum):
    ALLOWED = "allowed"
    CLAMPED = "clamped"
    BLOCKED_TRIGGER = "blocked_absolute_trigger"
    BLOCKED_ARTICULATION = "blocked_articulation_switch"
    BLOCKED_EVIDENCE = "blocked_insufficient_evidence"


@dataclass(frozen=True, slots=True)
class VelocityProposal:
    """Predlozena izmjena velocityja jedne note."""

    event_id: str
    note: int
    old_velocity: int
    new_velocity: int
    channel: int | None = None
    role: str = "unknown"


@dataclass(frozen=True, slots=True)
class GuardDecision:
    proposal: VelocityProposal
    verdict: GuardVerdict
    applied_velocity: int
    profile_id: str | None
    zone_before: str | None
    zone_after: str | None
    reason: str

    @property
    def is_change(self) -> bool:
        return self.applied_velocity != self.proposal.old_velocity


@dataclass(frozen=True, slots=True)
class GuardReport:
    decisions: tuple[GuardDecision, ...]

    @property
    def allowed(self) -> tuple[GuardDecision, ...]:
        return tuple(d for d in self.decisions if d.is_change)

    @property
    def blocked(self) -> tuple[GuardDecision, ...]:
        return tuple(
            d
            for d in self.decisions
            if d.verdict
            in (
                GuardVerdict.BLOCKED_TRIGGER,
                GuardVerdict.BLOCKED_ARTICULATION,
                GuardVerdict.BLOCKED_EVIDENCE,
            )
        )

    @property
    def clamped(self) -> tuple[GuardDecision, ...]:
        return tuple(d for d in self.decisions if d.verdict is GuardVerdict.CLAMPED)

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for decision in self.decisions:
            counts[decision.verdict.value] = counts.get(decision.verdict.value, 0) + 1
        return counts


class RxVelocityGuard:
    """Provjerava velocity prijedloge protiv RX oscilatorskih zona."""

    def __init__(
        self,
        profiles: RxProfileSet | None = None,
        *,
        allow_clamping: bool = True,
    ) -> None:
        self.profiles = profiles if profiles is not None else builtin_rx_profiles()
        self.allow_clamping = allow_clamping

    # -- razrjesavanje profila --------------------------------------------

    def resolve_profile(
        self,
        *,
        bank_msb: int | None = None,
        bank_lsb: int | None = None,
        program: int | None = None,
        profile_id: str | None = None,
    ) -> RxSoundProfile | None:
        if profile_id:
            return self.profiles.by_id(profile_id)
        if None not in (bank_msb, bank_lsb, program):
            return self.profiles.by_address(bank_msb, bank_lsb, program)  # type: ignore[arg-type]
        return None

    # -- glavni ulaz -------------------------------------------------------

    def review_one(
        self, proposal: VelocityProposal, profile: RxSoundProfile | None
    ) -> GuardDecision:
        keep = replace(proposal, new_velocity=proposal.old_velocity)

        def decide(
            verdict: GuardVerdict,
            velocity: int,
            reason: str,
            before: str | None = None,
            after: str | None = None,
        ) -> GuardDecision:
            return GuardDecision(
                proposal=proposal,
                verdict=verdict,
                applied_velocity=velocity,
                profile_id=profile.profile_id if profile else None,
                zone_before=before,
                zone_after=after,
                reason=reason,
            )

        # 1. Apsolutni okidaci -- i bez poznatog profila.
        if profile is not None:
            trigger = profile.is_trigger_note(proposal.note)
        else:
            trigger = is_absolute_trigger_note(proposal.note, proposal.role)
        if trigger:
            return decide(
                GuardVerdict.BLOCKED_TRIGGER,
                keep.new_velocity,
                f"nota {proposal.note} je apsolutni okidac (fret/slide/noise)",
            )

        # Bez profila ne mozemo suditi o artikulaciji; propusti nepromijenjeno
        # samo ako izmjena nije trazena.
        if profile is None:
            return decide(
                GuardVerdict.ALLOWED,
                proposal.new_velocity,
                "nema RX profila za adresu; velocity se tretira kao dinamika",
            )

        # 3. Dokazni prag.
        if not profile.is_automatic_eligible:
            return decide(
                GuardVerdict.BLOCKED_EVIDENCE,
                keep.new_velocity,
                f"profil {profile.profile_id} je {profile.evidence_status}",
            )

        before = profile.zone_for(proposal.note, proposal.old_velocity)
        after = profile.zone_for(proposal.note, proposal.new_velocity)
        before_name = before.name if before else None
        after_name = after.name if after else None

        # 2. Artikulacija.
        if profile.articulation_changes(
            proposal.note, proposal.old_velocity, proposal.new_velocity
        ):
            if self.allow_clamping and before is not None:
                clamped = profile.clamp_velocity(
                    proposal.note, proposal.old_velocity, proposal.new_velocity
                )
                if clamped != proposal.old_velocity:
                    return decide(
                        GuardVerdict.CLAMPED,
                        clamped,
                        (
                            f"velocity skracen na granicu zone "
                            f"{before.name} ({before.velocity_min}-{before.velocity_max})"
                        ),
                        before_name,
                        before_name,
                    )
            return decide(
                GuardVerdict.BLOCKED_ARTICULATION,
                keep.new_velocity,
                (
                    f"izmjena bi presla iz {before_name} u {after_name} "
                    f"i promijenila artikulaciju"
                ),
                before_name,
                after_name,
            )

        return decide(
            GuardVerdict.ALLOWED,
            proposal.new_velocity,
            "izmjena ostaje unutar iste oscilatorske zone",
            before_name,
            after_name,
        )

    def review(
        self,
        proposals: list[VelocityProposal],
        *,
        profile_for: dict[str, RxSoundProfile | None] | None = None,
        default_profile: RxSoundProfile | None = None,
    ) -> GuardReport:
        """Provjeri niz prijedloga.

        `profile_for` mapira event_id na profil kada su razliciti trackovi na
        razlicitim zvukovima; `default_profile` vrijedi za ostatak.
        """
        lookup = profile_for or {}
        decisions = [
            self.review_one(p, lookup.get(p.event_id, default_profile))
            for p in proposals
        ]
        return GuardReport(tuple(decisions))


def protected_note_ids(song, role_by_channel: dict[int, str] | None = None) -> frozenset[str]:
    """ID-jevi Note On dogadjaja koji su apsolutni okidaci.

    Koristi se prije bilo kakve transpozicije ili harmonizacije.
    """
    roles = role_by_channel or {}
    protected: set[str] = set()
    for track in song.tracks:
        for event in track.events:
            if not getattr(event, "is_note_on", False):
                continue
            channel = event.channel
            role = roles.get(channel or -1, "unknown")
            if is_absolute_trigger_note(event.data[0], role):
                protected.add(event.event_id)
    return frozenset(protected)
