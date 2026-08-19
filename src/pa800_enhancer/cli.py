import argparse
import hashlib
import json
import zipfile
from dataclasses import asdict
from pathlib import Path

from .app import EnhancerApplication
from .database import DEFAULT_DATABASE_PATH, LocalDatabase
from .hardware import (
    HARDWARE_TEST_SCHEMA,
    AudioReference,
    HardwareProbeGenerator,
    HardwareTestFormatError,
    HardwareTestHarness,
    HardwareTestLoader,
    record_hardware_cycle,
)
from .profiles import (
    DEVICE_PROFILE_SCHEMA,
    DeviceProfileLoader,
    ProfileFormatError,
    promote_hardware_case,
)
from .optimize.initialization_update import InitializationChannelTarget
from .optimize.sound_mapping import SoundMappingRequest
from .optimize.drum_mapping import DrumMappingRequest
from .optimize.policy import (
    AUTO_POLICY_SCHEMA,
    AutoPolicyFormatError,
    AutoPolicyLoader,
    AutomationMode,
    AutomationPackage,
    PolicyProfile,
    PolicyAction,
    evaluate_policy,
)
from .optimize.engine import ChangeEngine, song_revision
from .optimize.proposals import ProposalRegistry
from .optimize.proposal_adapters import (
    adapt_controller_thinning,
    adapt_drum_mapping,
    adapt_expression_conversion,
    adapt_initialization_update,
    adapt_sound_mapping,
    register_all,
)
from .optimize.auto_workflow import AutoWorkflow, build_auto_report, write_auto_report
from .ui.main_window import launch_ui
from .windows_setup import generate_windows_scripts
from .corpus import CorpusRunner, write_corpus_report
from .optimize.velocity import INSTRUMENT_VELOCITY_PROFILES
from .reference_learning import ReferenceLearner, load_reference_catalog, write_reference_catalog
from .optimize.performance_batch import PerformanceBatchRunner, write_batch_report
from .dna import extract_fingerprint, plan_dna_correction
from .dna_learning import DnaLearner
from .dna_audit import audit_database
from .generator import GeneratorConfig, KEYS, ROLES, SCALES, STYLE_PRESETS, SongForm, arrange_harmonically, fit_song_form, generate_notes, train_generator, write_generated_midi
from .artifacts import audit_manifest, build_manifest, load_manifest, write_manifest
from .analysis.harmony import analyze_harmony
from .analysis.structure import analyze_structure
from .analysis_repository import AnalysisRepository
from .planning import FactorySongPlanner, map_section_energy
from .arranging import FactorySourceRepository, arrange_song_plan, materialize_arrangement, transfer_gold_performance
from .evaluation import evaluate_arrangement
from .resources import ResourceResolver
from .retrieval import FactoryCorpusIndexer, FactoryIndex, FactoryPackageIndex, FactoryPackageQuery, FactoryQuery, load_factory_catalog, write_factory_catalog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pa800-enhancer", description="Inspect and safely process Standard MIDI Files for Korg Pa800 workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("inspect", "validate", "rhythms", "parameters", "sysex", "initialization"):
        command = subparsers.add_parser(name)
        command.add_argument("midi", type=Path)

    programs = subparsers.add_parser("programs")
    programs.add_argument("midi", type=Path)
    programs.add_argument("--profile", type=Path, required=True)
    programs.add_argument("--model")
    programs.add_argument("--os-version")
    programs.add_argument("--resources-version")
    programs.add_argument(
        "--minimum-status",
        choices=("hypothesis", "documented", "software_verified", "hardware_confirmed"),
        default="documented",
    )

    init_update = subparsers.add_parser("init-update")
    init_update.add_argument("midi", type=Path)
    init_update.add_argument("--channel", type=int, required=True)
    init_update.add_argument("--cc0", type=int)
    init_update.add_argument("--cc32", type=int)
    init_update.add_argument("--program", type=int)
    init_update.add_argument("--volume", type=int)
    init_update.add_argument("--pan", type=int)
    init_update.add_argument("--expression", type=int)
    init_update.add_argument("--reverb", type=int)
    init_update.add_argument("--chorus", type=int)
    init_update.add_argument("--apply", action="store_true")
    init_update.add_argument("--output", type=Path)

    sound_map = subparsers.add_parser("sound-map")
    sound_map.add_argument("midi", type=Path)
    sound_map.add_argument("--profile", type=Path, required=True)
    sound_map.add_argument("--program-event", required=True)
    sound_map.add_argument("--target-voice", required=True)
    sound_map.add_argument(
        "--minimum-status",
        choices=("hypothesis", "documented", "software_verified", "hardware_confirmed"),
        default="hardware_confirmed",
    )
    sound_map.add_argument("--model")
    sound_map.add_argument("--os-version")
    sound_map.add_argument("--resources-version")
    sound_map.add_argument("--apply", action="store_true")
    sound_map.add_argument("--output", type=Path)

    drum_map = subparsers.add_parser("drum-map")
    drum_map.add_argument("midi", type=Path)
    drum_map.add_argument("--profile", type=Path, required=True)
    drum_map.add_argument("--program-event", required=True)
    drum_map.add_argument("--target-kit", required=True)
    drum_map.add_argument("--source-note", type=int, required=True)
    drum_map.add_argument("--target-note", type=int, required=True)
    drum_map.add_argument(
        "--minimum-status",
        choices=("hypothesis", "documented", "software_verified", "hardware_confirmed"),
        default="hardware_confirmed",
    )
    drum_map.add_argument("--model")
    drum_map.add_argument("--os-version")
    drum_map.add_argument("--resources-version")
    drum_map.add_argument("--apply", action="store_true")
    drum_map.add_argument("--output", type=Path)

    expression = subparsers.add_parser("expression")
    expression.add_argument("midi", type=Path)
    expression.add_argument("--max-error-db", type=float, default=0.5)
    expression.add_argument("--apply", action="store_true")
    expression.add_argument("--channel", type=int)
    expression.add_argument("--output", type=Path)

    curves = subparsers.add_parser("curves")
    curves.add_argument("midi", type=Path)
    curves.add_argument("--tolerance", type=float, default=1.0)
    curves.add_argument("--apply", action="store_true")
    curves.add_argument("--output", type=Path)

    export = subparsers.add_parser("export")
    export.add_argument("midi", type=Path)
    export.add_argument("output", type=Path)
    export.add_argument("--mode", choices=("auto", "preserve", "segment-preserve", "canonical"), default="auto")

    optimize = subparsers.add_parser("optimize")
    optimize.add_argument("midi", type=Path)
    optimize.add_argument("--grid", type=int, default=16)
    optimize.add_argument("--apply", action="store_true", help="approve and apply all generated suggestions")
    optimize.add_argument("--output", type=Path)

    velocity_shape = subparsers.add_parser("velocity-shape")
    velocity_shape.add_argument("midi", type=Path)
    velocity_shape.add_argument("--family", choices=tuple(INSTRUMENT_VELOCITY_PROFILES), required=True)
    velocity_shape.add_argument("--seed", type=int, default=0)
    velocity_shape.add_argument("--catalog", type=Path)
    velocity_shape.add_argument("--address")
    velocity_shape.add_argument("--apply", action="store_true")
    velocity_shape.add_argument("--output", type=Path)
    velocity_auto = subparsers.add_parser("velocity-auto")
    velocity_auto.add_argument("midi", type=Path)
    velocity_auto.add_argument("--catalog", type=Path, required=True)
    velocity_auto.add_argument("--seed", type=int, default=0)
    velocity_auto.add_argument("--apply", action="store_true")
    velocity_auto.add_argument("--output", type=Path)
    articulation_auto = subparsers.add_parser("articulation-auto")
    articulation_auto.add_argument("midi", type=Path)
    articulation_auto.add_argument("--catalog", type=Path, required=True)
    articulation_auto.add_argument("--seed", type=int, default=0)
    articulation_auto.add_argument("--apply", action="store_true")
    articulation_auto.add_argument("--output", type=Path)
    performance_auto = subparsers.add_parser("performance-auto")
    performance_auto.add_argument("midi", type=Path)
    performance_auto.add_argument("--catalog", type=Path, required=True)
    performance_auto.add_argument("--seed", type=int, default=0)
    performance_auto.add_argument("--apply", action="store_true")
    performance_auto.add_argument("--output", type=Path)
    performance_auto.add_argument("--report", type=Path)
    performance_batch = subparsers.add_parser("performance-batch")
    performance_batch.add_argument("input_directory", type=Path)
    performance_batch.add_argument("output_directory", type=Path)
    performance_batch.add_argument("--catalog", type=Path, required=True)
    performance_batch.add_argument("--report", type=Path, required=True)
    performance_batch.add_argument("--seed", type=int, default=0)
    performance_batch.add_argument("--apply", action="store_true")
    performance_batch.add_argument("--overwrite", action="store_true")

    auto = subparsers.add_parser("auto")
    auto.add_argument("midi", type=Path)
    auto.add_argument("--policy", type=Path, required=True)
    auto.add_argument("--profile", type=Path)
    auto.add_argument("--tolerance", type=float, default=1.0)
    auto.add_argument("--max-error-db", type=float, default=0.5)
    auto.add_argument("--init", action="append", default=[])
    auto.add_argument("--sound-map", action="append", default=[])
    auto.add_argument("--drum-map", action="append", default=[])
    auto.add_argument("--approve", action="append", default=[])
    auto.add_argument("--interactive", action="store_true")
    auto.add_argument("--apply", action="store_true")
    auto.add_argument("--output", type=Path)
    auto.add_argument("--report", type=Path)
    auto.add_argument("--project", type=Path)
    auto.add_argument(
        "--export-mode",
        choices=("auto", "preserve", "segment-preserve", "canonical"),
        default="auto",
    )
    auto.add_argument(
        "--minimum-status",
        choices=("hypothesis", "documented", "software_verified", "hardware_confirmed"),
        default="hardware_confirmed",
    )
    auto.add_argument("--model")
    auto.add_argument("--os-version")
    auto.add_argument("--resources-version")
    auto.add_argument("--overwrite", action="store_true")

    project = subparsers.add_parser("project")
    project.add_argument("midi", type=Path)
    project.add_argument("output", type=Path)

    recover = subparsers.add_parser("recover")
    recover.add_argument("project", type=Path)
    recover.add_argument("--output", type=Path)

    resample = subparsers.add_parser("resample")
    resample.add_argument("midi", type=Path)
    resample.add_argument("output", type=Path)
    resample.add_argument("--ppq", type=int, required=True)

    profile = subparsers.add_parser("profile")
    profile_subparsers = profile.add_subparsers(dest="profile_command", required=True)
    profile_validate = profile_subparsers.add_parser("validate")
    profile_validate.add_argument("profile", type=Path)
    profile_show = profile_subparsers.add_parser("show")
    profile_show.add_argument("profile", type=Path)
    profile_promote = profile_subparsers.add_parser("promote-hardware")
    profile_promote.add_argument("source_profile", type=Path)
    profile_promote.add_argument("manifest", type=Path)
    profile_promote.add_argument("output", type=Path)
    profile_promote.add_argument("--voice-id", required=True)
    profile_promote.add_argument("--new-profile-id", required=True)
    profile_promote.add_argument("--new-version", required=True)
    profile_promote.add_argument("--assertion")
    profile_promote.add_argument("--overwrite", action="store_true")
    profile_subparsers.add_parser("schema")

    hardware = subparsers.add_parser("hardware")
    hardware_subparsers = hardware.add_subparsers(dest="hardware_command", required=True)
    hardware_validate = hardware_subparsers.add_parser("validate")
    hardware_validate.add_argument("manifest", type=Path)
    hardware_show = hardware_subparsers.add_parser("show")
    hardware_show.add_argument("manifest", type=Path)
    hardware_generate = hardware_subparsers.add_parser("generate")
    hardware_generate.add_argument("kind", choices=("sound", "drum"))
    hardware_generate.add_argument("output_directory", type=Path)
    hardware_generate.add_argument("--case-id", required=True)
    hardware_generate.add_argument("--cc0", type=int, required=True)
    hardware_generate.add_argument("--cc32", type=int, required=True)
    hardware_generate.add_argument("--program", type=int, required=True)
    hardware_generate.add_argument("--note", type=int)
    hardware_generate.add_argument("--velocity", type=int, default=96)
    hardware_generate.add_argument("--channel", type=int)
    hardware_generate.add_argument("--expected-name", required=True)
    hardware_generate.add_argument("--expected-kit-name")
    hardware_generate.add_argument("--os-version", required=True)
    hardware_generate.add_argument("--resources-version")
    hardware_generate.add_argument("--overwrite", action="store_true")
    hardware_record = hardware_subparsers.add_parser("record-cycle")
    hardware_record.add_argument("manifest", type=Path)
    hardware_record.add_argument("output", type=Path)
    hardware_record.add_argument("--cycle", type=int, required=True)
    hardware_record.add_argument("--status", choices=("passed", "failed"), required=True)
    hardware_record.add_argument("--tested-at", required=True)
    hardware_record.add_argument("--tester", required=True)
    hardware_record.add_argument("--output-midi", type=Path, required=True)
    hardware_record.add_argument("--observations", type=Path, required=True)
    hardware_record.add_argument("--log", action="append", default=[])
    hardware_record.add_argument("--notes", default="")
    hardware_record.add_argument("--audio-locator")
    hardware_record.add_argument("--audio-sha256")
    hardware_record.add_argument("--audio-notes", default="")
    hardware_record.add_argument("--overwrite", action="store_true")
    hardware_subparsers.add_parser("schema")

    database = subparsers.add_parser("database")
    database_subparsers = database.add_subparsers(dest="database_command", required=True)
    database_init = database_subparsers.add_parser("init")
    database_init.add_argument("path", type=Path, nargs="?", default=DEFAULT_DATABASE_PATH)
    database_status = database_subparsers.add_parser("status")
    database_status.add_argument("path", type=Path, nargs="?", default=DEFAULT_DATABASE_PATH)
    database_profile = database_subparsers.add_parser("import-profile")
    database_profile.add_argument("profile", type=Path)
    database_profile.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    database_hardware = database_subparsers.add_parser("import-hardware")
    database_hardware.add_argument("manifest", type=Path)
    database_hardware.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)

    policy = subparsers.add_parser("policy")
    policy_subparsers = policy.add_subparsers(dest="policy_command", required=True)
    policy_validate = policy_subparsers.add_parser("validate")
    policy_validate.add_argument("policy", type=Path)
    policy_show = policy_subparsers.add_parser("show")
    policy_show.add_argument("policy", type=Path)
    policy_create = policy_subparsers.add_parser("create")
    policy_create.add_argument("output", type=Path)
    policy_create.add_argument("--policy-id", required=True)
    policy_create.add_argument("--version", required=True)
    policy_create.add_argument(
        "--mode",
        choices=tuple(item.value for item in AutomationMode),
        default=AutomationMode.ASSISTED.value,
    )
    policy_create.add_argument(
        "--package",
        choices=tuple(item.value for item in AutomationPackage),
        default=AutomationPackage.FULL_ASSISTED.value,
    )
    policy_create.add_argument("--profile-id")
    policy_create.add_argument("--profile-sha256")
    policy_create.add_argument("--seed", type=int, default=0)
    policy_create.add_argument("--overwrite", action="store_true")
    policy_subparsers.add_parser("schema")

    windows_scripts = subparsers.add_parser("windows-scripts")
    windows_scripts.add_argument("output_directory", type=Path, nargs="?", default=Path("."))
    windows_scripts.add_argument("--overwrite", action="store_true")

    ui = subparsers.add_parser("ui")
    ui.add_argument("midi", type=Path, nargs="?")
    corpus = subparsers.add_parser("corpus")
    corpus.add_argument("sources", type=Path, nargs="+")
    corpus.add_argument("--output", type=Path)
    corpus.add_argument("--fail-on-blocked", action="store_true")
    references = subparsers.add_parser("reference-learn")
    references.add_argument("sources", type=Path, nargs="+")
    references.add_argument("--gold-match", default="Gold DNA.zip")
    references.add_argument("--factory-match", default="Split Factory Styles.zip")
    references.add_argument("--output", type=Path, required=True)
    dna_learn = subparsers.add_parser("dna-learn")
    dna_learn.add_argument("sources", type=Path, nargs="+")
    dna_learn.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    dna_learn.add_argument("--gold-match", default="Gold DNA.zip")
    dna_learn.add_argument("--factory-match", default="Split Factory Styles.zip")
    dna_learn.add_argument("--force", action="store_true")
    dna_optimize = subparsers.add_parser("dna-optimize")
    dna_optimize.add_argument("midi", type=Path)
    dna_optimize.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    dna_optimize.add_argument("--strength", type=float, default=0.65)
    dna_optimize.add_argument("--maximum-distance", type=float, default=0.12)
    dna_optimize.add_argument("--apply", action="store_true")
    dna_optimize.add_argument("--output", type=Path)
    dna_audit = subparsers.add_parser("dna-audit")
    dna_audit.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    generator_train = subparsers.add_parser("generator-train")
    generator_train.add_argument("sources", type=Path, nargs="+"); generator_train.add_argument("--checkpoint",type=Path,required=True)
    generator_train.add_argument("--epochs",type=int,default=2); generator_train.add_argument("--batch-size",type=int,default=16)
    generator_train.add_argument("--threads",type=int,default=2); generator_train.add_argument("--limit",type=int); generator_train.add_argument("--resume",action="store_true")
    generator_generate = subparsers.add_parser("generator-generate")
    generator_generate.add_argument("--checkpoint",type=Path,required=True); generator_generate.add_argument("--output",type=Path,required=True)
    generator_generate.add_argument("--roles",nargs="+",choices=ROLES,default=list(ROLES)); generator_generate.add_argument("--notes",type=int,default=256)
    generator_generate.add_argument("--temperature",type=float,default=.9); generator_generate.add_argument("--top-k",type=int,default=12); generator_generate.add_argument("--seed",type=int,default=0); generator_generate.add_argument("--tempo",type=int)
    generator_generate.add_argument("--key",choices=tuple(KEYS),default="C"); generator_generate.add_argument("--scale",choices=tuple(SCALES),default="major")
    generator_generate.add_argument("--bars",type=int,default=32)
    generator_generate.add_argument("--style",choices=tuple(STYLE_PRESETS),default="pop")
    artifacts = subparsers.add_parser("artifacts")
    artifact_subparsers = artifacts.add_subparsers(dest="artifact_command", required=True)
    artifact_create = artifact_subparsers.add_parser("create")
    artifact_create.add_argument("--root",type=Path,required=True); artifact_create.add_argument("--output",type=Path,required=True)
    artifact_create.add_argument("--entry",action="append",required=True,help="id,type,path,schema-or-none,status")
    artifact_audit = artifact_subparsers.add_parser("audit")
    artifact_audit.add_argument("manifest",type=Path); artifact_audit.add_argument("--root",type=Path,required=True)
    harmony = subparsers.add_parser("harmony")
    harmony.add_argument("midi",type=Path); harmony.add_argument("--database",type=Path,default=DEFAULT_DATABASE_PATH)
    harmony.add_argument("--store",action="store_true"); harmony.add_argument("--minimum-confidence",type=float,default=.18); harmony.add_argument("--chord-context-beats",type=float,default=.5); harmony.add_argument("--temporal-decode",action=argparse.BooleanOptionalAction,default=True)
    structure = subparsers.add_parser("structure")
    structure.add_argument("midi",type=Path); structure.add_argument("--database",type=Path,default=DEFAULT_DATABASE_PATH); structure.add_argument("--store",action="store_true")
    energy_map = subparsers.add_parser("energy-map"); energy_map.add_argument("midi",type=Path)
    factory_song = subparsers.add_parser("factory-song-plan"); factory_song.add_argument("midi",type=Path)
    factory_song.add_argument("--groove-catalog",type=Path,default=ResourceResolver().find(Path("data/factory-variation-groove-analysis.json"),required=False) or Path("data/factory-variation-groove-analysis.json"))
    factory_song.add_argument("--pattern-catalog",type=Path,default=ResourceResolver().find(Path("data/factory-pattern-catalog.json"),required=False) or Path("data/factory-pattern-catalog.json"))
    factory_song.add_argument("--family"); factory_song.add_argument("--style"); factory_song.add_argument("--meter",default="4/4"); factory_song.add_argument("--density",type=float); factory_song.add_argument("--drum-density",type=float); factory_song.add_argument("--off16-ratio",type=float); factory_song.add_argument("--minimum-channels",type=int,default=5)
    arrange_preview = subparsers.add_parser("factory-arrange-preview"); arrange_preview.add_argument("midi",type=Path); arrange_preview.add_argument("--factory-source",type=Path,required=True)
    arrange_preview.add_argument("--groove-catalog",type=Path,default=ResourceResolver().find(Path("data/factory-variation-groove-analysis.json"),required=False) or Path("data/factory-variation-groove-analysis.json")); arrange_preview.add_argument("--pattern-catalog",type=Path,default=ResourceResolver().find(Path("data/factory-pattern-catalog.json"),required=False) or Path("data/factory-pattern-catalog.json"))
    arrange_preview.add_argument("--family"); arrange_preview.add_argument("--style"); arrange_preview.add_argument("--meter",default="4/4"); arrange_preview.add_argument("--density",type=float); arrange_preview.add_argument("--drum-density",type=float); arrange_preview.add_argument("--off16-ratio",type=float); arrange_preview.add_argument("--minimum-channels",type=int,default=5); arrange_preview.add_argument("--chord-context-beats",type=float,default=.5); arrange_preview.add_argument("--temporal-decode",action=argparse.BooleanOptionalAction,default=True)
    arrange_preview.add_argument("--gold-transfer",action=argparse.BooleanOptionalAction,default=True)
    arrange_preview.add_argument("--gold-catalog",type=Path,default=ResourceResolver().find(Path("data/performance-reference-catalog-v2.json"),required=False) or Path("data/performance-reference-catalog-v2.json"))
    arrange_preview.add_argument("--performance-seed",type=int,default=0)
    arrange_preview.add_argument("--output",type=Path); arrange_preview.add_argument("--allow-review-preview",action="store_true")
    factory_retrieve = subparsers.add_parser("factory-retrieve")
    factory_retrieve.add_argument("--catalog",type=Path,default=ResourceResolver().find(Path("data/factory-variation-groove-analysis.json"),required=False) or Path("data/factory-variation-groove-analysis.json"))
    factory_retrieve.add_argument("--family"); factory_retrieve.add_argument("--variation",type=int,default=2)
    factory_retrieve.add_argument("--meter",default="4/4"); factory_retrieve.add_argument("--density",type=float); factory_retrieve.add_argument("--drum-density",type=float)
    factory_retrieve.add_argument("--off16-ratio",type=float); factory_retrieve.add_argument("--minimum-channels",type=int,default=1); factory_retrieve.add_argument("--limit",type=int,default=5)
    factory_index = subparsers.add_parser("factory-index")
    factory_index.add_argument("source",type=Path); factory_index.add_argument("--output",type=Path,required=True)
    factory_index.add_argument("--factory-member",default="Split Factory Styles.zip"); factory_index.add_argument("--limit",type=int); factory_index.add_argument("--workers",type=int,default=4)
    factory_package = subparsers.add_parser("factory-package")
    factory_package.add_argument("--groove-catalog",type=Path,default=ResourceResolver().find(Path("data/factory-variation-groove-analysis.json"),required=False) or Path("data/factory-variation-groove-analysis.json"))
    factory_package.add_argument("--pattern-catalog",type=Path,default=ResourceResolver().find(Path("data/factory-pattern-catalog.json"),required=False) or Path("data/factory-pattern-catalog.json"))
    factory_package.add_argument("--family"); factory_package.add_argument("--variation",type=int,default=2); factory_package.add_argument("--meter",default="4/4")
    factory_package.add_argument("--density",type=float); factory_package.add_argument("--drum-density",type=float); factory_package.add_argument("--off16-ratio",type=float)
    factory_package.add_argument("--minimum-channels",type=int,default=1); factory_package.add_argument("--roles",nargs="+",default=["bass","drums","percussion","guitar","accompaniment"])
    factory_package.add_argument("--include-types",nargs="+",choices=("variation","fill","break","intro","ending"),default=["variation","fill","break","intro","ending"]); factory_package.add_argument("--limit",type=int,default=3)
    return parser


