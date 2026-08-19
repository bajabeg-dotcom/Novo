#!/usr/bin/env python3
"""
KORG PA800 MIDI Optimizer - Command Line Interface

Usage:
    python midi_optimizer_cli.py optimize input.mid output.mid [--strategy AUTHENTIC]
    python midi_optimizer_cli.py analyze input.mid
    python midi_optimizer_cli.py batch /path/to/files/ /path/to/output/ [--strategy AUTHENTIC]
"""

import argparse
import sys
from pathlib import Path
from midi_optimizer_core import (
    MIDIOptimizerApp,
    OptimizationStrategy
)


class MIDIOptimizerCLI:
    """Command-line interface for MIDI Optimizer"""
    
    def __init__(self):
        self.db_path = Path("/mnt/user-data/outputs/ai_database.json")
        
        if not self.db_path.exists():
            print(f"❌ Sound Behaviour Database not found: {self.db_path}")
            sys.exit(1)
        
        self.app = MIDIOptimizerApp(self.db_path)
    
    def optimize(self, input_file: str, output_file: str, strategy: str = "AUTHENTIC"):
        """Optimize single MIDI file"""
        
        input_path = Path(input_file)
        output_path = Path(output_file)
        
        if not input_path.exists():
            print(f"❌ Input file not found: {input_path}")
            return False
        
        try:
            strat = OptimizationStrategy[strategy.upper()]
        except KeyError:
            print(f"❌ Invalid strategy: {strategy}")
            print(f"   Available: {', '.join(s.value for s in OptimizationStrategy)}")
            return False
        
        try:
            result = self.app.optimize_file(input_path, output_path, strat)
            
            if result.get("success"):
                print(f"\n✅ Optimization successful!")
                print(f"   Input:   {result['input_file']}")
                print(f"   Output:  {result['output_file']}")
                print(f"   Strategy: {result['strategy']}")
                print(f"   Notes:   {result['total_notes']}")
                print(f"   Adjusted: {result['adjusted_notes']} ({result['adjusted_notes']*100/result['total_notes']:.1f}%)")
                print(f"   Avg velocity change: {result['average_adjustment']:.1f}")
                return True
            else:
                print(f"❌ Optimization failed: {result.get('error', 'Unknown error')}")
                return False
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return False
    
    def analyze(self, input_file: str):
        """Analyze MIDI file"""
        
        input_path = Path(input_file)
        
        if not input_path.exists():
            print(f"❌ Input file not found: {input_path}")
            return False
        
        try:
            result = self.app.analyze_file(input_path)
            
            print(f"\n📊 MIDI Analysis Results")
            print(f"{'='*60}")
            print(f"File: {input_path.name}")
            print(f"Size: {input_path.stat().st_size:,} bytes")
            print(f"Total notes: {result.get('total_notes', 0)}")
            print(f"Programs used: {len(result.get('programs', {}))}")
            
            print(f"\nProgram Details:")
            print(f"  Program | Notes   | Velocity Range")
            print(f"  {'-'*40}")
            
            for prog in sorted(result.get('programs', {}).keys()):
                count = result['programs'][prog]
                vel_stats = result.get('velocity_stats', {}).get(str(prog), {})
                vel_min = int(vel_stats.get('min', 0))
                vel_max = int(vel_stats.get('max', 0))
                print(f"  {prog:7d} | {count:7d} | {vel_min:3d} - {vel_max:3d}")
            
            if result.get('registers'):
                print(f"\nRegister Distribution:")
                for register, count in sorted(result['registers'].items()):
                    pct = count * 100 / result.get('total_notes', 1)
                    print(f"  {register:10s}: {count:6d} ({pct:5.1f}%)")
            
            return True
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return False
    
    def batch(self, input_dir: str, output_dir: str, strategy: str = "AUTHENTIC"):
        """Batch process directory of MIDI files"""
        
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        
        if not input_path.is_dir():
            print(f"❌ Input directory not found: {input_path}")
            return False
        
        if not output_path.exists():
            output_path.mkdir(parents=True, exist_ok=True)
        
        try:
            strat = OptimizationStrategy[strategy.upper()]
        except KeyError:
            print(f"❌ Invalid strategy: {strategy}")
            return False
        
        # Find all MIDI files
        midi_files = list(input_path.glob("*.mid")) + list(input_path.glob("**/*.mid"))
        
        if not midi_files:
            print(f"❌ No MIDI files found in {input_path}")
            return False
        
        print(f"\n📦 Batch Processing {len(midi_files)} files")
        print(f"   Input:  {input_path}")
        print(f"   Output: {output_path}")
        print(f"   Strategy: {strategy}")
        print(f"   {'='*60}")
        
        successful = 0
        failed = 0
        
        for i, midi_file in enumerate(sorted(midi_files), 1):
            output_file = output_path / f"{midi_file.stem}_optimized.mid"
            
            print(f"\n[{i}/{len(midi_files)}] Processing: {midi_file.name}")
            
            try:
                result = self.app.optimize_file(midi_file, output_file, strat)
                
                if result.get("success"):
                    print(f"   ✅ {result['adjusted_notes']} notes optimized")
                    successful += 1
                else:
                    print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
                    failed += 1
            
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                failed += 1
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Batch Processing Complete")
        print(f"{'='*60}")
        print(f"Total: {len(midi_files)}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"\nOutput files saved to: {output_path}")
        
        return failed == 0


def main():
    parser = argparse.ArgumentParser(
        description="KORG PA800 MIDI Optimizer - Optimize MIDI using factory sound behavior patterns"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Optimize command
    optimize_parser = subparsers.add_parser("optimize", help="Optimize single MIDI file")
    optimize_parser.add_argument("input", help="Input MIDI file")
    optimize_parser.add_argument("output", help="Output MIDI file")
    optimize_parser.add_argument("--strategy", default="AUTHENTIC",
                               choices=[s.value for s in OptimizationStrategy],
                               help="Optimization strategy")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze MIDI file")
    analyze_parser.add_argument("input", help="Input MIDI file")
    
    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Batch process MIDI files")
    batch_parser.add_argument("input_dir", help="Input directory")
    batch_parser.add_argument("output_dir", help="Output directory")
    batch_parser.add_argument("--strategy", default="AUTHENTIC",
                            choices=[s.value for s in OptimizationStrategy],
                            help="Optimization strategy")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    cli = MIDIOptimizerCLI()
    
    if args.command == "optimize":
        success = cli.optimize(args.input, args.output, args.strategy)
        sys.exit(0 if success else 1)
    
    elif args.command == "analyze":
        success = cli.analyze(args.input)
        sys.exit(0 if success else 1)
    
    elif args.command == "batch":
        success = cli.batch(args.input_dir, args.output_dir, args.strategy)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
