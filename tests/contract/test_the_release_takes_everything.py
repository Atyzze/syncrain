"""The release allowlist and the tree agree: nothing is left out silently, nothing ignored ships."""
from __future__ import annotations

import fnmatch
import importlib.util


def packager(root):
    spec = importlib.util.spec_from_file_location("package_release", root / "tools/package_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_top_level_entry_is_shipped_or_is_host_state(root):
    pr = packager(root)
    host_state = pr.EXCLUDED_PARTS          # var/ (the release journal), caches, build products
    unaccounted = sorted(p.name for p in root.iterdir()
                         if p.name not in pr.ROOT_FILES | pr.ROOT_DIRS | host_state
                         and not p.name.startswith("result") and not p.name.endswith(".egg-info"))
    assert not unaccounted, f"neither shipped nor excluded on purpose: {unaccounted}"


def test_every_required_path_is_in_the_tree(root):
    packager(root).validate_required_release_paths()


def test_nothing_the_repository_ignores_is_shipped(root):
    patterns = [line.strip().rstrip("/") for line in (root / ".gitignore").read_text().splitlines()
                if line.strip() and not line.startswith("#")]
    shipped = packager(root).shipped()
    offenders = sorted(rel for rel in shipped for part in rel.split("/")
                       if any(fnmatch.fnmatch(part, pattern) for pattern in patterns))
    assert not offenders, f"ignored by git but in the release: {offenders[:10]}"


def test_the_delivery_is_named_for_its_build(root):
    pr = packager(root)
    assert pr.archive_name(7) == "SYNCRAIN7.tar.zst"
    assert pr.archive_root(7) == "syncrain_build_7"
    assert pr.release_output_path(root / "tools", 7) == (root / "tools" / "SYNCRAIN7.tar.zst").resolve()