def _print_issues(issues) -> int:
    for issue in issues:
        location = ""
        if issue.track_index is not None:
            location = f" track={issue.track_index} tick={issue.tick}"
        print(f"{issue.severity.value}: {issue.code}:{location} {issue.message}")
    return 2 if any(issue.blocks_export for issue in issues) else 0


def _parse_auto_init(value: str) -> InitializationChannelTarget:
    parts = [item.strip() for item in value.split(",") if item.strip()]
    if not parts:
        raise ValueError("empty --init specification")
    try:
        channel = int(parts[0])
    except ValueError as error:
        raise ValueError("--init must start with a MIDI channel") from error
    program = None
    controllers = []
    seen = set()
    for item in parts[1:]:
        if "=" not in item:
            raise ValueError(f"invalid --init assignment: {item}")
        key, raw = (part.strip().lower() for part in item.split("=", 1))
        try:
            number = int(raw)
        except ValueError as error:
            raise ValueError(f"invalid --init value: {item}") from error
        if key == "program":
            if program is not None:
                raise ValueError("--init program is repeated")
            program = number
        elif key.startswith("cc") and key[2:].isdigit():
            controller = int(key[2:])
            if controller in seen:
                raise ValueError(f"--init CC{controller} is repeated")
            seen.add(controller)
            controllers.append((controller, number))
        else:
            raise ValueError(f"unknown --init field: {key}")
    return InitializationChannelTarget(channel, program, tuple(controllers))


