from __future__ import annotations

from korg_optimizer.factory.discovery import discover_files


def test_discovers_mid_files_case_insensitively(tmp_path):
    (tmp_path / "a.mid").write_bytes(b"x")
    (tmp_path / "b.MID").write_bytes(b"x")
    (tmp_path / "c.txt").write_bytes(b"x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "d.mid").write_bytes(b"x")

    found = {p.name for p in discover_files(tmp_path)}
    assert found == {"a.mid", "b.MID", "d.mid"}


def test_discover_files_on_missing_root_yields_nothing(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert list(discover_files(missing)) == []


def test_discover_files_stable_order(tmp_path):
    for name in ["z.mid", "a.mid", "m.mid"]:
        (tmp_path / name).write_bytes(b"x")
    names = [p.name for p in discover_files(tmp_path)]
    assert names == sorted(names)
