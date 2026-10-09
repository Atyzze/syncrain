#!/usr/bin/env python3
"""Make the next numbered syncrain release, or nothing.

    setsid nohup python3 tools/package_release.py --output <dir> > ../release.log 2>&1 < /dev/null &

In order: undo a previous run that was killed (from `var/release_journal.json`); write
`current + 1` into BUILD_NUMBER; rebuild the generated web pages for it; run every test lane with
every environment required (`tools/test_suite.py --lane all --require-all`) and write its summary
into the build's notes in place of the token GATE_RESULT; compile the Python; build a wheel,
install it somewhere clean and ask it which build and stream it is; then write
`<dir>/SYNCRAIN<N>.tar.zst`: one directory `syncrain_build_<N>/` holding the release allowlist,
verified byte for byte against the tree before it is given its name. Only then is the number
earned, and the log's last line is `build <N>: <path>`.

A run that raises puts the tree back at the previous build and spends no number. A run that is
killed cannot, so the next run reads the journal and does it. Never fix either by editing
BUILD_NUMBER by hand, and never hand anyone a tar made another way.
"""
from __future__ import annotations

import argparse
import compileall
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: What a release carries: these files at the root, and these directories whole.
ROOT_FILES = {".gitignore", "BUILD_NUMBER", "LICENSE", "README.md", "flake.nix", "flake.lock", "install.sh",
              "pyproject.toml"}
#: Root files whose absence is a fact about the tree, not a broken promise.
OPTIONAL_ROOT_FILES = {"flake.lock"}
ROOT_DIRS = {"docs", "extras", "nix", "syncrain", "tests", "tools", "web"}
#: Never in a release: host state, caches and build products.
EXCLUDED_PARTS = {".git", ".pytest_cache", "__pycache__", "build", "dist", "var", ".venv", "venv",
                  "syncrain-wallpaper"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
#: What a fresh machine needs; the release refuses to ship without any of them.
REQUIRED_RELEASE_PATHS = {
    "BUILD_NUMBER", "README.md", "LICENSE", "install.sh", "flake.nix", "pyproject.toml",
    "syncrain/__main__.py", "syncrain/app.py", "syncrain/build.py", "syncrain/diagnose.py", "syncrain/engine.py",
    "syncrain/renderer.py", "syncrain/gl.py", "syncrain/native.py", "syncrain/native/build.sh",
    "syncrain/native/wallpaper.c", "syncrain/native/render.c", "syncrain/native/syncrain.h",
    "syncrain/data/themes.json", "syncrain/data/atlas.png",
    "web/index.html", "web/artifact.html", "web/template.html",
    "nix/package.nix", "nix/nixos-module.nix", "nix/hm-module.nix",
    "tests/fixtures/stream_freeze.json", "tools/package_release.py", "tools/test_suite.py",
    "tools/stream_freeze.py", "tools/build_web.py",
    "docs/WHERE_WE_ARE.md", "docs/ROADMAP.md", "docs/agent/HANDOFF.md", "docs/agent/NEXT_BUILD.md",
    "docs/agent/ENVIRONMENT.md",
}
NOTES_DIR = "docs/build_notes"
GATE_RESULT_TOKEN = "GATE_RESULT"
JOURNAL = ROOT / "var" / "release_journal.json"
JOURNAL_CONTRACT = "syncrain-release-journal-1"
#: The files a release changes before it knows whether it will succeed.
TRACKED = ("BUILD_NUMBER", "web/index.html", "web/artifact.html")


def archive_name(number: int) -> str:
    return f"SYNCRAIN{number}.tar.zst"


def archive_root(number: int) -> str:
    return f"syncrain_build_{number}"


def current_build() -> int:
    return int((ROOT / "BUILD_NUMBER").read_text(encoding="utf-8").strip())


def notes_path(number: int) -> Path:
    return ROOT / NOTES_DIR / f"BUILD{number}_NOTES.md"


# ---------------------------------------------------------------- the allowlist

def release_paths() -> list[Path]:
    paths = [ROOT / name for name in ROOT_FILES if (ROOT / name).is_file()]
    for directory in sorted(ROOT_DIRS):
        base = ROOT / directory
        if base.is_dir():
            paths.extend(p for p in base.rglob("*") if p.is_file() or p.is_symlink())
    return sorted(set(paths), key=lambda p: p.relative_to(ROOT).as_posix())


def include_in_release(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in rel.parts):
        return False
    return path.suffix not in EXCLUDED_SUFFIXES


def shipped() -> dict[str, Path]:
    return {p.relative_to(ROOT).as_posix(): p for p in release_paths() if include_in_release(p)}


def validate_required_release_paths(present: set[str] | None = None) -> None:
    present = set(shipped()) if present is None else present
    missing = sorted(REQUIRED_RELEASE_PATHS - present)
    if not any(name.startswith(NOTES_DIR + "/") for name in present):
        missing.append(NOTES_DIR + "/ (no build notes)")
    if missing:
        raise RuntimeError(f"the release would be missing: {missing}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------- the gate and the notes

def run_gate(command: list[str]) -> str:
    """Run the full lane, echoing it, and return pytest's summary line."""
    summary = ""
    proc = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if re.search(r"\b\d+ (passed|failed)\b", line):
                summary = line.strip()
        proc.wait()
    except BaseException:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
        raise
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, command)
    return re.sub(r"^=+\s*|\s*=+$", "", summary) or "lane passed; pytest printed no summary line"


def stamp_gate_result(number: int, summary: str) -> None:
    """Put the gate's own summary where the notes carry the token (a mention in backticks is prose)."""
    path = notes_path(number)
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    stamped = re.sub(rf"(?<!`){GATE_RESULT_TOKEN}(?!`)", lambda _m: summary, text)
    if stamped != text:
        path.write_text(stamped, encoding="utf-8")
        print(f"notes: {path.relative_to(ROOT)}: {summary}")


def refuse_unstamped_notes(number: int) -> None:
    path = notes_path(number)
    if not path.is_file():
        raise RuntimeError(f"no {path.relative_to(ROOT)}: a build is released with its notes or not at all")
    if re.search(rf"(?<!`){GATE_RESULT_TOKEN}(?!`)", path.read_text(encoding="utf-8")):
        raise RuntimeError(f"{path.relative_to(ROOT)} still carries {GATE_RESULT_TOKEN}: an unverified claim")


def rebuild_web_pages() -> None:
    subprocess.run([sys.executable, "tools/build_web.py"], cwd=ROOT, check=True,
                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))


