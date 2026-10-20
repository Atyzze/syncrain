"""syncrain --video: what it is asked, the frames it plans, and what it hands ffmpeg."""
import os
import shutil

import pytest

from syncrain import video
from syncrain.app import parse_args
from tests.conftest import need


def test_every_frame_is_its_own_moment():
    """No frame is faded or blended into another: a crossfade made the first seconds of a video
    blurred, the logo with them. The moments start at a whole second, as the page rounds them."""
    frames = video.plan(4, 10, 1000.7)
    assert len(frames) == 40
    assert frames[0] == 1000.0 and frames[10] == 1001.0 and frames[-1] == 1000.0 + 39 / 10
    assert all(isinstance(t, float) for t in frames)


def test_the_number_of_frames_rounds_as_the_page_does():
    """1.1 s at 7 fps is 8 frames (7.7, rounded); halves round up as the page's Math.round does."""
    assert len(video.plan(1.1, 7, 0)) == 8
    assert len(video.plan(0.1, 25, 0)) == 3                         # 2.5 frames
    assert len(video.plan(0.001, 30, 0)) == 1                       # never none


def test_there_is_no_loop_option_any_more():
    """The seamless-loop crossfade is gone, and with it --loop: asked for, it is refused, not ignored."""
    with pytest.raises(SystemExit):
        parse_args(["--config", "none", "--video", "a.mp4", "--loop", "on"])
    assert not hasattr(video, "blend") and not hasattr(video, "LOOP_FADE")


@pytest.mark.parametrize("name, size, seconds, fps", [("a.mp4", (1920, 1080), 30, 30), ("a.webm", (1920, 1080), 30, 30),
                                                      ("A.GIF", (640, 360), 10, 15), ("a.mkv", (1920, 1080), 30, 30)])
def test_the_defaults_go_with_the_format(name, size, seconds, fps):
    """A GIF is large for what it shows: smaller, shorter and slower unless asked."""
    args = parse_args(["--config", "none", "--video", name])
    assert (args.video_size, args.seconds, args.video_fps) == (size, seconds, fps)
    args = parse_args(["--config", "none", "--video", name, "--size", "480x270", "--seconds", "4", "--video-fps", "24"])
    assert (args.video_size, args.seconds, args.video_fps) == ((480, 270), 4, 24)


@pytest.mark.parametrize("argv", [
    ["--video", "a.avi"], ["--video", "a"], ["--video", "a.mp4", "--size", "641x360"],
    ["--video", "a.mp4", "--size", "8x8"], ["--video", "a.mp4", "--seconds", "0"],
    ["--video", "a.mp4", "--video-fps", "500"], ["--video", "a.mp4", "--loop", "off"],
    ["--video", "a.mp4", "--screenshot", "a.png"], ["--video", "a.mp4", "--record", "d"],
    ["--video", "a.avi", "--size", "640x360"], ["--video", "a.mp4", "--size", "big"],
    ["--video", "a.gif", "--video-fps", "60"], ["--video", "a.gif", "--size", "1920x1080"],
])
def test_a_video_it_cannot_make_is_refused_at_once(argv, capsys):
    with pytest.raises(SystemExit) as e:
        parse_args(["--config", "none", *argv])
    assert e.value.code == 2 and "error" in capsys.readouterr().err


def test_a_number_too_high_says_so():
    """An option with only a top (--record-fps) said 'invalid parse value' before build 29."""
    with pytest.raises(SystemExit):
        parse_args(["--config", "none", "--record-fps", "2000"])


@pytest.mark.parametrize("name, says", [("a.mp4", ["libx264", "+faststart"]),
                                        ("a.mkv", ["libx264"]),
                                        ("a.webm", ["libvpx-vp9"]),
                                        ("a.gif", ["-loop", "0"])])
def test_ffmpeg_reads_the_frames_as_they_are_drawn(name, says, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda exe: "/usr/bin/" + exe)
    cmd = video.ffmpeg_command(name, 640, 360, 30)
    assert cmd[-1] == "file:" + os.path.abspath(name), "a file, whatever its name holds"
    assert cmd[cmd.index("-i") + 1] == "-" and "640x360" in cmd and "rgba" in cmd
    assert all(word in cmd for word in says)
    assert any(arg.startswith("vflip") for arg in cmd)              # OpenGL's rows run bottom to top
    if name.endswith(".gif"):
        assert "palettegen" in cmd[cmd.index("-vf") + 1]
    else:                                                            # BT.709, and said so: players assume it for HD
        assert "out_color_matrix=bt709" in cmd[cmd.index("-vf") + 1] and "format=yuv420p" in cmd[cmd.index("-vf") + 1]
        assert cmd[cmd.index("-colorspace") + 1] == "bt709"


def test_without_ffmpeg_it_says_what_to_install(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda exe: None)
    with pytest.raises(FileNotFoundError, match="needs ffmpeg"):
        video.ffmpeg_command("a.mp4", 640, 360, 30)


def test_a_video_is_made_from_the_frames_drawn(tmp_path):
    """With a stand-in for the drawing: every frame reaches ffmpeg, each drawn once, at its moment."""
    need(shutil.which("ffmpeg") is not None, "no ffmpeg")
    import subprocess
    drawn = []

    def draw(t):
        drawn.append(t)
        return bytes([int(t * 40) % 256, 0, 0, 255]) * (32 * 18)
    path = tmp_path / "out" / "a.mp4"
    frames = video.plan(1, 10, 0)
    assert video.write(str(path), 32, 18, 10, frames, draw) == 10
    assert drawn == frames                                           # nothing drawn twice, nothing blended in
    assert sorted(p.name for p in path.parent.iterdir()) == ["a.mp4"]   # made as a.part.mp4, then named
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries", "stream=nb_read_frames",
                            "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    assert probe.stdout.strip() == "10"


def test_what_ffmpeg_refuses_is_said_and_leaves_what_was_there(tmp_path):
    """An odd size H.264 takes not: the failure in ffmpeg's words, the earlier video kept, no half one."""
    need(shutil.which("ffmpeg") is not None, "no ffmpeg")
    path = tmp_path / "a.mp4"
    path.write_bytes(b"the earlier one")
    with pytest.raises(RuntimeError, match="ffmpeg could not make"):
        video.write(str(path), 31, 17, 10, video.plan(1, 10, 0), lambda t: bytes(31 * 17 * 4))
    assert path.read_bytes() == b"the earlier one" and sorted(p.name for p in tmp_path.iterdir()) == ["a.mp4"]


def test_a_video_stopped_halfway_leaves_nothing(tmp_path):
    need(shutil.which("ffmpeg") is not None, "no ffmpeg")
    path = tmp_path / "a.mp4"
    writer = video.Writer(str(path), 32, 18, 10, video.plan(2, 10, 0), lambda t: bytes(32 * 18 * 4))
    for _ in range(5):
        assert not writer.step()
    writer.abort()
    assert list(tmp_path.iterdir()) == []
