from .base import OptimizationContext, OptimizationModule
from .engine import ChangeEngine
from .history import CommandHistory, HistoryEntry
from .pipeline import OptimizationPipeline
from .quantize import QuantizeModule
from .velocity import (
    INSTRUMENT_VELOCITY_PROFILES,
    InstrumentVelocityProfile,
    VelocityRangeModule,
    VelocityShapeResult,
    detect_trill_note_ids,
    shape_instrument_velocity,
)
from .ppq import PpqResampleResult, resample_ppq
from .proposals import (
    Proposal,
    ProposalConflict,
    ProposalPlan,
    ProposalPlanEntry,
    ProposalRegistry,
    ProposalStatus,
)
from .policy import (
    AUTO_POLICY_SCHEMA,
    AUTO_POLICY_SCHEMA_VERSION,
    AutoPolicy,
    AutoPolicyFormatError,
    AutoPolicyLoader,
    AutomationMode,
    AutomationPackage,
    ErrorBudgets,
    ModulePolicy,
    PolicyAction,
    PolicyDecision,
    PolicyLocks,
    PolicyProfile,
    evaluate_policy,
)
from .proposal_adapters import (
    adapt_controller_thinning,
    adapt_drum_mapping,
    adapt_expression_conversion,
    adapt_initialization_update,
    adapt_sound_mapping,
    proposal_from_transaction,
    register_all,
)
from .simulation import (
    AnalyzerSnapshot,
    ProposalSimulator,
    SimulationDelta,
    SimulationMetrics,
    SimulationOutcome,
    SimulationReport,
    SimulationStep,
)
from .auto_workflow import (
    AUTO_REPORT_SCHEMA_VERSION,
    AutoWorkflow,
    PreparedAutoRun,
    build_auto_report,
    write_auto_report,
)

__all__ = ["AUTO_POLICY_SCHEMA", "AUTO_POLICY_SCHEMA_VERSION", "AUTO_REPORT_SCHEMA_VERSION", "AnalyzerSnapshot", "AutoPolicy", "AutoPolicyFormatError", "AutoPolicyLoader", "AutoWorkflow", "AutomationMode", "AutomationPackage", "ChangeEngine", "CommandHistory", "ErrorBudgets", "HistoryEntry", "ModulePolicy", "OptimizationContext", "OptimizationModule", "OptimizationPipeline", "PolicyAction", "PolicyDecision", "PolicyLocks", "PolicyProfile", "PpqResampleResult", "PreparedAutoRun", "Proposal", "ProposalConflict", "ProposalPlan", "ProposalPlanEntry", "ProposalRegistry", "ProposalSimulator", "ProposalStatus", "QuantizeModule", "SimulationDelta", "SimulationMetrics", "SimulationOutcome", "SimulationReport", "SimulationStep", "VelocityRangeModule", "adapt_controller_thinning", "adapt_drum_mapping", "adapt_expression_conversion", "adapt_initialization_update", "adapt_sound_mapping", "build_auto_report", "evaluate_policy", "proposal_from_transaction", "register_all", "resample_ppq", "write_auto_report"]
