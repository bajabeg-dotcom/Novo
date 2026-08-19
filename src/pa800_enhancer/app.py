from pathlib import Path

from .config import AppConfig
from .domain.song import Song
from .analysis.rhythm import RhythmDetector
from .analysis.summary import summarize
from .analysis.controllers import analyze_controllers
from .analysis.parameters import analyze_parameters
from .analysis.curves import simplify_song_curves
from .analysis.sysex import analyze_sysex
from .analysis.expression import analyze_cc7_to_cc11
from .analysis.programs import analyze_programs
from .analysis.initialization import analyze_initialization_bar
from .export.service import ExportService
from .optimize.base import OptimizationContext
from .optimize.engine import ChangeEngine
from .optimize.history import CommandHistory
from .optimize.pipeline import OptimizationPipeline
from .optimize.quantize import QuantizeModule
from .optimize.velocity import (
    INSTRUMENT_VELOCITY_PROFILES,
    VelocityRangeModule,
    shape_instrument_velocity,
    shape_velocity_automatically,
)
from .optimize.ppq import resample_ppq
from .optimize.simulation import ProposalSimulator
from .optimize.articulation import plan_articulations
from .optimize.performance import run_performance_pipeline
from .optimize.controller_thinning import build_curve_thinning_transaction
from .optimize.expression_conversion import (
    build_expression_conversion_transaction,
    preview_expression_conversion,
)
from .optimize.initialization_update import (
    build_initialization_update_transaction,
    plan_initialization_update,
    preview_initialization_update,
)
from .optimize.sound_mapping import (
    build_sound_mapping_transaction,
    plan_sound_mapping,
    preview_sound_mapping,
)
from .optimize.drum_mapping import (
    build_drum_mapping_transaction,
    plan_drum_mapping,
    preview_drum_mapping,
)
from .profiles.builtin_rhythms import RHYTHM_PROFILES
from .profiles.models import DeviceProfile
from .project.model import Project
from .project.storage import ProjectStorage
from .smf.reader import SmfReader
from .smf.writer import SmfWriter
from .validation.validator import SongValidator
from .database import DEFAULT_DATABASE_PATH, LocalDatabase
from .dna import extract_fingerprint, plan_dna_correction
from .optimize.conservative import optimize_conservatively


