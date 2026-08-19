"""Zajednicke fixture za test suite v0.28.0."""

from __future__ import annotations

import os
import struct
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_ENV = "PA800_TEST_CORPUS"


def _vlq(value: int) -> bytes:
    if value == 0:
        return b"\x00"
    chunks = []
    while value:
        chunks.append(value & 0x7F)
        value >>= 7
    out = bytearray()
    for i, c in enumerate(reversed(chunks)):
        out.append(c | (0x80 if i < len(chunks) - 1 else 0))
    return bytes(out)


def build_midi(
    fmt: int = 1,
    ppq: int = 384,
    tracks: list[list[tuple[int, bytes]]] | None = None,
) -> bytes:
    """Sagradi SMF iz (delta, event_bytes) parova. End-of-Track se dodaje."""
    if tracks is None:
        tracks = [
            [
                (0, bytes([0xC0, 0x00])),
                (0, bytes([0x90, 60, 100])),
                (ppq, bytes([0x80, 60, 0])),
            ]
        ]
    body = b""
    for events in tracks:
        chunk = b""
        for delta, payload in events:
            chunk += _vlq(delta) + payload
        chunk += _vlq(0) + b"\xff\x2f\x00"
        body += b"MTrk" + struct.pack(">I", len(chunk)) + chunk
    header = struct.pack(">HHH", fmt, len(tracks), ppq)
    return b"MThd" + struct.pack(">I", 6) + header + body


@pytest.fixture
def simple_midi_bytes() -> bytes:
    return build_midi()


@pytest.fixture
def simple_midi(tmp_path: Path, simple_midi_bytes: bytes) -> Path:
    path = tmp_path / "simple.mid"
    path.write_bytes(simple_midi_bytes)
    return path


@pytest.fixture
def multi_track_midi(tmp_path: Path) -> Path:
    """Format 1, tri tracka, isti kanal na dva -- oponasa Factory strukturu."""
    data = build_midi(
        fmt=1,
        ppq=192,
        tracks=[
            [(0, b"\xff\x51\x03\x07\xa1\x20"), (0, b"\xff\x58\x04\x04\x02\x18\x08")],
            [
                (0, bytes([0xB0, 0, 121])),
                (0, bytes([0xB0, 32, 3])),
                (0, bytes([0xC0, 25])),
                (0, bytes([0x90, 64, 90])),
                (192, bytes([0x80, 64, 0])),
            ],
            [
                (0, bytes([0xC0, 25])),
                (0, bytes([0x90, 67, 80])),
                (192, bytes([0x80, 67, 0])),
            ],
        ],
    )
    path = tmp_path / "multi.mid"
    path.write_bytes(data)
    return path


@pytest.fixture
def dangling_note_midi(tmp_path: Path) -> Path:
    """Note On bez Note Off -- reprodukuje nalaz iz FORENZIKA.md."""
    data = build_midi(
        fmt=1,
        ppq=192,
        tracks=[
            [
                (0, bytes([0x90, 60, 100])),
                (0, bytes([0x90, 62, 100])),
                (192, bytes([0x80, 60, 0])),
            ]
        ],
    )
    path = tmp_path / "dangling.mid"
    path.write_bytes(data)
    return path


@pytest.fixture
def running_status_midi(tmp_path: Path) -> Path:
    """Kanalne poruke koje koriste running status."""
    chunk = b""
    chunk += _vlq(0) + bytes([0x90, 60, 100])
    chunk += _vlq(96) + bytes([62, 100])  # running status
    chunk += _vlq(96) + bytes([60, 0])
    chunk += _vlq(96) + bytes([62, 0])
    chunk += _vlq(0) + b"\xff\x2f\x00"
    body = b"MTrk" + struct.pack(">I", len(chunk)) + chunk
    data = b"MThd" + struct.pack(">I", 6) + struct.pack(">HHH", 0, 1, 192) + body
    path = tmp_path / "running.mid"
    path.write_bytes(data)
    return path


@pytest.fixture
def corpus_root() -> Path:
    """Vanjski DNA korpus; test se preskace ako nije dostupan."""
    value = os.environ.get(CORPUS_ENV)
    if not value:
        pytest.skip(f"{CORPUS_ENV} nije postavljen")
    path = Path(value)
    if not path.is_dir():
        pytest.skip(f"{CORPUS_ENV} ne pokazuje na direktorij")
    return path
