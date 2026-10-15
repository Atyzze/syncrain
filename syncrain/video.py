"""syncrain --video FILE: the rain as a video file that plays on anything, made with ffmpeg.

A video is the rain recorded, not the rain: it repeats where the live rain never does, and it is
the same on every machine where the live rain follows the clock. What it saves is the drawing: a
player decodes it, on most machines in the video hardware, where the live rain runs the graphics
card every frame.

Frames are drawn one by one at the video's own size (not the window's) and handed to ffmpeg as
they are drawn, so nothing is kept on disk. A looping video (the default) ends where it begins:
its first seconds are drawn twice over, once as themselves and once as the moment just after the
end, the one fading into the other, so the last frame flows into the first. The web page's Video
section makes the same video, frame for frame (index.html, makeVideo)."""

import contextlib
import math
import os
import shutil
import subprocess
import sys

#: the formats a name may end in, and what ffmpeg makes of each
FORMATS = (".mp4", ".mkv", ".webm", ".gif")
#: the size, seconds and frame rate when not given: a GIF is large for what it shows, so less
DEFAULTS = {"gif": ((640, 360), 10.0, 15.0), "video": ((1920, 1080), 30.0, 30.0)}
#: a GIF's frames all wait in ffmpeg's memory until its palette is made: at most this many pixels
#: in all (640x360 for 30 s at 15 fps, about 300 MiB), and at most 50 fps (browsers show a frame
#: that asks for under 20 ms for 100 ms)
GIF_PIXELS, GIF_FPS = 640 * 360 * 450, 50.0
#: seconds the end fades into the start over, at most (half the video, if that is shorter)
LOOP_FADE = 2.0