# ---------------------------------------------------------------- the wheel

def remove_generated_files() -> None:
    """Delete setuptools products a wheel build could capture; never var/, a venv or the repository."""
    for path in sorted(ROOT.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        rel = path.relative_to(ROOT)
        if any(part in {".git", "var", ".venv", "venv"} for part in rel.parts):
            continue
        if path.is_dir() and (path.name in {"build", "dist", "__pycache__"} or path.name.endswith(".egg-info")):
            shutil.rmtree(path, ignore_errors=True)


def validate_wheel(number: int) -> None:
    """Build the wheel, install it clean, and ask it which build and stream it is."""
    from syncrain import build
    remove_generated_files()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    with tempfile.TemporaryDirectory(prefix="syncrain-release-wheel-") as raw:
        wheel_dir, install_dir = Path(raw) / "wheel", Path(raw) / "install"
        subprocess.run([sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation",
                        "--wheel-dir", str(wheel_dir), "-q"], cwd=ROOT, env=env, check=True)
        remove_generated_files()
        wheels = list(wheel_dir.glob("*.whl"))
        if len(wheels) != 1 or wheels[0].name != f"syncrain-{number}-py3-none-any.whl":
            raise RuntimeError(f"expected syncrain-{number}-py3-none-any.whl, found {[w.name for w in wheels]}")
        with zipfile.ZipFile(wheels[0]) as wheel:
            names = set(wheel.namelist())
        needed = {f"syncrain/{rel}" for rel in build.STREAM_FILES} | {"syncrain/diagnose.py", "syncrain/app.py"}
        if needed - names:
            raise RuntimeError(f"the wheel lacks {sorted(needed - names)}")
        if [n for n in names if n.endswith((".pyc", ".pyo")) or "__pycache__/" in n]:
            raise RuntimeError("the wheel carries compiled caches")
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(install_dir), "-q",
                        str(wheels[0])], cwd=raw, env=env, check=True)
        probe = subprocess.run(
            [sys.executable, "-c", "import json; from syncrain import build; "
             "print(json.dumps({'build': build.BUILD_NUMBER, 'stream': build.stream_fingerprint()}))"],
            cwd=raw, env=dict(env, PYTHONPATH=str(install_dir)), check=True, capture_output=True, text=True)
        said = json.loads(probe.stdout.strip().splitlines()[-1])
        if said != {"build": number, "stream": build.stream_fingerprint()}:
            raise RuntimeError(f"the installed wheel says {said}; the tree is build {number}, "
                               f"stream {build.stream_id()}")


