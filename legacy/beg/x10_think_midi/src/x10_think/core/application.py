"""
Application Module

Main application class that initializes and runs the X10 Think MIDI Intelligence Engine.
Provides the entry point for both GUI and CLI modes.
"""

from typing import Optional, List
from pathlib import Path
import sys
import logging
from logging.handlers import RotatingFileHandler

from .config_manager import ConfigManager
from .event_bus import EventBus
from .engine import EngineCoordinator

logger = logging.getLogger(__name__)


class Application:
    """
    Main application class for X10 Think MIDI Intelligence Engine.
    
    This class serves as the primary entry point and orchestrates the
    initialization of all application components including configuration,
    logging, database, engines, and the user interface.
    
    Example:
        >>> app = Application()
        >>> app.initialize()
        >>> app.run()
        >>> app.shutdown()
    """
    
    def __init__(self) -> None:
        """Initialize the application with default components."""
        self._config_manager: Optional[ConfigManager] = None
        self._event_bus: Optional[EventBus] = None
        self._engine_coordinator: Optional[EngineCoordinator] = None
        self._initialized = False
        self._running = False
        
        logger.debug("Application instance created")
    
    @property
    def config_manager(self) -> Optional[ConfigManager]:
        """Get the configuration manager instance."""
        return self._config_manager
    
    @property
    def event_bus(self) -> Optional[EventBus]:
        """Get the event bus instance."""
        return self._event_bus
    
    @property
    def engine_coordinator(self) -> Optional[EngineCoordinator]:
        """Get the engine coordinator instance."""
        return self._engine_coordinator
    
    @property
    def is_initialized(self) -> bool:
        """Check if the application is initialized."""
        return self._initialized
    
    @property
    def is_running(self) -> bool:
        """Check if the application is currently running."""
        return self._running
    
    def initialize(self, config_path: Optional[Path] = None) -> bool:
        """
        Initialize the application and all its components.
        
        Args:
            config_path: Optional path to configuration file.
        
        Returns:
            True if initialization was successful, False otherwise.
        """
        logger.info("Initializing X10 Think MIDI Intelligence Engine...")
        
        try:
            # Step 1: Setup logging
            self._setup_logging()
            
            # Step 2: Initialize configuration
            self._config_manager = ConfigManager(config_path)
            self._config_manager.load()
            
            # Apply log level from config
            log_level = getattr(logging, self._config_manager.app_config.log_level)
            logging.getLogger("x10_think").setLevel(log_level)
            
            # Step 3: Initialize event bus
            self._event_bus = EventBus()
            
            # Step 4: Initialize database
            self._init_database()
            
            # Step 5: Initialize engine coordinator
            self._engine_coordinator = EngineCoordinator(
                self._config_manager,
                self._event_bus
            )
            
            if not self._engine_coordinator.initialize():
                logger.error("Failed to initialize engine coordinator")
                return False
            
            # Step 6: Subscribe to system events
            self._setup_event_handlers()
            
            self._initialized = True
            logger.info("Application initialized successfully")
            
            self._event_bus.publish(EventBusEvent(
                name="app.initialized",
                source="Application"
            ))
            
            return True
            
        except Exception as e:
            logger.error(f"Application initialization failed: {e}", exc_info=True)
            return False
    
    def run(self, gui_mode: bool = True) -> int:
        """
        Run the application.
        
        Args:
            gui_mode: If True, launch the GUI. If False, run in CLI mode.
        
        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        if not self._initialized:
            logger.error("Application not initialized. Call initialize() first.")
            return 1
        
        logger.info(f"Starting application in {'GUI' if gui_mode else 'CLI'} mode")
        self._running = True
        
        try:
            if gui_mode:
                return self._run_gui()
            else:
                return self._run_cli()
        except Exception as e:
            logger.error(f"Application runtime error: {e}", exc_info=True)
            return 1
        finally:
            self._running = False
    
    def shutdown(self) -> None:
        """Shutdown the application gracefully."""
        logger.info("Shutting down application...")
        
        try:
            # Shutdown engine coordinator
            if self._engine_coordinator:
                self._engine_coordinator.shutdown()
            
            # Close database connection
            self._close_database()
            
            # Flush and close logging handlers
            logging.shutdown()
            
            self._initialized = False
            
            logger.info("Application shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    def _setup_logging(self) -> None:
        """Configure application logging."""
        # Create logger
        root_logger = logging.getLogger("x10_think")
        root_logger.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        root_logger.addHandler(console_handler)
        
        # File handler (if configured)
        # Will be configured after loading config
    
    def _init_database(self) -> None:
        """Initialize the database connection."""
        from ..database import DatabaseManager
        
        db_path = self._config_manager.app_config.database_path
        if not db_path:
            db_path = "x10_think.db"
        
        self._db_manager = DatabaseManager(db_path)
        self._db_manager.initialize()
        logger.debug("Database initialized")
    
    def _close_database(self) -> None:
        """Close the database connection."""
        if hasattr(self, '_db_manager') and self._db_manager:
            self._db_manager.close()
            logger.debug("Database connection closed")
    
    def _setup_event_handlers(self) -> None:
        """Setup global event handlers."""
        if not self._event_bus:
            return
        
        def on_midi_processed(event):
            payload = event.payload
            logger.info(
                f"MIDI processing completed: {payload.get('success')} "
                f"in {payload.get('processing_time_ms', 0):.2f}ms"
            )
        
        self._event_bus.subscribe("midi.processed", on_midi_processed)
    
    def _run_gui(self) -> int:
        """Run the application in GUI mode."""
        try:
            from ..gui.main_window import MainWindow
            from PyQt6.QtWidgets import QApplication
            
            app = QApplication(sys.argv)
            app.setApplicationName("X10 Think")
            app.setStyle("Fusion")
            
            window = MainWindow(
                config_manager=self._config_manager,
                event_bus=self._event_bus,
                engine_coordinator=self._engine_coordinator
            )
            window.show()
            
            exit_code = app.exec()
            return exit_code
            
        except ImportError:
            logger.warning("PyQt6 not available, falling back to CLI mode")
            return self._run_cli()
    
    def _run_cli(self) -> int:
        """Run the application in CLI mode."""
        print("\n" + "=" * 60)
        print("X10 Think MIDI Intelligence Engine - CLI Mode")
        print("=" * 60)
        print("\nAvailable commands:")
        print("  process <input.mid> [output.mid] - Process a MIDI file")
        print("  analyze <input.mid>              - Analyze a MIDI file")
        print("  export-rules                     - Export current rule set")
        print("  quit                             - Exit application")
        print("\n")
        
        while True:
            try:
                command = input("> ").strip()
                
                if command.lower() in ['quit', 'exit', 'q']:
                    break
                
                parts = command.split()
                if not parts:
                    continue
                
                cmd = parts[0].lower()
                
                if cmd == 'process' and len(parts) >= 2:
                    input_file = Path(parts[1])
                    output_file = Path(parts[2]) if len(parts) > 2 else None
                    
                    result = self._engine_coordinator.process_midi_file(
                        input_file, output_file
                    )
                    
                    if result.success:
                        print(f"✓ Processing completed in {result.processing_time_ms:.2f}ms")
                        if result.output_file:
                            print(f"  Output: {result.output_file}")
                    else:
                        print("✗ Processing failed:")
                        for error in result.errors:
                            print(f"  - {error}")
                
                elif cmd == 'analyze' and len(parts) >= 2:
                    input_file = Path(parts[1])
                    # Analysis logic here
                    print(f"Analysis not yet implemented for: {input_file}")
                
                elif cmd == 'export-rules':
                    # Export rules logic
                    print("Rule export not yet implemented")
                
                else:
                    print(f"Unknown command: {command}")
                    
            except KeyboardInterrupt:
                break
            except EOFError:
                break
        
        return 0


# Import Event here to avoid circular dependency
from .event_bus import Event as EventBusEvent
