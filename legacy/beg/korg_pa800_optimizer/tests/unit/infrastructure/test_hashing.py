from __future__ import annotations

from korg_optimizer.infrastructure import hashing


def test_sha256_file_matches_sha256_bytes(tmp_path):
    content = b"korg pa800 test content"
    path = tmp_path / "sample.bin"
    path.write_bytes(content)

    assert hashing.sha256_file(path) == hashing.sha256_bytes(content)


def test_sha256_file_is_stable_across_chunk_sizes(tmp_path):
    content = bytes(range(256)) * 5000  # > 1 MB default chunk size
    path = tmp_path / "large.bin"
    path.write_bytes(content)

    assert hashing.sha256_file(path, chunk_size=16) == hashing.sha256_file(path, chunk_size=1024 * 1024)


def test_sha256_file_never_modifies_the_file(tmp_path):
    content = b"do not touch me"
    path = tmp_path / "sample.bin"
    path.write_bytes(content)
    before_mtime = path.stat().st_mtime_ns

    hashing.sha256_file(path)

    assert path.read_bytes() == content
    assert path.stat().st_mtime_ns == before_mtime