class EnhancerApplication:
    """Thin application service coordinating the independent core modules."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        self.reader = SmfReader(
            max_file_size=self.config.max_file_size,
            max_tracks=self.config.max_tracks,
            max_chunks=self.config.max_chunks,
            max_chunk_size=self.config.max_chunk_size,
            max_events_per_track=self.config.max_events_per_track,
        )
        self.writer = SmfWriter()
        self.validator = SongValidator()
        self.rhythm_detector = RhythmDetector()
        self.project_storage = ProjectStorage()
        self.export_service = ExportService()

    def import_midi(self, path: str | Path) -> Song:
        return self.reader.read(Path(path))

    def validate(self, song: Song):
        return self.validator.validate(song)

    def plan_dna_optimization(self, song: Song, *, database_path=DEFAULT_DATABASE_PATH,
                              strength: float = 0.65, maximum_distance: float = 0.12):
        fingerprint = extract_fingerprint(song)
        matches = LocalDatabase().nearest_fingerprints(
            fingerprint, corpus_kind="gold", path=Path(database_path)
        )
        return fingerprint, plan_dna_correction(
            song, matches, strength=strength, maximum_distance=maximum_distance
        )

    def summarize(self, song: Song):
        return summarize(song)

    def detect_rhythms(self, song: Song):
        return self.rhythm_detector.rank(song)

    def analyze_controllers(self, song: Song):
        return analyze_controllers(song)

    def analyze_parameters(self, song: Song):
        return analyze_parameters(song)

    def simplify_controller_curves(self, song: Song, tolerance: float = 1.0):
        return simplify_song_curves(song, tolerance)

    def build_curve_thinning_transaction(self, song: Song, plans, *, approved=False):
        return build_curve_thinning_transaction(song, plans, approved=approved)

    def analyze_sysex(self, song: Song):
        return analyze_sysex(song)

    def analyze_expression_conversion(self, song: Song, maximum_error_db=0.5):
        return analyze_cc7_to_cc11(song, maximum_error_db)

    def analyze_programs(self, song: Song, profile: DeviceProfile, **target):
        return analyze_programs(song, profile, **target)

    def analyze_initialization_bar(self, song: Song):
        return analyze_initialization_bar(song)

    def plan_initialization_update(self, song: Song, targets):
        return plan_initialization_update(song, tuple(targets))

    def preview_initialization_update(self, song: Song, plan):
        return preview_initialization_update(song, plan)

    def build_initialization_update_transaction(self, song: Song, plan, *, approved=False):
        return build_initialization_update_transaction(song, plan, approved=approved)

    def plan_sound_mapping(self, song: Song, profile: DeviceProfile, request, **target):
        return plan_sound_mapping(song, profile, request, **target)

    def preview_sound_mapping(self, song: Song, profile: DeviceProfile, plan):
        return preview_sound_mapping(song, profile, plan)

    def build_sound_mapping_transaction(
        self, song: Song, profile: DeviceProfile, plan, *, approved=False
    ):
        return build_sound_mapping_transaction(
            song, profile, plan, approved=approved
        )

    def plan_drum_mapping(self, song: Song, profile: DeviceProfile, request, **target):
        return plan_drum_mapping(song, profile, request, **target)

    def preview_drum_mapping(self, song: Song, profile: DeviceProfile, plan):
        return preview_drum_mapping(song, profile, plan)

    def build_drum_mapping_transaction(
        self, song: Song, profile: DeviceProfile, plan, *, approved=False
    ):
        return build_drum_mapping_transaction(song, profile, plan, approved=approved)

    def preview_expression_conversion(self, song: Song, plan):
        return preview_expression_conversion(song, plan)

    def build_expression_conversion_transaction(self, song: Song, plan, *, approved=False):
        return build_expression_conversion_transaction(song, plan, approved=approved)

    def suggest_basic_optimization(self, song: Song, quantize_division: int = 16):
        profile = DeviceProfile("pa800-default", rhythm_profiles=dict(RHYTHM_PROFILES))
        context = OptimizationContext(song, profile)
        pipeline = OptimizationPipeline([QuantizeModule(quantize_division, 0.5), VelocityRangeModule(1, 127)])
        return pipeline.suggest(context)

    def shape_instrument_velocity(self, song: Song, family: str, *, seed: int = 0, learned_profile=None):
        try:
            profile = INSTRUMENT_VELOCITY_PROFILES[family]
        except KeyError as error:
            raise ValueError(f"unknown instrument family: {family}") from error
        if learned_profile is not None:
            from dataclasses import replace
            if learned_profile.factory_key_range:
                profile = replace(profile, key_range=learned_profile.factory_key_range)
            if learned_profile.factory_velocity_p10_p90:
                low, high = learned_profile.factory_velocity_p10_p90
                profile = replace(profile, minimum=max(1, low), maximum=min(127, high), center=(low + high) // 2)
        context = OptimizationContext(song, DeviceProfile("pa800-default"), seed)
        return shape_instrument_velocity(context, profile)

    def shape_velocity_automatically(self, song: Song, catalog, *, seed: int = 0):
        context = OptimizationContext(song, DeviceProfile("pa800-default"), seed)
        return shape_velocity_automatically(context, catalog)

    def plan_articulations(self, song: Song, catalog, *, seed: int = 0):
        context = OptimizationContext(song, DeviceProfile("pa800-default"), seed)
        return plan_articulations(context, catalog)

    def run_performance_pipeline(self, song: Song, catalog, *, seed: int = 0):
        context = OptimizationContext(song, DeviceProfile("pa800-default"), seed)
        return run_performance_pipeline(context, catalog, self.validator)

    def optimize_conservatively(self, song: Song, factory_catalog):
        return optimize_conservatively(song, factory_catalog)

    def apply_approved_changes(self, song: Song, changes):
        return ChangeEngine().apply(song, changes)

    def create_command_history(self, song: Song) -> CommandHistory:
        return CommandHistory(song)

    def resample_ppq(self, song: Song, target_ppq: int):
        return resample_ppq(song, target_ppq)

    def simulate_proposals(
        self,
        song: Song,
        registry,
        policy,
        *,
        approved_proposal_ids=(),
    ):
        return ProposalSimulator(self.validator).simulate(
            song,
            registry,
            policy,
            approved_proposal_ids=tuple(approved_proposal_ids),
        )

    def create_project(
        self, song: Song, history: CommandHistory | None = None
    ) -> Project:
        project = Project(
            source_path=str(song.source_path) if song.source_path else None,
            source_sha256=song.source_sha256,
        )
        if history is not None:
            self.update_project_history(project, history)
        return project

    @staticmethod
    def update_project_history(project: Project, history: CommandHistory) -> None:
        state = history.to_state()
        project.command_history = state
        project.locked_event_ids = list(state["locked_event_ids"])
        project.locked_track_indices = list(state["locked_track_indices"])

    @staticmethod
    def restore_command_history(project: Project, song: Song) -> CommandHistory:
        if project.source_sha256 and song.source_sha256 != project.source_sha256:
            raise ValueError("project source SHA-256 does not match the imported MIDI")
        state = dict(project.command_history)
        state.setdefault("locked_event_ids", project.locked_event_ids)
        state.setdefault("locked_track_indices", project.locked_track_indices)
        return CommandHistory.from_state(song, state)

    def save_project(self, project: Project, path: str | Path) -> None:
        self.project_storage.save(project, Path(path))

    def load_project(self, path: str | Path) -> Project:
        return self.project_storage.load(Path(path))

    def autosave_project(
        self, project: Project, path: str | Path, generations: int = 3
    ) -> Path:
        return self.project_storage.autosave(project, Path(path), generations)

    def recover_project(
        self, path: str | Path, output: str | Path | None = None
    ):
        target = Path(output) if output is not None else None
        return self.project_storage.recover_latest(Path(path), target)

    def export_midi(self, song: Song, path: str | Path, mode: str = "auto") -> None:
        issues = self.validate(song)
        blocking = [issue for issue in issues if issue.blocks_export]
        if blocking:
            messages = "; ".join(issue.message for issue in blocking)
            raise ValueError(f"Export blocked: {messages}")
        self.export_service.export(song, Path(path), "pa800-default", mode=mode)
