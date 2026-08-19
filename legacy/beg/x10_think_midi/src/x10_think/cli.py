"""
Command Line Interface for X10 Think MIDI Intelligence Engine.
"""

import sys
import argparse
from pathlib import Path


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="x10-think",
        description="X10 Think - Python MIDI Intelligence Engine"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Process command
    process_parser = subparsers.add_parser("process", help="Process a MIDI file")
    process_parser.add_argument("input", type=Path, help="Input MIDI file")
    process_parser.add_argument("output", type=Path, nargs="?", help="Output MIDI file")
    process_parser.add_argument("--config", type=Path, help="Configuration file")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a MIDI file")
    analyze_parser.add_argument("input", type=Path, help="Input MIDI file")
    analyze_parser.add_argument("--output", type=Path, help="Output report file")
    analyze_parser.add_argument("--config", type=Path, help="Configuration file")
    
    # GUI command
    gui_parser = subparsers.add_parser("gui", help="Launch GUI mode")
    gui_parser.add_argument("--config", type=Path, help="Configuration file")
    
    # Interactive command
    interactive_parser = subparsers.add_parser("interactive", help="Interactive mode")
    interactive_parser.add_argument("--config", type=Path, help="Configuration file")
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 0
    
    # Import application here to avoid circular imports
    from x10_think.core.application import Application
    
    app = Application()
    
    try:
        config_path = getattr(args, 'config', None)
        
        if not app.initialize(config_path):
            print("Failed to initialize application", file=sys.stderr)
            return 1
        
        if args.command == "process":
            return _cmd_process(app, args)
        elif args.command == "analyze":
            return _cmd_analyze(app, args)
        elif args.command == "gui":
            return app.run(gui_mode=True)
        elif args.command == "interactive":
            return app.run(gui_mode=False)
        else:
            parser.print_help()
            return 1
            
    finally:
        app.shutdown()


def _cmd_process(app: Application, args) -> int:
    """Handle the process command."""
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1
    
    result = app.engine_coordinator.process_midi_file(
        args.input,
        args.output
    )
    
    if result.success:
        print(f"✓ Processing completed in {result.processing_time_ms:.2f}ms")
        if result.output_file:
            print(f"  Output: {result.output_file}")
        return 0
    else:
        print("✗ Processing failed:")
        for error in result.errors:
            print(f"  - {error}")
        return 1


def _cmd_analyze(app: Application, args) -> int:
    """Handle the analyze command."""
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1
    
    print(f"Analyzing: {args.input}")
    print("Analysis functionality coming soon...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
