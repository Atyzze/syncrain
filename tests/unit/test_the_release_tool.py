"""The packager's guarantees, on a small tree of its own: a verified archive, or none."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tarfile

import pytest

from tests.conftest import need


@pytest.fixture
def pr(root, tmp_path, monkeypatch):
    """The packager pointed at a throwaway tree with a handful of files."""
    spec = importlib.util.spec_from_file_location("package_release_under_test", root / "tools/package_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tree = tmp_path / "tree"
    (tree / "docs/build_notes").mkdir(parents=True)
    (tree / "syncrain").mkdir()
    (tree / "BUILD_NUMBER").write_text("5\n")
    (tree / "README.md").write_text("readme\n")
    (tree / "install.sh").write_text("#!/bin/sh\n")
    (tree / "install.sh").chmod(0o755)
    (tree / "syncrain/app.py").write_text("print('app')\n")
    (tree / "docs/build_notes/BUILD5_NOTES.md").write_text("# Build 5: x\n\n## Verification\n\nGATE_RESULT\n")
    (tree / "syncrain/__pycache__").mkdir()
    (tree / "syncrain/__pycache__/app.cpython-313.pyc").write_bytes(b"cache")
    monkeypatch.setattr(module, "ROOT", tree)
    monkeypatch.setattr(module, "JOURNAL", tree / "var/release_journal.json")
    monkeypatch.setattr(module, "REQUIRED_RELEASE_PATHS", {"BUILD_NUMBER", "README.md", "install.sh"})
    monkeypatch.setattr(module, "ROOT_DIRS", {"docs", "syncrain"})
    return module


def members(archive, tmp_path):
    tar = tmp_path / "check.tar"
    subprocess.run(["zstd", "-d", "-q", "-f", str(archive), "-o", str(tar)], check=True)
    with tarfile.open(tar) as tf:
        return {m.name: m for m in tf.getmembers()}


def test_an_archive_is_one_directory_named_for_its_build(pr, tmp_path):
    need(shutil.which("zstd") is not None, "no zstd")
    partial = pr.write_archive(5, tmp_path / "out" / "SYNCRAIN5.tar.zst")
    pr.verify_archive(5, partial)
    found = members(partial, tmp_path)
    assert {name.split("/", 1)[0] for name in found} == {"syncrain_build_5"}
    assert "syncrain_build_5/syncrain/__pycache__/app.cpython-313.pyc" not in found
    assert found["syncrain_build_5/install.sh"].mode & 0o100
    assert partial.name == ".SYNCRAIN5.tar.zst.partial", "unverified archives never carry the delivery name"


def test_an_archive_that_differs_from_the_tree_is_refused(pr, tmp_path):
    need(shutil.which("zstd") is not None, "no zstd")
    partial = pr.write_archive(5, tmp_path / "out" / "SYNCRAIN5.tar.zst")
    (pr.ROOT / "README.md").write_text("changed after packing\n")
    with pytest.raises(RuntimeError, match="differs from the tree"):
        pr.verify_archive(5, partial)


def test_an_archive_named_for_another_build_is_refused(pr, tmp_path):
    need(shutil.which("zstd") is not None, "no zstd")
    partial = pr.write_archive(6, tmp_path / "out" / "SYNCRAIN6.tar.zst")
    with pytest.raises(RuntimeError, match="named for build 6 but the tree says 5"):
        pr.verify_archive(6, partial)


def test_the_gate_s_summary_replaces_the_token_and_only_the_bare_one(pr):
    notes = pr.ROOT / "docs/build_notes/BUILD5_NOTES.md"
    notes.write_text("# Build 5: x\n\nThe token `GATE_RESULT` is prose here.\n\n## Verification\n\nGATE_RESULT\n")
    pr.stamp_gate_result(5, "12 passed in 3.00s")
    text = notes.read_text()
    assert text.endswith("12 passed in 3.00s\n") and "`GATE_RESULT`" in text
    pr.refuse_unstamped_notes(5)


def test_unstamped_notes_stop_the_release(pr):
    with pytest.raises(RuntimeError, match="unverified claim"):
        pr.refuse_unstamped_notes(5)


def test_a_killed_release_is_undone_by_the_next_run(pr):
    """A SIGKILL runs no handler; the journal it left puts the tree back before anything reads it."""
    dead = subprocess.Popen(["true"])
    dead.wait()
    (pr.ROOT / "BUILD_NUMBER").write_text("6\n")                    # the killed run's bump
    pr.JOURNAL.parent.mkdir(parents=True)
    pr.JOURNAL.write_text(json.dumps({"contract": pr.JOURNAL_CONTRACT, "number": 6, "pid": dead.pid,
                                      "originals": {"BUILD_NUMBER": "5\n"}}))
    assert pr.restore_from_journal() == 6
    assert pr.current_build() == 5 and not pr.JOURNAL.exists()


def test_a_running_release_s_journal_is_left_alone(pr):
    pr.JOURNAL.parent.mkdir(parents=True)
    pr.JOURNAL.write_text(json.dumps({"contract": pr.JOURNAL_CONTRACT, "number": 6, "pid": os.getpid(),
                                      "originals": {"BUILD_NUMBER": "4\n"}}))
    assert pr.restore_from_journal() is None
    assert pr.current_build() == 5 and pr.JOURNAL.exists()