def _parse_auto_sound(value: str) -> SoundMappingRequest:
    if "=" not in value:
        raise ValueError("--sound-map must use PROGRAM_EVENT=VOICE_ID")
    event_id, voice_id = (item.strip() for item in value.split("=", 1))
    if not event_id or not voice_id:
        raise ValueError("--sound-map requires both event and voice identifiers")
    return SoundMappingRequest(event_id, voice_id)


def _parse_auto_drum(value: str) -> DrumMappingRequest:
    if "=" not in value:
        raise ValueError("--drum-map must use PROGRAM_EVENT=KIT_ID,SOURCE_NOTE,TARGET_NOTE")
    event_id, raw = (item.strip() for item in value.split("=", 1))
    parts = [item.strip() for item in raw.split(",")]
    if not event_id or len(parts) != 3 or not all(parts):
        raise ValueError("--drum-map must use PROGRAM_EVENT=KIT_ID,SOURCE_NOTE,TARGET_NOTE")
    try:
        return DrumMappingRequest(event_id, parts[0], int(parts[1]), int(parts[2]))
    except ValueError as error:
        raise ValueError("--drum-map notes must be integers") from error


def _default_auto_report_path(midi: Path) -> Path:
    return midi.with_name(f"{midi.name}.auto-report.json")


