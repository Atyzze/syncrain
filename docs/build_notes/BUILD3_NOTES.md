# Build 3: build numbers, GSD's way of keeping a project, and build 2's grey screen fixed

**Type: practices and a fix; the picture does not change.** Made on 2026-10-07 from the operator's
messages of 00:56 and 00:58: "can you adopt the good architecture/code-base management practices
from this codebase, such as a clear build number (instead of these versionings .... stop, no
'versions', only build numbers)", with GSD592 attached; and, with a screenshot of build 2 on their
desktop, "the wallpaper went gray/static, and then the 'syncrain opengl unavailable message
appeared and that was it, ctlr + c luckily did reset it back to what it was". Build 3 draws build
2's frames pixel for pixel (two moments compared at 1280x720); its stream id, `48e6bf9c`, is the
first one, so it has nothing to match yet.

## 1. Build numbers instead of versions

`BUILD_NUMBER` at the root is the only identity a tree has (`syncrain/build.py`): pyproject reads it
as its packaging field (`dynamic = ["version"]`, from the file), the Nix package and web bundle read
it (`lib.fileContents ../BUILD_NUMBER`), `install.sh` reads it, copies it beside the installed app
and names upgrades ("Upgrading syncrain from build 2 to build 3"), and `syncrain --build` prints
`syncrain build 3 (stream 48e6bf9c)` (`--version` is a hidden spelling of the same). The archive
is `SYNCRAIN3.tar.zst` holding one directory, `syncrain_build_3/`. `__version__`, "0.1.0" and the
themes file's "version" key are gone (the file's format is its contract, `syncrain-themes-1`).
Held by `tests/contract/test_build_identity.py` and `tests/unit/test_the_build_identity.py`.

## 2. The stream id and its freeze

The stream fingerprint is a SHA-256 over the files that decide the picture (the shaders,
`themes.json`, the atlas, the logos, `syncrain/engine.py`); its first eight digits are the stream
id, shown by `--build`, in the startup line and in the page's footer. Same id, same channel, synced
clocks: the same frame. `tests/fixtures/stream_freeze.json` records it, and the gate fails when a
stream file moves until `tools/stream_freeze.py --write` re-takes it on purpose
(`tests/contract/test_the_stream_is_frozen.py`).

## 3. The release and its gate (adopted from GSD's `package_release.py`)

`tools/package_release.py` is the only way to make an archive: it recovers a killed run from its
journal, writes the new number, rebuilds the web pages, runs `tools/test_suite.py --lane all
--require-all`, writes the summary into these notes in place of the token, compiles, builds and
clean-installs a wheel and asks it its build and stream, then writes the archive under a hidden
name, verifies it byte for byte (one root, nothing extra, nothing missing, install.sh executable,
the BUILD_NUMBER inside equal to the name) and only then renames it. Six lanes: unit, contract (the
project's rules: identity, current documents, cadence, pointers, style, the freeze, generated pages,
the allowlist), render (the app on a private Xvfb), wayland (the wallpaper in a headless Sway, seen
with grim), browser (the page in Chromium, against the app), nix (the package built, both services
evaluated). `tests/unit/test_the_release_tool.py` holds the packager to its guarantees.

## 4. The documents

The README is a directory. `docs/` holds ARCHITECTURE, OPERATIONS (every option and recipe, one
home), LESSONS, HISTORY, ROADMAP (questions, decisions, planned builds, the cadence, the standing
constraints) and WHERE_WE_ARE (the operator's page); `docs/agent/` the handoff, the next build, the
sandbox, the target machines and how the work with the operator goes; these notes, one per build
(1 and 2 written now, from the record). Consolidation builds are every number ending in 0; the
next is 10.

## 5. The grey screen

**Cause.** GTK creates a GLArea's context to share with the display's own, which is OpenGL ES
unless `GDK_DEBUG=gl-prefer-gl` (GTK 4.22.5, `gdk/gdkglcontext.c`, read from the GNOME/gtk mirror).
Build 2 asked for version 3.3; as OpenGL ES that is above every version GTK tries (3.2, 3.1, 3.0),
so none was tried, and GTK fell back to desktop OpenGL shared with the ES context. Mesa allows that,
so every sandbox run drew; the EGL specification forbids it, and the operator's driver (NVIDIA,
most likely; not confirmed) refused: "Unable to create a GL context", once per screen, and two grey
windows. **Reproduced** with only OpenGL ES allowed, in the sandbox (GTK 4.14.5) and in a real Arch
root (GTK 4.22.5): build 2 printed the operator's exact message and stayed grey.

**Fix** (`syncrain/app.py`): no version is asked for; after realising, `gl_context_problem` checks
for OpenGL 3.3 or OpenGL ES 3.0 and the renderer compiles the shaders for whichever it got (ES and
desktop OpenGL draw the same frame, pixel for pixel on Mesa). Held by
`tests/render/test_the_app_draws.py` and `tests/wayland/test_the_wallpaper_layer.py`, which run the
app with only OpenGL ES, only desktop OpenGL, and none.

**Around it.** Without OpenGL the windows are hidden at once and the app exits with status 69,
which every service lists in `RestartPreventExitStatus`, so nothing loops; until the first frame a
window is black, not GTK's grey. Ctrl+C, SIGTERM and SIGHUP end it cleanly (build 2 printed a
KeyboardInterrupt traceback). The launcher sets `PYTHONSAFEPATH=1`: run from inside the unpacked
folder, build 2's started that folder's copy, not the installed one. Service lines now double
backslashes too (systemd unescapes inside single quotes), checked by parsing them as systemd does.

## 6. `syncrain --diagnose`

Whether syncrain can draw here and why not, verdict first: the session, the libraries, the graphics
cards and driver from sysfs, the OpenGL context GTK hands out with its vendor and renderer, the
shaders compiled on it and one test frame drawn offscreen (`syncrain/diagnose.py`). One command to
send when something does not work.

## 7. What the operator does

* Unpack `SYNCRAIN3.tar.zst`, run `./install.sh` from `syncrain_build_3/` (it replaces build 2;
  no new packages), then `syncrain`. The terminal shows one line: the build, the stream, the OpenGL
  it got and "2 screens".
* If it does not draw: `syncrain --diagnose`, and send what it prints.
* The KDE question in `docs/ROADMAP.md`: keep the icons covered, or a Plasma wallpaper plugin.

## Verification

96 passed in 122.33s (0:02:02)

Before the gate, by hand: build 2 and build 3 in a real Arch root (GTK 4.22.5, Mesa 26.2.4) under
headless Sway with OpenGL ES only, desktop OpenGL only and none (build 2 grey with the operator's
message; build 3 drew, and exited 69 without OpenGL); `install.sh` run there over build 2's
install as the operator has it (it named the replacement; the installed launcher then drew as a
Wayland wallpaper with OpenGL ES only, and `--diagnose` said OK); build 2 and build 3 frames
compared at two moments (identical). Not checked: the operator's GPU, KDE Plasma itself, two real
screens.