def kind(path: str) -> str:
    """'.mp4' etc., or ValueError saying which it takes."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in FORMATS:
        raise ValueError(f"a video ends in {', '.join(FORMATS)}: {path!r}")
    return ext


def js_round(x: float) -> int:
    """Math.round: a half goes up (Python's round() takes it to the even neighbour)."""
    return int(math.floor(x + 0.5))


def settle(args) -> None:
    """The video's size (args.video_size), seconds and frame rate, the format's defaults for what
    is not given; ValueError for a video it cannot make. Even sizes: H.264 and VP9 in the usual
    colour format take nothing else."""
    ext = kind(args.video)
    (dw, dh), seconds, fps = DEFAULTS["gif" if ext == ".gif" else "video"]
    try:
        w, h = (int(v) for v in args.size.lower().split("x")) if args.size else (dw, dh)
    except ValueError:
        raise ValueError(f"a size is WIDTHxHEIGHT, e.g. 1920x1080: {args.size!r}") from None
    if w < 16 or h < 16 or w > 8192 or h > 8192 or w % 2 or h % 2:
        raise ValueError(f"a video is 16 to 8192 pixels each way, in even numbers: {w}x{h}")
    args.video_size = (w, h)
    args.seconds = seconds if args.seconds is None else args.seconds
    args.video_fps = fps if args.video_fps is None else args.video_fps
    if ext == ".gif":
        if args.video_fps > GIF_FPS:
            raise ValueError(f"a GIF plays at most {GIF_FPS:g} fps evenly: {args.video_fps:g}")
        if w * h * js_round(args.seconds * args.video_fps) > GIF_PIXELS:
            raise ValueError(f"a GIF of {w}x{h} for {args.seconds:g} s at {args.video_fps:g} fps needs more memory "
                             f"than is wise (its frames wait for its palette): make it smaller, shorter or "
                             f"slower, or make an .mp4")


def plan(seconds: float, fps: float, loop: bool, t0: float):
    """The frames, in order: [(t, None)] for a frame drawn as it is, [(t, (t_end, a))] for one that
    is the moment t over the moment t_end with opacity a (the page's makeVideo, the same sums).
    t0 is rounded down to a whole second, as the page rounds it."""
    t0 = float(math.floor(t0))
    n = max(1, js_round(seconds * fps))
    fade = min(LOOP_FADE, seconds / 2) if loop else 0.0
    nf = js_round(fade * fps)
    out = []
    for k in range(n):
        t = t0 + k / fps
        # the moment just after the last frame is the one n frames on, so frame n-1 flows into frame 0
        out.append((t, (t0 + (n + k) / fps, k / nf)) if k < nf else (t, None))
    return out


def ffmpeg_command(path: str, w: int, h: int, fps: float) -> list[str]:
    """ffmpeg reading bottom-up RGBA frames (as glReadPixels gives them) on its input, writing path."""
    exe = shutil.which("ffmpeg")
    if not exe:
        raise FileNotFoundError("syncrain --video needs ffmpeg (pacman -S ffmpeg, apt install ffmpeg, "
                                "dnf install ffmpeg, zypper install ffmpeg, nix shell nixpkgs#ffmpeg), or the web page's "
                                "Video section")
    # a file, said so: a name with a colon ("rain-12:00.mp4") is otherwise a protocol, one with a
    # leading "-" an option
    path = "file:" + os.path.abspath(path)
    head = [exe, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-framerate", f"{fps:g}", "-i", "-"]
    ext = kind(path[len("file:"):])
    if ext == ".gif":
        # one palette for the whole video, made from its frames, then dithered to it; loops forever
        return head + ["-vf", "vflip,format=rgb24,split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=sierra2_4a",
                       "-loop", "0", path]
    # BT.709 and said so: players take an untagged HD video as BT.709, and ffmpeg's untagged default
    # (BT.601) shows a full green about 14% darker there
    colour = ["-vf", "vflip,scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
              "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
    if ext == ".webm":
        return head + colour + ["-c:v", "libvpx-vp9", "-crf", "24", "-b:v", "0", "-row-mt", "1", path]
    return head + colour + ["-c:v", "libx264", "-crf", "16", "-preset", "slow"] + (
        ["-movflags", "+faststart"] if ext == ".mp4" else []) + [path]


def blend(over: bytes, under: bytes, a: float) -> bytes:
    """over with opacity a on under, as a canvas draws it (8 bits, rounded: Image.blend truncates)."""
    from PIL import Image
    w = len(over) // 4                            # any shape will do: the sum is per byte
    mask = Image.new("L", (w, 1), round(a * 255))
    img = Image.composite(Image.frombytes("RGBA", (w, 1), over), Image.frombytes("RGBA", (w, 1), under), mask)
    return img.tobytes()


class Writer:
    """A video being made, a frame at a time: draw(t) gives the moment t as bottom-up RGBA bytes,
    w x h. step() writes the next frame and says whether the video is whole; abort() ends it with
    nothing left behind. OSError or RuntimeError on failure, with ffmpeg's words."""

    def __init__(self, path: str, w: int, h: int, fps: float, frames, draw):
        self.path, self.frames, self.draw, self.done = path, frames, draw, 0
        # made beside its name and put there when whole, so a failure leaves no half video and an
        # earlier one where it was (the extension stays last: ffmpeg goes by it)
        stem, ext = os.path.splitext(path)
        self.part = f"{stem}.part{ext}"
        cmd = ffmpeg_command(self.part, w, h, fps)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        # its own process group: Ctrl+C reaches syncrain, which stops it, not ffmpeg finishing early
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)

    def step(self) -> bool:
        if self.done < len(self.frames):
            t, end = self.frames[self.done]
            try:
                data = self.draw(t)
                if end is not None:
                    t_end, a = end
                    data = blend(data, self.draw(t_end), a)
                self.proc.stdin.write(data)
            except BrokenPipeError:              # ffmpeg stopped: what it said comes with the failure
                self._fail()
            except BaseException:
                self.abort()
                raise
            self.done += 1
            if self.done < len(self.frames):
                return False
        with contextlib.suppress(OSError):
            self.proc.stdin.close()
        if self.proc.wait() != 0:
            self._fail()
        self.proc.stderr.close()
        os.replace(self.part, self.path)
        return True

    def _fail(self):
        with contextlib.suppress(OSError):
            self.proc.stdin.close()
        err = self.proc.stderr.read().decode(errors="replace").strip()
        self.proc.wait()
        self._forget()
        raise RuntimeError(f"ffmpeg could not make {self.path}: {err or 'it stopped'}")

    def abort(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        self._forget()

    def _forget(self):
        for pipe in (self.proc.stdin, self.proc.stderr):
            with contextlib.suppress(OSError):
                pipe.close()
        with contextlib.suppress(OSError):
            os.unlink(self.part)


def write(path: str, w: int, h: int, fps: float, frames, draw) -> int:
    """The whole video at once (Writer, step after step). Returns the number of frames."""
    writer = Writer(path, w, h, fps, frames, draw)
    while not writer.step():
        pass
    return writer.done


def progress_line(i: int, n: int) -> None:
    print(f"\rsyncrain: frame {i} of {n}", end="", file=sys.stderr, flush=True)