# ---------------------------------------------------------------- the archive

def release_output_path(requested: Path | None, number: int) -> Path:
    """No --output: beside the tree. A directory, or a path with no suffix: the name inside it."""
    name = archive_name(number)
    if requested is None:
        return (ROOT.parent / name).resolve()
    requested = Path(requested)
    if requested.is_dir() or not requested.suffix:
        return (requested / name).resolve()
    return requested.resolve()


def partial_path(output: Path) -> Path:
    """Hidden and suffixed, so nothing looking for the delivery name ever finds an unverified archive."""
    return output.with_name(f".{output.name}.partial")


def _normalised(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def write_archive(number: int, output: Path) -> Path:
    validate_required_release_paths()
    zstd = shutil.which("zstd")
    if not zstd:
        raise RuntimeError("zstd is needed to write SYNCRAIN<N>.tar.zst")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = partial_path(output)
    partial.unlink(missing_ok=True)
    prefix = archive_root(number)
    with tempfile.TemporaryDirectory(prefix="syncrain-release-archive-", dir=output.parent) as raw:
        tar_path = Path(raw) / f"{prefix}.tar"
        with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT, dereference=True) as tf:
            for rel, path in shipped().items():
                if path.resolve() in (output.resolve(), partial.resolve()):
                    continue
                tf.add(path, arcname=f"{prefix}/{rel}", recursive=False, filter=_normalised)
        compressed = Path(raw) / f"{prefix}.tar.zst"
        subprocess.run([zstd, "-19", "-T0", "-q", "-f", str(tar_path), "-o", str(compressed)], check=True)
        subprocess.run([zstd, "-t", "-q", str(compressed)], check=True)
        os.replace(compressed, partial)
    return partial


def verify_archive(number: int, archive: Path) -> None:
    """The archive is exactly the allowlist, byte for byte, under one root, and it is the build it is named for."""
    told = current_build()
    if told != number:
        raise RuntimeError(f"refusing: the archive is named for build {number} but the tree says {told}")
    prefix = archive_root(number)
    expected = {f"{prefix}/{rel}": _sha256(path) for rel, path in shipped().items()}
    zstd = shutil.which("zstd")
    with tempfile.TemporaryDirectory(prefix="syncrain-release-verify-") as raw:
        tar_path = Path(raw) / "release.tar"
        subprocess.run([zstd, "-d", "-q", "-f", str(archive), "-o", str(tar_path)], check=True)
        actual, modes = {}, {}
        with tarfile.open(tar_path, "r:") as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    raise RuntimeError(f"the archive holds a non-file member: {member.name}")
                if member.name.startswith("/") or ".." in Path(member.name).parts:
                    raise RuntimeError(f"unsafe member name: {member.name}")
                data = tf.extractfile(member).read()
                actual[member.name] = hashlib.sha256(data).hexdigest()
                modes[member.name] = member.mode
                if member.name == f"{prefix}/BUILD_NUMBER" and data.decode().strip() != str(number):
                    raise RuntimeError(f"the archive's BUILD_NUMBER says {data.decode().strip()}, not {number}")
    roots = {name.split("/", 1)[0] for name in actual}
    if roots != {prefix}:
        raise RuntimeError(f"the archive must have exactly one top-level directory, {prefix}; it has {sorted(roots)}")
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(n for n in set(expected) & set(actual) if expected[n] != actual[n])
    if missing or extra or changed:
        raise RuntimeError(f"the archive differs from the tree: missing={missing[:5]} extra={extra[:5]} "
                           f"changed={changed[:5]}")
    if not modes.get(f"{prefix}/install.sh", 0) & 0o100:
        raise RuntimeError("install.sh lost its executable bit in the archive")


