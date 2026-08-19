"""
Engine Coordinator Module

Orchestrates the execution of all engines in the X10 Think system.
Manages engine lifecycle, dependencies, and processing pipelines.
"""

from typing import Dict, List, Optional, Any, Type
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import logging

from ..core.event_bus import EventBus, Event
from ..core.config_manager import ConfigManager, AppConfig

logger = logging.getLogger(__name__)


@dataclass
class EngineStatus:
    """Status information for an engine."""
    
    name: str
    enabled: bool
    initialized: bool = False
    last_run: Optional[datetime] = None
    last_error: Optional[str] = None
    processing_time_ms: float = 0.0


@dataclass
class ProcessingResult:
    """Result of a MIDI processing operation."""
    
    success: bool
    input_file: Path
    output_file: Optional[Path] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    analysis_data: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class EngineCoordinator:
    """
    Central orchestrator for all X10 Think engines.
    
    This class manages the initialization, configuration, and execution
    of all processing engines in the correct order. It handles dependency
    injection, error handling, and result aggregation.
    
    The processing pipeline follows this order:
    1. Parser Engine - Extract MIDI data
    2. Track Intelligence Engine - Classify tracks
    3. Harmony Engine - Analyze harmonic structure
    4. RX Engine - Apply articulations
    5. Velocity Engine - Shape velocities
    6. Expression Engine - Add expression controllers
    7. Humanization Engine - Apply humanization
    8. Musical Rules Engine - Final rule validation
    
    Example:
        >>> coordinator = EngineCoordinator(config, event_bus)
        >>> coordinator.initialize()
        >>> result = coordinator.process_midi_file("input.mid", "output.mid")
        >>> if result.success:
        ...     print(f"Processed in {result.processing_time_ms}ms")
    """
    
    def __init__(self, config_manager: ConfigManager, event_bus: EventBus) -> None:
        """
        Initialize the engine coordinator.
        
        Args:
            config_manager: Configuration manager instance.
            event_bus: Event bus for inter-component communication.
        """
        self._config_manager = config_manager
        self._event_bus = event_bus
        self._engines: Dict[str, Any] = {}
        self._engine_status: Dict[str, EngineStatus] = {}
        self._initialized = False
        
        logger.debug("EngineCoordinator initialized")
    
    @property
    def is_initialized(self) -> bool:
        """Check if all engines are initialized."""
        return self._initialized
    
    @property
    def engine_status(self) -> Dict[str, EngineStatus]:
        """Get status information for all engines."""
        return self._engine_status.copy()
    
    def initialize(self) -> bool:
        """
        Initialize all engines in the correct order.
        
        Returns:
            True if all engines initialized successfully, False otherwise.
        """
        logger.info("Initializing engine coordinator...")
        
        try:
            # Initialize engines in dependency order
            self._init_parser_engine()
            self._init_track_intelligence_engine()
            self._init_harmony_engine()
            self._init_rx_engine()
            self._init_velocity_engine()
            self._init_expression_engine()
            self._init_humanization_engine()
            self._init_musical_rules_engine()
            
            self._initialized = True
            logger.info("All engines initialized successfully")
            
            self._event_bus.publish(Event(
                name="engines.initialized",
                payload={"engine_count": len(self._engines)},
                source="EngineCoordinator"
            ))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize engines: {e}", exc_info=True)
            return False
    
    def shutdown(self) -> None:
        """Shutdown all engines gracefully."""
        logger.info("Shutting down engine coordinator...")
        
        for engine_name, engine in self._engines.items():
            try:
                if hasattr(engine, 'shutdown'):
                    engine.shutdown()
                logger.debug(f"Engine '{engine_name}' shut down")
            except Exception as e:
                logger.error(f"Error shutting down {engine_name}: {e}")
        
        self._engines.clear()
        self._initialized = False
        
        self._event_bus.publish(Event(
            name="engines.shutdown",
            source="EngineCoordinator"
        ))
    
    def process_midi_file(self, input_path: Path, output_path: Optional[Path] = None) -> ProcessingResult:
        """
        Process a MIDI file through all engines.
        
        Args:
            input_path: Path to the input MIDI file.
            output_path: Optional path for the output file. If None,
                        the input file will be modified in place.
        
        Returns:
            ProcessingResult containing success status and analysis data.
        """
        start_time = datetime.now()
        result = ProcessingResult(success=False, input_file=input_path)
        
        if not self._initialized:
            result.errors.append("Engines not initialized")
            return result
        
        if not input_path.exists():
            result.errors.append(f"Input file not found: {input_path}")
            return result
        
        logger.info(f"Processing MIDI file: {input_path}")
        
        try:
            # Step 1: Parse MIDI file
            parser_result = self._engines['parser'].parse_file(input_path)
            if not parser_result:
                result.errors.append("Failed to parse MIDI file")
                return result
            
            midi_data = parser_result
            
            # Step 2: Classify tracks
            track_classification = self._engines['track_intelligence'].classify(midi_data)
            result.analysis_data['track_classification'] = track_classification
            
            # Step 3: Analyze harmony
            harmony_analysis = self._engines['harmony'].analyze(midi_data)
            result.analysis_data['harmony'] = harmony_analysis
            
            # Step 4: Apply articulations (RX)
            rx_applied = self._engines['rx'].apply(midi_data, track_classification)
            result.analysis_data['rx_applied'] = rx_applied
            
            # Step 5: Shape velocities
            velocity_shaped = self._engines['velocity'].apply(midi_data, track_classification)
            result.analysis_data['velocity'] = velocity_shaped
            
            # Step 6: Add expression
            expression_added = self._engines['expression'].apply(midi_data, track_classification)
            result.analysis_data['expression'] = expression_added
            
            # Step 7: Apply humanization
            humanized = self._engines['humanization'].apply(midi_data, track_classification)
            result.analysis_data['humanization'] = humanized
            
            # Step 8: Validate with musical rules
            validation = self._engines['musical_rules'].validate(midi_data)
            result.warnings.extend(validation.get('warnings', []))
            
            # Export processed MIDI
            export_path = output_path or input_path
            export_success = self._engines['parser'].export_file(midi_data, export_path)
            
            if export_success:
                result.success = True
                result.output_file = export_path
            else:
                result.errors.append("Failed to export processed MIDI")
            
        except Exception as e:
            logger.error(f"Error processing MIDI file: {e}", exc_info=True)
            result.errors.append(str(e))
        
        # Calculate processing time
        end_time = datetime.now()
        result.processing_time_ms = (end_time - start_time).total_seconds() * 1000
        
        # Publish completion event
        self._event_bus.publish(Event(
            name="midi.processed",
            payload={
                "success": result.success,
                "input": str(input_path),
                "output": str(result.output_file) if result.output_file else None,
                "processing_time_ms": result.processing_time_ms
            },
            source="EngineCoordinator"
        ))
        
        return result
    
    def get_engine(self, name: str) -> Optional[Any]:
        """
        Get a specific engine by name.
        
        Args:
            name: The engine name.
            
        Returns:
            The engine instance or None if not found.
        """
        return self._engines.get(name)
    
    def _register_engine(self, name: str, engine: Any, enabled: bool) -> None:
        """Register an engine with status tracking."""
        self._engines[name] = engine
        self._engine_status[name] = EngineStatus(
            name=name,
            enabled=enabled,
            initialized=True
        )
        logger.info(f"Engine registered: {name}")
    
    def _init_parser_engine(self) -> None:
        """Initialize the MIDI Parser Engine."""
        from ..engines.parser import MIDIParserEngine
        
        config = self._config_manager.app_config.parser_engine
        engine = MIDIParserEngine(config.parameters)
        self._register_engine('parser', engine, config.enabled)
    
    def _init_track_intelligence_engine(self) -> None:
        """Initialize the Track Intelligence Engine."""
        from ..engines.track_intelligence import TrackIntelligenceEngine
        
        config = self._config_manager.app_config.track_intelligence_engine
        engine = TrackIntelligenceEngine(config.parameters)
        self._register_engine('track_intelligence', engine, config.enabled)
    
    def _init_harmony_engine(self) -> None:
        """Initialize the Harmony Engine."""
        from ..engines.harmony import HarmonyEngine
        
        config = self._config_manager.app_config.harmony_engine
        engine = HarmonyEngine(config.parameters)
        self._register_engine('harmony', engine, config.enabled)
    
    def _init_rx_engine(self) -> None:
        """Initialize the RX (Articulation) Engine."""
        from ..engines.rx import RXEngine
        
        config = self._config_manager.app_config.rx_engine
        engine = RXEngine(config.parameters)
        self._register_engine('rx', engine, config.enabled)
    
    def _init_velocity_engine(self) -> None:
        """Initialize the Velocity Engine."""
        from ..engines.velocity import VelocityEngine
        
        config = self._config_manager.app_config.velocity_engine
        engine = VelocityEngine(config.parameters)
        self._register_engine('velocity', engine, config.enabled)
    
    def _init_expression_engine(self) -> None:
        """Initialize the Expression Engine."""
        from ..engines.expression import ExpressionEngine
        
        config = self._config_manager.app_config.expression_engine
        engine = ExpressionEngine(config.parameters)
        self._register_engine('expression', engine, config.enabled)
    
    def _init_humanization_engine(self) -> None:
        """Initialize the Humanization Engine."""
        from ..engines.humanization import HumanizationEngine
        
        config = self._config_manager.app_config.humanization_engine
        engine = HumanizationEngine(config.parameters)
        self._register_engine('humanization', engine, config.enabled)
    
    def _init_musical_rules_engine(self) -> None:
        """Initialize the Musical Rules Engine."""
        from ..engines.musical_rules import MusicalRulesEngine
        
        config = self._config_manager.app_config.musical_rules_engine
        engine = MusicalRulesEngine(config.parameters)
        self._register_engine('musical_rules', engine, config.enabled)
