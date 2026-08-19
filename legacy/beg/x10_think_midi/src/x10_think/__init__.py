"""
X10 Think - Python MIDI Intelligence Engine

A professional-grade Python desktop application that intelligently analyzes 
and enhances Standard MIDI Files using deterministic musical rules, music 
theory principles, and instrument-specific performance logic.

This system operates entirely through a rule-based musical intelligence engine
without any neural networks, machine learning, or reference MIDI datasets.

Author: Senior Python Software Architect
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "X10 Think Team"
__license__ = "MIT"

from .core.application import Application
from .core.engine import EngineCoordinator

__all__ = ["Application", "EngineCoordinator", "__version__"]
