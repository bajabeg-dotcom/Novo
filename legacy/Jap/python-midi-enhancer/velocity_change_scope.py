"""V02 explicit USER authorization for bounded S01 Note On velocity Apply.

Unknown velocity-switch and RX thresholds are not treated as safe. The user must
provide a second, explicit risk acknowledgement after approving the Suggest
plan. This module only creates the specialized execution request; C01 and V01
still enforce and independently verify the mutation limits.
"""

from __future__ import annotations

from change_engine import (
    ChangeExecutionError,
    ChangeExecutionRequest,
    create_execution_request,
)
from change_plan import ChangePlan, MutationField, PlanState

S01_RULE_ID = "S01.PROFILE_VELOCITY_OUTLIER"
VELOCITY_SWITCH_RISK_ACK = "UNKNOWN_VELOCITY_SWITCH_RX_THRESHOLDS"


class VelocityChangeScopeError(ValueError):
    """Raised when an S01 plan lacks specialized bounded authorization."""


def create_velocity_execution_request(
    plan: ChangePlan,
    *,
    requested_at: str,
    user_acknowledged_unknown_switch_risk: bool,
) -> ChangeExecutionRequest:
    if plan.state is not PlanState.APPROVED:
        raise VelocityChangeScopeError("V02 requires a fully USER-approved S01 plan")
    if not user_acknowledged_unknown_switch_risk:
        raise VelocityChangeScopeError(
            "USER must acknowledge unknown velocity-switch/RX threshold risk"
        )
    if not plan.proposals or any(
        proposal.rule_id != S01_RULE_ID for proposal in plan.proposals
    ):
        raise VelocityChangeScopeError("V02 accepts only S01 proposals")
    mutations = tuple(
        mutation for proposal in plan.proposals for mutation in proposal.mutations
    )
    if not mutations or len(mutations) > 32:
        raise VelocityChangeScopeError("V02 requires 1..32 mutations")
    for mutation in mutations:
        if mutation.event_kind != "note_on" or mutation.field is not MutationField.DATA_1:
            raise VelocityChangeScopeError("V02 accepts only Note On data[1] mutations")
        if not 1 <= mutation.old_value <= 127 or not 1 <= mutation.new_value <= 127:
            raise VelocityChangeScopeError("V02 velocity must remain in 1..127")
        if abs(mutation.new_value - mutation.old_value) > 8:
            raise VelocityChangeScopeError("V02 adjustment exceeds 8 velocity units")
    try:
        return create_execution_request(
            plan,
            requested_at=requested_at,
            actor="USER",
            authorized_rule_ids=(S01_RULE_ID,),
            risk_acknowledgements=(VELOCITY_SWITCH_RISK_ACK,),
        )
    except ChangeExecutionError as exc:
        raise VelocityChangeScopeError(str(exc)) from exc
