"""
KORG PA800 Factory Intelligence - Dataset Discovery

Discovers and validates the Factory Style MIDI dataset.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import NamedTuple

from .config import CANONICAL_FACTORY_DIR, EXPECTED_STYLE_COUNT, MIDI_EXTENSIONS


logger = logging.getLogger(__name__)


class DiscoveredFile(NamedTuple):
    """Represents a discovered MIDI file."""
    path: Path
    filename: str
    sha256: str
    style_id: str


class DiscoveryResult(NamedTuple):
    """Result of dataset discovery."""
    success: bool
    files: list[DiscoveredFile]
    expected_count: int
    found_count: int
    duplicates: int
    errors: list[str]


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def generate_style_id(filename: str, sha256: str) -> str:
    """
    Generate a stable style ID from filename and content hash.
    
    Format: first 8 chars of SHA-256 + sanitized filename prefix
    """
    hash_prefix = sha256[:8]
    name_part = filename.rsplit(".", 1)[0][:20].replace(" ", "_").replace("-", "_")
    return f"{hash_prefix}_{name_part}"


def find_midi_files(directory: Path) -> list[Path]:
    """Find all MIDI files in a directory (non-recursive)."""
    if not directory.exists():
        return []
    
    midi_files = []
    for item in directory.iterdir():
        if item.is_file() and item.suffix in MIDI_EXTENSIONS:
            midi_files.append(item)
    
    return sorted(midi_files)


def discover_dataset() -> DiscoveryResult:
    """
    Discover and validate the Factory Style dataset.
    
    Returns:
        DiscoveryResult with validation status and file information.
    """
    errors = []
    
    # Check canonical directory exists
    if not CANONICAL_FACTORY_DIR.exists():
        return DiscoveryResult(
            success=False,
            files=[],
            expected_count=EXPECTED_STYLE_COUNT,
            found_count=0,
            duplicates=0,
            errors=[f"Canonical directory not found: {CANONICAL_FACTORY_DIR}"]
        )
    
    if not CANONICAL_FACTORY_DIR.is_dir():
        return DiscoveryResult(
            success=False,
            files=[],
            expected_count=EXPECTED_STYLE_COUNT,
            found_count=0,
            duplicates=0,
            errors=[f"Canonical path is not a directory: {CANONICAL_FACTORY_DIR}"]
        )
    
    # Find MIDI files
    midi_files = find_midi_files(CANONICAL_FACTORY_DIR)
    found_count = len(midi_files)
    
    logger.info(f"Found {found_count} MIDI files in {CANONICAL_FACTORY_DIR}")
    
    if found_count == 0:
        return DiscoveryResult(
            success=False,
            files=[],
            expected_count=EXPECTED_STYLE_COUNT,
            found_count=0,
            duplicates=0,
            errors=["No MIDI files found in canonical directory"]
        )
    
    # Process files and detect duplicates
    discovered_files: list[DiscoveredFile] = []
    sha256_to_file: dict[str, DiscoveredFile] = {}
    duplicate_count = 0
    
    for file_path in midi_files:
        try:
            sha256 = compute_sha256(file_path)
            style_id = generate_style_id(file_path.name, sha256)
            
            discovered_file = DiscoveredFile(
                path=file_path,
                filename=file_path.name,
                sha256=sha256,
                style_id=style_id
            )
            
            # Check for content duplicates
            if sha256 in sha256_to_file:
                duplicate_count += 1
                logger.warning(f"Duplicate content detected: {file_path.name} matches {sha256_to_file[sha256].filename}")
            else:
                sha256_to_file[sha256] = discovered_file
                discovered_files.append(discovered_file)
                
        except Exception as e:
            errors.append(f"Failed to process {file_path.name}: {e}")
            logger.error(f"Failed to process {file_path.name}: {e}")
    
    # Validate count
    unique_count = len(discovered_files)
    
    if unique_count != EXPECTED_STYLE_COUNT:
        errors.append(
            f"Expected {EXPECTED_STYLE_COUNT} unique styles, found {unique_count}"
        )
    
    success = (
        unique_count == EXPECTED_STYLE_COUNT and
        duplicate_count == 0 and
        len(errors) == 0
    )
    
    result = DiscoveryResult(
        success=success,
        files=discovered_files,
        expected_count=EXPECTED_STYLE_COUNT,
        found_count=unique_count,
        duplicates=duplicate_count,
        errors=errors
    )
    
    logger.info(
        f"Discovery complete: {unique_count}/{EXPECTED_STYLE_COUNT} styles, "
        f"{duplicate_count} duplicates, {len(errors)} errors"
    )
    
    return result


def validate_dataset() -> tuple[bool, str]:
    """
    Quick validation of the dataset.
    
    Returns:
        Tuple of (is_valid, message)
    """
    result = discover_dataset()
    
    if not result.success:
        message = f"VALIDATION FAILED: {'; '.join(result.errors)}"
        return False, message
    
    message = (
        f"VALIDATION PASSED: {result.found_count}/{result.expected_count} styles, "
        f"{result.duplicates} duplicates"
    )
    return True, message