def publish(partial: Path, output: Path) -> None:
    with partial.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(partial, output)
    directory = os.open(output.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


# ---------------------------------------------------------------- the journal

def _process_alive(pid: int) -> bool:
    """Signal 0 checks existence without delivering anything; someone else's process counts as alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def write_journal(number: int, originals: dict[str, str | None]) -> None:
    """Written before the first change and deleted only after the archive is published, so a
    journal found at startup always means a run that did not finish."""
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL.write_text(json.dumps({
        "contract": JOURNAL_CONTRACT, "number": number, "pid": os.getpid(),
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "originals": originals,
    }, indent=1) + "\n", encoding="utf-8")


def restore_from_journal() -> int | None:
    if not JOURNAL.is_file():
        return None
    try:
        record = json.loads(JOURNAL.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        print(f"warning: the release journal is unreadable ({exc}); ignoring it")
        return None
    if record.get("contract") != JOURNAL_CONTRACT:
        print("warning: the release journal has an unknown contract; ignoring it")
        return None
    owner = record.get("pid")
    if isinstance(owner, int) and _process_alive(owner):
        print(f"a release of build {record.get('number')} is running (pid {owner}); leaving its journal alone")
        return None
    restored = []
    for rel, content in (record.get("originals") or {}).items():
        path = ROOT / rel
        if content is None:
            if path.exists():
                path.unlink()
                restored.append(f"{rel} (removed)")
        elif not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
            restored.append(rel)
    JOURNAL.unlink(missing_ok=True)
    print(f"recovered an interrupted release of build {record.get('number')}: "
          + (", ".join(restored) if restored else "nothing to restore")
          + f"; the tree is back at build {current_build()}")
    return record.get("number")


# ---------------------------------------------------------------- the run

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", type=Path, help=f"a directory for {archive_name(0).replace('0', '<N>')}, or a file path")
    ap.add_argument("--number", type=int, help="release under this number instead of current + 1; must be higher, "
                                               "and the notes must say 'Follows build: <the current one>'")
    ap.add_argument("--skip-tests", action="store_true",
                    help="no gate: the notes say the archive is unverified (never for a delivery)")
    ap.add_argument("--skip-wheel", action="store_true", help="no wheel build and clean install")
    args = ap.parse_args(argv)

    restore_from_journal()
    if args.number is not None and args.number <= current_build():
        raise SystemExit(f"--number {args.number} is not above the current build {current_build()}; "
                         "a released number is spent")
    number = args.number if args.number is not None else current_build() + 1
    output = release_output_path(args.output, number)
    notes = notes_path(number)
    tracked = list(TRACKED) + [notes.relative_to(ROOT).as_posix()]
    originals = {rel: ((ROOT / rel).read_text(encoding="utf-8") if (ROOT / rel).exists() else None)
                 for rel in tracked}
    previous_handlers: dict = {}
    try:
        write_journal(number, originals)

        def interrupted(signum, _frame):
            raise KeyboardInterrupt(f"release interrupted by signal {signum}")
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            try:
                previous_handlers[sig] = signal.signal(sig, interrupted)
            except (ValueError, OSError):
                pass

        if not notes.is_file():
            raise RuntimeError(f"write {notes.relative_to(ROOT)} first (with {GATE_RESULT_TOKEN} under "
                               "## Verification): a build is released with its notes or not at all")
        (ROOT / "BUILD_NUMBER").write_text(f"{number}\n", encoding="utf-8")
        rebuild_web_pages()
        if args.skip_tests:
            stamp_gate_result(number, "tests skipped (--skip-tests); this archive is not verified")
        else:
            summary = run_gate([sys.executable, "tools/test_suite.py", "--lane", "all", "--require-all"])
            stamp_gate_result(number, summary)
        if not compileall.compile_dir(ROOT / "syncrain", quiet=1) or not compileall.compile_dir(ROOT / "tools", quiet=1):
            raise RuntimeError("the Python does not compile")
        if not args.skip_wheel:
            validate_wheel(number)
        remove_generated_files()
        refuse_unstamped_notes(number)
        partial = write_archive(number, output)
        try:
            verify_archive(number, partial)
            publish(partial, output)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
    except BaseException:
        for rel, content in originals.items():
            path = ROOT / rel
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(content, encoding="utf-8")
        JOURNAL.unlink(missing_ok=True)
        print(f"release failed; the tree is back at build {current_build()} and no number was spent")
        raise
    finally:
        for sig, handler in previous_handlers.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass
    JOURNAL.unlink(missing_ok=True)
    print(f"build {number}: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