def _default_auto_project_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}.pa800-project.json")


def _run_auto(app: EnhancerApplication, args) -> int:
    report_path = args.report or _default_auto_report_path(args.midi)
    if report_path.exists() and not args.overwrite:
        print(f"error: refusing to overwrite {report_path}")
        return 2
    if args.apply and args.output is None:
        print("error: --output is required with --apply")
        return 2
    if args.output is not None:
        if args.output.exists() and not args.overwrite:
            print(f"error: refusing to overwrite {args.output}")
            return 2
        try:
            if args.midi.resolve() == args.output.resolve():
                print("error: auto output must differ from the input MIDI")
                return 2
        except OSError:
            pass

    policy_loader = AutoPolicyLoader()
    try:
        policy = policy_loader.load(args.policy)
        profile = DeviceProfileLoader().load(args.profile) if args.profile else None
        if policy.profile is not None:
            if profile is None:
                raise ValueError("selected policy requires --profile")
            profile_digest = DeviceProfileLoader().digest(profile)
            if (
                profile.profile_id != policy.profile.profile_id
                or profile_digest != policy.profile.sha256
            ):
                raise ValueError("selected profile does not match the policy profile lock")
        if (args.sound_map or args.drum_map) and profile is None:
            raise ValueError("--profile is required for sound or drum mapping")

        song = app.import_midi(args.midi)
        registry = ProposalRegistry(song_revision(song))
        register_all(
            registry,
            adapt_controller_thinning(
                song, app.simplify_controller_curves(song, args.tolerance)
            ),
        )
        register_all(
            registry,
            adapt_expression_conversion(
                song, app.analyze_expression_conversion(song, args.max_error_db)
            ),
        )
        if args.init:
            targets = tuple(_parse_auto_init(value) for value in args.init)
            registry.register(
                adapt_initialization_update(
                    song, app.plan_initialization_update(song, targets)
                )
            )
        for value in args.sound_map:
            request = _parse_auto_sound(value)
            plan = app.plan_sound_mapping(
                song,
                profile,
                request,
                minimum_identity_status=args.minimum_status,
                target_model=args.model,
                target_os_version=args.os_version,
                target_musical_resources_version=args.resources_version,
            )
            registry.register(adapt_sound_mapping(song, profile, plan))
        for value in args.drum_map:
            request = _parse_auto_drum(value)
            plan = app.plan_drum_mapping(
                song,
                profile,
                request,
                minimum_identity_status=args.minimum_status,
                target_model=args.model,
                target_os_version=args.os_version,
                target_musical_resources_version=args.resources_version,
            )
            registry.register(adapt_drum_mapping(song, profile, plan))

        approvals = list(dict.fromkeys(args.approve))
        if args.interactive:
            plan = registry.build_plan()
            entries = {item.proposal_id: item for item in plan.entries}
            for decision in evaluate_policy(plan, policy):
                if decision.action is not PolicyAction.REVIEW:
                    continue
                if decision.proposal_id in approvals:
                    continue
                entry = entries[decision.proposal_id]
                answer = input(
                    f"Approve {decision.proposal_id} "
                    f"risk={entry.risk.name.lower()} targets={len(entry.targets)}? [y/N] "
                ).strip().lower()
                if answer in ("y", "yes", "da", "d"):
                    approvals.append(decision.proposal_id)

        workflow = AutoWorkflow()
        prepared = workflow.prepare(
            song,
            registry,
            policy,
            approved_proposal_ids=tuple(approvals),
        )
        output_sha256 = None
        output_name = None
        project_name = None
        if args.apply:
            simulation = prepared.simulation.report
            if (
                simulation.status != "simulated"
                or simulation.blockers
                or not simulation.selected_proposal_ids
            ):
                raise ValueError("auto apply requires a successful non-empty simulation")
            current = app.import_midi(args.midi)
            if (
                current.source_sha256 != song.source_sha256
                or song_revision(current) != song_revision(song)
            ):
                raise ValueError("input MIDI changed after auto analysis")
            history = workflow.commit(song, registry, prepared)
            app.export_midi(history.song, args.output, mode=args.export_mode)
            output_sha256 = hashlib.sha256(args.output.read_bytes()).hexdigest()
            output_name = args.output.name
            project_path = args.project or _default_auto_project_path(args.output)
            project = app.create_project(history.song, history)
            autosave_path = app.autosave_project(project, project_path)
            project_name = autosave_path.name

        profile_digest = DeviceProfileLoader().digest(profile) if profile else None
        report = build_auto_report(
            prepared,
            policy,
            input_name=args.midi.name,
            input_sha256=song.source_sha256,
            profile_id=profile.profile_id if profile else None,
            profile_sha256=profile_digest,
            output_name=output_name,
            output_sha256=output_sha256,
            project_name=project_name,
        )
        write_auto_report(report_path, report)
    except (
        OSError,
        ValueError,
        AutoPolicyFormatError,
        ProfileFormatError,
    ) as error:
        print(f"error: {error}")
        return 2

    summary = {
        "status": prepared.simulation.report.status,
        "plan_digest": prepared.plan.digest,
        "simulation_digest": prepared.simulation.report.digest,
        "selected": prepared.simulation.report.selected_proposal_ids,
        "deferred": prepared.simulation.report.deferred_proposal_ids,
        "blockers": prepared.simulation.report.blockers,
        "output": str(args.output) if output_name else None,
        "report": str(report_path),
        "project": project_name,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 2 if prepared.simulation.report.status in ("blocked", "rolled_back") else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "artifacts":
        try:
            if args.artifact_command == "create":
                specifications=[]
                for entry in args.entry:
                    parts=[item.strip() for item in entry.split(",")]
                    if len(parts)!=5: raise ValueError("artifact entry requires id,type,path,schema,status")
                    schema=None if parts[3].casefold()=="none" else int(parts[3])
                    specifications.append((parts[0],parts[1],Path(parts[2]),schema,parts[4]))
                manifest=build_manifest(args.root,tuple(specifications)); write_manifest(manifest,args.output)
                print(json.dumps({"artifacts":len(manifest.artifacts),"output":str(args.output)},indent=2)); return 0
            manifest=load_manifest(args.manifest); audit=audit_manifest(manifest,args.root)
            print(json.dumps(asdict(audit)|{"ok":audit.ok},indent=2,ensure_ascii=False)); return 0 if audit.ok else 2
        except (OSError,ValueError,json.JSONDecodeError) as error:
            print(f"error: {error}"); return 2
    if args.command == "corpus":
        try:
            report = CorpusRunner().run(args.sources)
            if args.output:
                write_corpus_report(report, args.output)
            summary = asdict(report)
            summary.pop("entries")
            if args.output:
                summary["output"] = str(args.output)
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        except (OSError, ValueError) as error:
            print(f"error: {error}")
            return 2
        return 2 if report.failed or (args.fail_on_blocked and report.blocked) else 0
    if args.command == "reference-learn":
        try:
            catalog = ReferenceLearner().learn(
                tuple(args.sources),
                gold_match=args.gold_match,
                factory_match=args.factory_match,
            )
            write_reference_catalog(catalog, args.output)
        except (OSError, ValueError) as error:
            print(f"error: {error}")
            return 2
        print(json.dumps({
            "profiles": len(catalog.profiles),
            "sources": len(catalog.source_sha256),
            "output": str(args.output),
        }, indent=2, ensure_ascii=False))
        return 0
    if args.command == "dna-learn":
        try:
            result = DnaLearner().learn(
                tuple(args.sources), database_path=args.database,
                gold_match=args.gold_match, factory_match=args.factory_match,
                force=args.force,
            )
        except (OSError, RuntimeError, ValueError) as error:
            print(f"error: {error}")
            return 2
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
        return 2 if result.failed else 0
    if args.command == "dna-audit":
        try:
            print(json.dumps(asdict(audit_database(args.database)), indent=2, ensure_ascii=False))
            return 0
        except (OSError, RuntimeError, ValueError) as error:
            print(f"error: {error}")
            return 2
    if args.command == "generator-train":
        try: result=train_generator(tuple(args.sources),args.checkpoint,epochs=args.epochs,batch_size=args.batch_size,threads=args.threads,limit=args.limit,resume=args.resume)
        except (OSError,RuntimeError,ValueError) as error: print(f"error: {error}"); return 2
        print(json.dumps(asdict(result),indent=2,ensure_ascii=False)); return 0
    if args.command == "generator-generate":
        try:
            generated={}; config=None
            for index,role in enumerate(args.roles):
                raw,config=generate_notes(args.checkpoint,role,args.notes,temperature=args.temperature,top_k=args.top_k,seed=args.seed+index)
                harmonic=arrange_harmonically(raw,role,key=args.key,scale=args.scale)
                generated[role]=fit_song_form(harmonic,role,SongForm(args.bars),style=STYLE_PRESETS[args.style])
            tempo=args.tempo or STYLE_PRESETS[args.style].tempo
            write_generated_midi(args.output,generated,config,tempo=tempo,bars=args.bars)
            app=EnhancerApplication(); song=app.import_midi(args.output); blockers=[i.message for i in app.validate(song) if i.blocks_export]
            if blockers: raise ValueError("generated MIDI blocked validation: "+"; ".join(blockers[:5]))
        except (OSError,RuntimeError,ValueError) as error: print(f"error: {error}"); return 2
        print(json.dumps({"output":str(args.output),"roles":args.roles,"notes_per_role":args.notes,"bars":args.bars,"style":args.style,"tempo":tempo,"key":args.key,"scale":args.scale,"validated":True},indent=2)); return 0
    if args.command == "factory-retrieve":
        try:
            meter=tuple(int(item) for item in args.meter.split("/"))
            if len(meter)!=2 or min(meter)<=0: raise ValueError("--meter must use positive NUMERATOR/DENOMINATOR")
            index=FactoryIndex.load(args.catalog)
            result=index.retrieve(FactoryQuery(args.family,args.variation,meter,args.density,args.drum_density,args.off16_ratio,args.minimum_channels),limit=args.limit)
            print(json.dumps({"catalog":index.source,"indexed_styles":len(index.styles),"candidates":[asdict(item) for item in result]},indent=2,ensure_ascii=False)); return 0
        except (OSError,ValueError,json.JSONDecodeError) as error: print(f"error: {error}"); return 2
    if args.command == "factory-index":
        try:
            catalog=FactoryCorpusIndexer().build(args.source,factory_member=args.factory_member,limit=args.limit,workers=args.workers); write_factory_catalog(catalog,args.output)
            role_counts={}
            for element in catalog.elements:
                for role in element.roles: role_counts[role.role]=role_counts.get(role.role,0)+1
            truncated=sum(element.boundary_truncated_events for element in catalog.elements)
            print(json.dumps({"source":catalog.source_locator,"elements":len(catalog.elements),"failures":len(catalog.failures),"boundary_truncated_events":truncated,"roles":role_counts,"output":str(args.output)},indent=2,ensure_ascii=False)); return 2 if catalog.failures else 0
        except (OSError,ValueError,zipfile.BadZipFile) as error: print(f"error: {error}"); return 2
    if args.command == "factory-package":
        try:
            meter=tuple(int(item) for item in args.meter.split("/"))
            if len(meter)!=2 or min(meter)<=0: raise ValueError("--meter must use positive NUMERATOR/DENOMINATOR")
            grooves=FactoryIndex.load(args.groove_catalog); patterns=load_factory_catalog(args.pattern_catalog); index=FactoryPackageIndex(grooves,patterns)
            query=FactoryPackageQuery(FactoryQuery(args.family,args.variation,meter,args.density,args.drum_density,args.off16_ratio,args.minimum_channels),tuple(args.roles),tuple(args.include_types))
            candidates=index.retrieve(query,limit=args.limit); payload=[]
            for candidate in candidates:
                elements=[]
                for element in candidate.elements:
                    elements.append({"locator":element.locator,"sha256":element.sha256,"type":element.element_type,"variation":element.variation_level,"evidence_status":element.evidence_status,"boundary_truncated_events":element.boundary_truncated_events,"roles":[{"role":role.role,"channel":role.channel,"bank_msb":role.bank_msb,"bank_lsb":role.bank_lsb,"program":role.program,"note_count":role.note_count,"key_range":role.key_range,"velocity_p10_p90":role.velocity_p10_p90} for role in element.roles]})
                payload.append({"style":candidate.style,"family":candidate.family,"score":candidate.score,"evidence":candidate.evidence,"role_coverage":candidate.role_coverage,"missing_roles":candidate.missing_roles,"limitations":candidate.limitations,"elements":elements})
            print(json.dumps({"candidates":payload},indent=2,ensure_ascii=False)); return 0 if candidates else 2
        except (OSError,ValueError,json.JSONDecodeError) as error: print(f"error: {error}"); return 2
    if args.command == "performance-batch":
        if args.report.exists() and not args.overwrite:
            print(f"error: refusing to overwrite {args.report}")
            return 2
        try:
            catalog = load_reference_catalog(args.catalog)
            report = PerformanceBatchRunner().run(
                args.input_directory, args.output_directory, catalog,
                apply=args.apply, overwrite=args.overwrite, seed=args.seed,
            )
            write_batch_report(report, args.report)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"error: {error}")
            return 2
        print(json.dumps({
            "total": report.total,
            "ready": report.ready,
            "exported": report.exported,
            "blocked": report.blocked,
            "failed": report.failed,
            "skipped": report.skipped,
            "elapsed_ms": report.elapsed_ms,
            "report": str(args.report),
        }, indent=2, ensure_ascii=False))
        return 2 if report.blocked or report.failed else 0
    if args.command == "ui":
        try:
            launch_ui(args.midi)
        except RuntimeError as error:
            print(f"error: {error}")
            return 2
        return 0
    if args.command == "windows-scripts":
        try:
            generated = generate_windows_scripts(
                args.output_directory, overwrite=args.overwrite
            )
        except OSError as error:
            print(f"error: {error}")
            return 2
        print(json.dumps(asdict(generated), indent=2, ensure_ascii=False))
        return 0
    if args.command == "policy":
        loader = AutoPolicyLoader()
        if args.policy_command == "schema":
            print(json.dumps(AUTO_POLICY_SCHEMA, indent=2, ensure_ascii=False))
            return 0
        if args.policy_command == "create":
            if args.output.exists() and not args.overwrite:
                print(f"error: refusing to overwrite {args.output}")
                return 2
            if bool(args.profile_id) != bool(args.profile_sha256):
                print("error: --profile-id and --profile-sha256 must be supplied together")
                return 2
            profile = (
                PolicyProfile(args.profile_id, args.profile_sha256)
                if args.profile_id
                else None
            )
            try:
                policy = loader.default(
                    policy_id=args.policy_id,
                    policy_version=args.version,
                    mode=AutomationMode(args.mode),
                    package=AutomationPackage(args.package),
                    profile=profile,
                    seed=args.seed,
                )
                args.output.parent.mkdir(parents=True, exist_ok=True)
                temporary = args.output.with_name(f".{args.output.name}.tmp")
                try:
                    temporary.write_text(loader.dumps(policy), encoding="utf-8")
                    temporary.replace(args.output)
                finally:
                    temporary.unlink(missing_ok=True)
            except (OSError, ValueError, AutoPolicyFormatError) as error:
                print(f"error: {error}")
                return 2
            print(
                f"created policy={policy.policy_id} version={policy.policy_version} "
                f"mode={policy.mode.value} package={policy.package.value} "
                f"sha256={loader.digest(policy)} output={args.output}"
            )
            return 0
        try:
            policy = loader.load(args.policy)
        except AutoPolicyFormatError as error:
            print(f"error: {error}")
            return 2
        if args.policy_command == "show":
            print(loader.dumps(policy), end="")
        else:
            print(
                f"valid policy={policy.policy_id} version={policy.policy_version} "
                f"mode={policy.mode.value} package={policy.package.value} "
                f"modules={len(policy.modules)} sha256={loader.digest(policy)}"
            )
        return 0
    app = EnhancerApplication()
    if args.command == "recover":
        candidate = app.recover_project(args.project, args.output)
        print(candidate.path)
        return 0
    if args.command == "profile":
        loader = DeviceProfileLoader()
        if args.profile_command == "schema":
            print(json.dumps(DEVICE_PROFILE_SCHEMA, indent=2, ensure_ascii=False))
            return 0
        if args.profile_command == "promote-hardware":
            if args.output.exists() and not args.overwrite:
                print(f"error: refusing to overwrite {args.output}")
                return 2
            try:
                if args.source_profile.resolve() == args.output.resolve():
                    raise ValueError("promoted profile output must differ from the source profile")
                source_profile = loader.load(args.source_profile)
                case = HardwareTestLoader().load(args.manifest)
                promotion = promote_hardware_case(
                    source_profile,
                    case,
                    voice_id=args.voice_id,
                    new_profile_id=args.new_profile_id,
                    new_profile_version=args.new_version,
                    assertion_id=args.assertion,
                    source_locator=args.manifest.as_posix(),
                )
                loader.dump(promotion.profile, args.output)
            except (OSError, ValueError, ProfileFormatError, HardwareTestFormatError) as error:
                print(f"error: {error}")
                return 2
            summary = asdict(promotion)
            summary.pop("profile")
            summary["profile_id"] = promotion.profile.profile_id
            summary["profile_version"] = promotion.profile.profile_version
            summary["output"] = str(args.output)
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 0
        try:
            profile = loader.load(args.profile)
        except ProfileFormatError as error:
            print(f"error: {error}")
            return 2
        if args.profile_command == "validate":
            print(
                f"valid profile={profile.profile_id} schema={profile.schema_version} "
                f"sounds={len(profile.sounds)} drum_kits={len(profile.drum_kits)} "
                f"sha256={loader.digest(profile)}"
            )
        else:
            print(loader.dumps(profile), end="")
        return 0
    if args.command == "hardware":
        if args.hardware_command == "generate":
            note = args.note if args.note is not None else (36 if args.kind == "drum" else 60)
            try:
                generated = HardwareProbeGenerator().generate(
                    args.output_directory,
                    kind=args.kind,
                    case_id=args.case_id,
                    bank_msb=args.cc0,
                    bank_lsb=args.cc32,
                    program=args.program,
                    note=note,
                    velocity=args.velocity,
                    expected_name=args.expected_name,
                    expected_kit_name=args.expected_kit_name,
                    os_version=args.os_version,
                    musical_resources_version=args.resources_version,
                    channel=args.channel,
                    overwrite=args.overwrite,
                )
            except (ValueError, OSError) as error:
                print(f"error: {error}")
                return 2
            print(json.dumps(asdict(generated), indent=2, ensure_ascii=False, default=str))
            return 0
        loader = HardwareTestLoader()
        if args.hardware_command == "schema":
            print(json.dumps(HARDWARE_TEST_SCHEMA, indent=2, ensure_ascii=False))
            return 0
        if args.hardware_command == "record-cycle":
            if args.output.exists() and not args.overwrite:
                print(f"error: refusing to overwrite {args.output}")
                return 2
            try:
                if args.manifest.resolve() == args.output.resolve():
                    raise ValueError("cycle output manifest must differ from its input")
                case = loader.load(args.manifest)
                raw_observations = json.loads(
                    args.observations.read_text(encoding="utf-8")
                )
                if not isinstance(raw_observations, dict):
                    raise ValueError("observations file must contain a JSON object")
                audio = (
                    AudioReference(
                        locator=args.audio_locator,
                        sha256=args.audio_sha256,
                        notes=args.audio_notes,
                    )
                    if args.audio_locator
                    else None
                )
                record = record_hardware_cycle(
                    case,
                    cycle=args.cycle,
                    status=args.status,
                    tested_at=args.tested_at,
                    tester=args.tester,
                    output_midi_path=args.output_midi,
                    observations=raw_observations,
                    log=tuple(args.log),
                    notes=args.notes,
                    audio_reference=audio,
                )
                args.output.parent.mkdir(parents=True, exist_ok=True)
                temporary = args.output.with_name(f".{args.output.name}.tmp")
                try:
                    temporary.write_text(loader.dumps(record.case), encoding="utf-8")
                    temporary.replace(args.output)
                finally:
                    temporary.unlink(missing_ok=True)
            except (OSError, ValueError, json.JSONDecodeError, HardwareTestFormatError) as error:
                print(f"error: {error}")
                return 2
            summary = asdict(record)
            summary.pop("case")
            summary["output"] = str(args.output)
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 0
        try:
            case = loader.load(args.manifest)
        except HardwareTestFormatError as error:
            print(f"error: {error}")
            return 2
        if args.hardware_command == "show":
            print(loader.dumps(case), end="")
            return 0
        preflight = HardwareTestHarness().preflight(args.manifest)
        print(json.dumps(asdict(preflight), indent=2, ensure_ascii=False))
        return 2 if preflight.blockers else 0
    if args.command == "database":
        database = LocalDatabase()
        try:
            if args.database_command == "init":
                result = database.initialize(args.path)
            elif args.database_command == "status":
                result = database.status(args.path)
            elif args.database_command == "import-profile":
                result = database.import_profile(args.profile, args.database)
            else:
                result = database.import_hardware_test(args.manifest, args.database)
        except (OSError, RuntimeError, ProfileFormatError, HardwareTestFormatError) as error:
            print(f"error: {error}")
            return 2
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
        return 0
    if args.command == "auto":
        return _run_auto(app, args)
    song = app.import_midi(args.midi)
    if args.command == "harmony":
        try:
            analysis=analyze_harmony(song,minimum_chord_confidence=args.minimum_confidence,chord_context_beats=args.chord_context_beats,temporal_decode=args.temporal_decode)
            payload={"primary_key":analysis.primary_key.label if analysis.primary_key else None,
                     "key_windows":[{"start_tick":window.start_tick,"end_tick":window.end_tick,"candidates":[asdict(item)|{"label":item.label} for item in window.candidates]} for window in analysis.key_windows],
                     "chords":[asdict(item)|{"label":item.label} for item in analysis.chords]}
            if args.store: payload["stored"]=asdict(AnalysisRepository().store_harmony(song,analysis,locator=str(args.midi),path=args.database))
            print(json.dumps(payload,indent=2,ensure_ascii=False)); return 0
        except (OSError,RuntimeError,ValueError) as error: print(f"error: {error}"); return 2
    if args.command == "structure":
        try:
            analysis=analyze_structure(song); payload={"sections":[asdict(item) for item in analysis.sections],"boundaries":[asdict(item) for item in analysis.boundaries],"track_roles":[asdict(item) for item in analysis.track_roles]}
            if args.store: payload["stored"]=asdict(AnalysisRepository().store_structure(song,analysis,locator=str(args.midi),path=args.database))
            print(json.dumps(payload,indent=2,ensure_ascii=False)); return 0
        except (OSError,RuntimeError,ValueError) as error: print(f"error: {error}"); return 2
    if args.command == "energy-map":
        try:
            structure=analyze_structure(song); plan=map_section_energy(structure)
            print(json.dumps(asdict(plan),indent=2,ensure_ascii=False)); return 0
        except (OSError,RuntimeError,ValueError) as error: print(f"error: {error}"); return 2
    if args.command == "factory-song-plan":
        try:
            meter=tuple(int(item) for item in args.meter.split("/"))
            if len(meter)!=2 or min(meter)<=0: raise ValueError("--meter must use positive NUMERATOR/DENOMINATOR")
            energy=map_section_energy(analyze_structure(song)); grooves=FactoryIndex.load(args.groove_catalog); patterns=load_factory_catalog(args.pattern_catalog)
            plan=FactorySongPlanner(grooves,patterns).plan(energy,FactoryQuery(args.family,2,meter,args.density,args.drum_density,args.off16_ratio,args.minimum_channels,args.style))
            assignments=[]
            for item in plan.assignments:
                assignments.append({"section":item.section_index,"label":item.label,"energy":item.energy,"variation":item.variation_level,"primary":{"locator":item.primary.locator,"sha256":item.primary.sha256,"type":item.primary.element_type},"transition":{"locator":item.transition.locator,"sha256":item.transition.sha256,"type":item.transition.element_type} if item.transition else None,"confidence":item.confidence,"evidence":item.evidence})
            print(json.dumps({"style":plan.style,"family":plan.family,"score":plan.score,"role_coverage":plan.role_coverage,"missing_roles":plan.missing_roles,"evidence":plan.evidence,"assignments":assignments},indent=2,ensure_ascii=False)); return 0
        except (OSError,RuntimeError,ValueError,json.JSONDecodeError) as error: print(f"error: {error}"); return 2
    if args.command == "factory-arrange-preview":
        try:
            meter=tuple(int(item) for item in args.meter.split("/"))
            if len(meter)!=2 or min(meter)<=0: raise ValueError("--meter must use positive NUMERATOR/DENOMINATOR")
            structure=analyze_structure(song); energy=map_section_energy(structure); harmony=analyze_harmony(song,chord_context_beats=args.chord_context_beats,temporal_decode=args.temporal_decode)
            grooves=FactoryIndex.load(args.groove_catalog); patterns=load_factory_catalog(args.pattern_catalog); query=FactoryQuery(args.family,2,meter,args.density,args.drum_density,args.off16_ratio,args.minimum_channels,args.style)
            plan=FactorySongPlanner(grooves,patterns).plan(energy,query); repository=FactorySourceRepository(args.factory_source); preview=arrange_song_plan(plan,energy,harmony,repository,target_ppq=song.header.ppq)
            arranged_patterns=preview.patterns; gold_transfer=None
            if args.gold_transfer:
                if not args.gold_catalog.exists(): raise ValueError(f"Gold performance catalog does not exist: {args.gold_catalog}")
                gold_transfer=transfer_gold_performance(arranged_patterns,load_reference_catalog(args.gold_catalog),ppq=song.header.ppq,seed=args.performance_seed)
                arranged_patterns=gold_transfer.patterns
            evaluation=evaluate_arrangement(arranged_patterns,harmony.chords,ppq=song.header.ppq); output=None; materialization=None
            if args.output and evaluation.status!="blocked" and (evaluation.status=="ready" or args.allow_review_preview):
                materialization=materialize_arrangement(arranged_patterns,song); blockers=[item.message for item in app.validate(materialization.song) if item.blocks_export]
                if blockers: raise ValueError("materialized preview blocked MIDI validation: "+"; ".join(blockers[:5]))
                app.writer.write(materialization.song,args.output); output=str(args.output)
            placements=[]
            for placement,pattern in zip(preview.placements,preview.patterns): placements.append(asdict(placement)|{"notes":len(pattern.notes),"harmonized":pattern.harmonized_notes,"inferred":pattern.inferred_chord_notes,"unknown":pattern.unknown_chord_notes})
            transfer_report=None if gold_transfer is None else {"catalog":str(args.gold_catalog),"factory_timing_locked":gold_transfer.factory_timing_locked,"changed_velocities":gold_transfer.changed_velocities,"changed_durations":gold_transfer.changed_durations,"matched_addresses":len(gold_transfer.evidence),"unmatched_addresses":gold_transfer.unmatched_addresses,"evidence":[asdict(item) for item in gold_transfer.evidence]}
            print(json.dumps({"style":plan.style,"family":plan.family,"placements":placements,"gold_transfer":transfer_report,"evaluation":asdict(evaluation),"export_allowed":evaluation.status=="ready","preview_written":output,"materialization":({"notes":materialization.note_count,"trimmed_overlaps":materialization.trimmed_overlaps,"channel_addresses":materialization.channel_addresses,"mixer_levels":materialization.mixer_levels} if materialization else None)},indent=2,ensure_ascii=False)); return 0 if evaluation.status!="blocked" else 2
        except (OSError,RuntimeError,ValueError,json.JSONDecodeError,zipfile.BadZipFile) as error: print(f"error: {error}"); return 2
    if args.command == "dna-optimize":
        try:
            fingerprint = extract_fingerprint(song)
            matches = LocalDatabase().nearest_fingerprints(
                fingerprint, corpus_kind="gold", path=args.database
            )
            result = plan_dna_correction(
                song, matches, strength=args.strength,
                maximum_distance=args.maximum_distance,
            )
            output = None
            if args.apply:
                if not args.output:
                    raise ValueError("--output is required with --apply")
                result.changes.approve_all()
                projected = ChangeEngine().apply(song, result.changes)
                blockers = [issue.message for issue in app.validate(projected) if issue.blocks_export]
                if blockers:
                    raise ValueError("DNA result blocked validation: " + "; ".join(blockers[:5]))
                app.writer.write(projected, args.output)
                output = str(args.output)
            print(json.dumps({
                "fingerprint_id": fingerprint.fingerprint_id,
                "roles": [role.role for role in fingerprint.roles],
                "matches": [
                    {"role": item.role, "source": item.source_locator,
                     "distance": round(item.distance, 6)} for item in matches
                ],
                "changes": len(result.changes.changes),
                "protected_notes": result.protected_notes,
                "applied": args.apply,
                "output": output,
            }, indent=2, ensure_ascii=False))
            return 0
        except (OSError, RuntimeError, ValueError) as error:
            print(f"error: {error}")
            return 2
    if args.command == "inspect":
        print(json.dumps(asdict(app.summarize(song)), indent=2, ensure_ascii=False))
        return 0
    if args.command == "validate":
        return _print_issues(app.validate(song))
    if args.command == "rhythms":
        for candidate in app.detect_rhythms(song):
            print(f"{candidate.score:.2f}\t{candidate.profile_id}\t{candidate.reason}")
        return 0
    if args.command == "parameters":
        analysis = app.analyze_parameters(song)
        print(json.dumps(asdict(analysis), indent=2, ensure_ascii=False))
        return 2 if analysis.issues else 0
    if args.command == "initialization":
        analysis = app.analyze_initialization_bar(song)
        print(json.dumps(asdict(analysis), indent=2, ensure_ascii=False))
        return 2 if analysis.blockers else 0
    if args.command == "init-update":
        requested = (
            (0, args.cc0),
            (32, args.cc32),
            (7, args.volume),
            (10, args.pan),
            (11, args.expression),
            (91, args.reverb),
            (93, args.chorus),
        )
        target = InitializationChannelTarget(
            args.channel,
            args.program,
            tuple((controller, value) for controller, value in requested if value is not None),
        )
        plan = app.plan_initialization_update(song, (target,))
        print(json.dumps(asdict(plan), indent=2, ensure_ascii=False))
        if plan.status == "ready":
            preview = app.preview_initialization_update(song, plan)
            print(json.dumps(asdict(preview), indent=2, ensure_ascii=False))
        if args.apply:
            if args.output is None:
                raise SystemExit("--output is required with --apply")
            transaction = app.build_initialization_update_transaction(
                song, plan, approved=True
            )
            history = app.create_command_history(song)
            updated = history.apply(transaction)
            app.export_midi(updated, args.output)
            print(args.output)
        return 2 if plan.blockers else 0
    if args.command == "sound-map":
        try:
            profile = DeviceProfileLoader().load(args.profile)
        except ProfileFormatError as error:
            print(f"error: {error}")
            return 2
        request = SoundMappingRequest(args.program_event, args.target_voice)
        plan = app.plan_sound_mapping(
            song,
            profile,
            request,
            minimum_identity_status=args.minimum_status,
            target_model=args.model,
            target_os_version=args.os_version,
            target_musical_resources_version=args.resources_version,
        )
        print(json.dumps(asdict(plan), indent=2, ensure_ascii=False))
        if plan.status == "ready":
            preview = app.preview_sound_mapping(song, profile, plan)
            print(json.dumps(asdict(preview), indent=2, ensure_ascii=False))
        if args.apply:
            if args.output is None:
                raise SystemExit("--output is required with --apply")
            transaction = app.build_sound_mapping_transaction(
                song, profile, plan, approved=True
            )
            history = app.create_command_history(song)
            mapped = history.apply(transaction)
            app.export_midi(mapped, args.output)
            print(args.output)
        return 2 if plan.blockers else 0
    if args.command == "drum-map":
        try:
            profile = DeviceProfileLoader().load(args.profile)
        except ProfileFormatError as error:
            print(f"error: {error}")
            return 2
        request = DrumMappingRequest(
            args.program_event,
            args.target_kit,
            args.source_note,
            args.target_note,
        )
        plan = app.plan_drum_mapping(
            song,
            profile,
            request,
            minimum_identity_status=args.minimum_status,
            target_model=args.model,
            target_os_version=args.os_version,
            target_musical_resources_version=args.resources_version,
        )
        print(json.dumps(asdict(plan), indent=2, ensure_ascii=False))
        if plan.status == "ready":
            preview = app.preview_drum_mapping(song, profile, plan)
            print(json.dumps(asdict(preview), indent=2, ensure_ascii=False))
        if args.apply:
            if args.output is None:
                raise SystemExit("--output is required with --apply")
            transaction = app.build_drum_mapping_transaction(
                song, profile, plan, approved=True
            )
            history = app.create_command_history(song)
            mapped = history.apply(transaction)
            app.export_midi(mapped, args.output)
            print(args.output)
        return 2 if plan.blockers else 0
    if args.command == "programs":
        try:
            profile = DeviceProfileLoader().load(args.profile)
        except ProfileFormatError as error:
            print(f"error: {error}")
            return 2
        analysis = app.analyze_programs(
            song,
            profile,
            target_model=args.model,
            target_os_version=args.os_version,
            target_musical_resources_version=args.resources_version,
            minimum_identity_status=args.minimum_status,
        )
        print(json.dumps(asdict(analysis), indent=2, ensure_ascii=False))
        return 2 if any(item.blockers for item in analysis.resolutions) else 0
    if args.command == "curves":
        plans = app.simplify_controller_curves(song, args.tolerance)
        print(json.dumps([asdict(item) for item in plans], indent=2, ensure_ascii=False))
        if args.apply:
            if args.output is None:
                raise SystemExit("--output is required with --apply")
            transaction = app.build_curve_thinning_transaction(
                song, plans, approved=True
            )
            history = app.create_command_history(song)
            optimized = history.apply(transaction)
            app.export_midi(optimized, args.output)
            print(args.output)
        return 0
    if args.command == "sysex":
        analysis = app.analyze_sysex(song)
        print(json.dumps(asdict(analysis), indent=2, ensure_ascii=False))
        return 2 if analysis.issues else 0
    if args.command == "expression":
        plans = app.analyze_expression_conversion(song, args.max_error_db)
        print(json.dumps([asdict(item) for item in plans], indent=2, ensure_ascii=False))
        if args.apply:
            if args.channel is None or args.output is None:
                raise SystemExit("--channel and --output are required with --apply")
            try:
                plan = next(item for item in plans if item.channel == args.channel)
            except StopIteration as error:
                raise SystemExit(f"no CC7 conversion plan for channel {args.channel}") from error
            preview = app.preview_expression_conversion(song, plan)
            print(json.dumps(asdict(preview), indent=2, ensure_ascii=False))
            transaction = app.build_expression_conversion_transaction(
                song, plan, approved=True
            )
            history = app.create_command_history(song)
            converted = history.apply(transaction)
            app.export_midi(converted, args.output)
            print(args.output)
            return 0
        return 2 if any(item.blockers for item in plans) else 0
    if args.command == "export":
        app.export_midi(song, args.output, mode=args.mode)
        print(args.output)
        return 0
    if args.command == "project":
        app.save_project(app.create_project(song), args.output)
        print(args.output)
        return 0
    if args.command == "resample":
        result = app.resample_ppq(song, args.ppq)
        app.export_midi(result.song, args.output, mode="canonical")
        print(f"{args.output} moved_events={result.moved_event_count} ppq={result.source_ppq}->{result.target_ppq}")
        return 0
    if args.command == "optimize":
        changes = app.suggest_basic_optimization(song, args.grid)
        for change in changes.changes:
            print(f"{change.change_id}: {change.field} {change.old_value} -> {change.new_value}: {change.reason}")
        if args.apply:
            if args.output is None:
                raise SystemExit("--output is required with --apply")
            changes.approve_all()
            optimized = app.apply_approved_changes(song, changes)
            app.export_midi(optimized, args.output)
            print(args.output)
        return 0
    if args.command == "velocity-shape":
        if bool(args.catalog) != bool(args.address):
            raise SystemExit("--catalog and --address must be supplied together")
        learned = load_reference_catalog(args.catalog).find(args.address) if args.catalog else None
        result = app.shape_instrument_velocity(song, args.family, seed=args.seed, learned_profile=learned)
        summary = {
            "family": args.family,
            "reference_address": args.address,
            "note_count": result.note_count,
            "changed_count": result.changed_count,
            "protected_out_of_range": result.protected_out_of_range,
            "trill_note_count": result.trill_note_count,
            "changes": [
                {
                    "event_id": change.event_id,
                    "old_velocity": change.old_value,
                    "new_velocity": change.new_value,
                    "reason": change.reason,
                }
                for change in result.changes.changes
            ],
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        if args.apply:
            if args.output is None:
                raise SystemExit("--output is required with --apply")
            result.changes.approve_all()
            shaped = app.apply_approved_changes(song, result.changes)
            app.export_midi(shaped, args.output)
            print(args.output)
        return 0
    if args.command == "velocity-auto":
        catalog = load_reference_catalog(args.catalog)
        result = app.shape_velocity_automatically(song, catalog, seed=args.seed)
        print(json.dumps({
            "segments": result.segments,
            "changed_count": len(result.changes.changes),
            "unmatched_addresses": result.unmatched_addresses,
        }, indent=2, ensure_ascii=False))
        if args.apply:
            if args.output is None:
                raise SystemExit("--output is required with --apply")
            if not result.changes.changes:
                raise SystemExit("no catalog-backed velocity changes are available")
            result.changes.approve_all()
            shaped = app.apply_approved_changes(song, result.changes)
            app.export_midi(shaped, args.output)
            print(args.output)
        return 2 if result.unmatched_addresses and not result.segments else 0
    if args.command == "articulation-auto":
        catalog = load_reference_catalog(args.catalog)
        result = app.plan_articulations(song, catalog, seed=args.seed)
        counts: dict[str, int] = {}
        for finding in result.findings:
            counts[finding.kind] = counts.get(finding.kind, 0) + 1
        print(json.dumps({
            "finding_counts": counts,
            "changed_count": len(result.changes.changes),
            "processed_addresses": result.processed_addresses,
            "unmatched_addresses": result.unmatched_addresses,
        }, indent=2, ensure_ascii=False))
        if args.apply:
            if args.output is None:
                raise SystemExit("--output is required with --apply")
            if not result.changes.changes:
                raise SystemExit("no catalog-backed articulation changes are available")
            result.changes.approve_all()
            articulated = app.apply_approved_changes(song, result.changes)
            app.export_midi(articulated, args.output)
            print(args.output)
        return 2 if result.unmatched_addresses and not result.processed_addresses else 0
    if args.command == "performance-auto":
        catalog = load_reference_catalog(args.catalog)
        result = app.run_performance_pipeline(song, catalog, seed=args.seed)
        summary = {
            "source_revision": result.source_revision,
            "velocity_revision": result.velocity_revision,
            "final_revision": result.final_revision,
            "repair_changes": len(result.repairs.changes),
            "velocity_changes": len(result.velocity.changes.changes),
            "articulation_changes": len(result.articulation.changes.changes),
            "segments": result.velocity.segments,
            "unmatched_addresses": sorted(set(result.velocity.unmatched_addresses) | set(result.articulation.unmatched_addresses)),
            "validation_issue_counts": {},
            "blockers": result.blockers,
        }
        for issue in result.validation_issues:
            counts = summary["validation_issue_counts"]
            counts[issue.code] = counts.get(issue.code, 0) + 1
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.report.with_name(f".{args.report.name}.tmp")
            try:
                temporary.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                temporary.replace(args.report)
            finally:
                temporary.unlink(missing_ok=True)
        if args.apply:
            if args.output is None:
                raise SystemExit("--output is required with --apply")
            if result.blockers:
                raise SystemExit("performance export is blocked by projected validation")
            app.export_midi(result.projected_song, args.output)
            print(args.output)
        return 2 if result.blockers else 0
    return 1
