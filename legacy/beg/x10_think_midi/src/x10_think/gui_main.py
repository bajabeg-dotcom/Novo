#!/usr/bin/env python3
"""
X10 Think MIDI Intelligence Engine - GUI Entry Point

This module serves as the main entry point for launching the graphical user interface.
"""

import sys
import logging
from pathlib import Path

# Configure logging before importing GUI components
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the GUI application."""
    try:
        # Import core components
        from x10_think.core.config_manager import ConfigManager
        from x10_think.core.event_bus import EventBus
        from x10_think.core.engine import EngineCoordinator
        
        # Import PyQt6 and main window
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        from x10_think.gui.main_window import MainWindow
        
        # Initialize core components
        config_manager = ConfigManager()
        event_bus = EventBus()
        engine_coordinator = EngineCoordinator(config_manager, event_bus)
        
        # Enable high DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        
        # Create application instance
        app = QApplication(sys.argv)
        app.setApplicationName("X10 Think MIDI")
        app.setOrganizationName("X10 Think")
        app.setStyle("Fusion")  # Use Fusion style for consistent cross-platform look
        
        # Apply dark palette
        from PyQt6.QtGui import QPalette, QColor
        
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        
        app.setPalette(dark_palette)
        
        # Create and show main window with required dependencies
        window = MainWindow(
            config_manager=config_manager,
            event_bus=event_bus,
            engine_coordinator=engine_coordinator
        )
        window.show()
        
        logger.info("X10 Think GUI started successfully")
        
        # Run event loop
        sys.exit(app.exec())
        
    except ImportError as e:
        logger.error(f"Failed to import GUI dependencies: {e}")
        print(f"\n[ERROR] Failed to start GUI: {e}")
        print("\nMake sure PyQt6 is installed:")
        print("  pip install PyQt6")
        print("\nOr run the installation script:")
        print("  install.bat")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error starting GUI: {e}")
        print(f"\n[ERROR] Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
