"""syncrain --video: what it is asked, the frames it plans, and what it hands ffmpeg."""
import shutil

import pytest

from syncrain import video
from syncrain.app import parse_args
from tests.conftest import need


def test_a_looping_video_ends_where_it_begins():
    """Its first two seconds are the moments just after its end fading into themselves: frame 0 is
    all end (the moment after the last frame), and from the fade's end each frame is its moment."""
    frames = video.plan(4, 10, True, 1000.7)
    assert len(frames) == 40
    assert frames[0] == (1000.0, (1004.0, 0.0))                 # rounded down to the second, as the page does
    t, (t_end, a) = frames[10]
    assert (t, t_end, a) == (1001.0, 1005.0, 0.5)
    assert frames[19][1][1] == pytest.approx(0.95) and frames[20] == (1002.0, None)
    assert frames[-1] == (1000.0 + 39 / 10, None)


def test_a_video_that_does_not_loop_is_its_moments_only():
    assert all(end is None for _, end in video.plan(3, 30, False, 5))


def test_a_short_loop_fades_over_half_of_itself():
    frames = video.plan(1, 10, True, 0)
    assert [end is not None for _, end in frames] == [True] * 5 + [False] * 5


def test_a_frame_in_the_fade_is_drawn_as_a_canvas_draws_it():
    over, under = bytes([200, 0, 100, 255]), bytes([0, 200, 100, 255])
    assert video.blend(over, under, 0.25) == bytes([50, 150, 100, 255])
    assert video.blend(over, under, 0.0) == under and video.blend(over, under, 1.0) == over


@pytest.mark.parametrize("name, size, seconds, fps", [("a.mp4", (1920, 1080), 30, 30), ("a.webm", (1920, 1080), 30, 30),
                                                      ("A.GIF", (640, 360), 10, 15), ("a.mkv", (1920, 1080), 30, 30)])
def test_the_defaults_go_with_the_format(name, size, seconds, fps):
    """A GIF is large for what it shows: smaller, shorter and slower unless asked."""
    args = parse_args(["--config", "none", "--video", name])
    assert (args.video_size, args.seconds, args.video_fps, args.loop) == (size, seconds, fps, "on")
    args = parse_args(["--config", "none", "--video", name, "--size", "480x270", "--seconds", "4", "--video-fps", "24"])
    assert (args.video_size, args.seconds, args.video_fps) == ((480, 270), 4, 24)


def test_the_seam_is_one_frame_whatever_the_length():
    """The moment after the last frame is n frames on, also where seconds x fps is no whole number
    (1.1 s at 7 fps is 8 frames, 8/7 s, not 1.1); halves round up as the page's Math.round does."""
    frames = video.plan(1.1, 7, True, 0)
    assert len(frames) == 8 and frames[0][1][0] == pytest.approx(8 / 7)
    assert sum(end is not None for _, end in video.plan(1, 25, True, 0)) == 13      # 12.5 frames of fade


@pytest.mark.parametrize("argv", [
    ["--video", "a.avi"], ["--video", "a"], ["--video", "a.mp4", "--size", "641x360"],
    ["--video", "a.mp4", "--size", "8x8"], ["--video", "a.mp4", "--seconds", "0"],
    ["--video", "a.mp4", "--video-fps", "500"], ["--video", "a.mp4", "--loop", "maybe"],
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
    assert cmd[-1] == name and cmd[cmd.index("-i") + 1] == "-" and "640x360" in cmd and "rgba" in cmd
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
    """With a stand-in for the drawing: every frame reaches ffmpeg, and the fade's draws the end too."""
    need(shutil.which("ffmpeg") is not None, "no ffmpeg")
    import subprocess
    drawn = []

    def draw(t):
        drawn.append(t)
        return bytes([int(t * 40) % 256, 0, 0, 255]) * (32 * 18)
    path = tmp_path / "out" / "a.mp4"
    frames = video.plan(1, 10, True, 0)
    assert video.write(str(path), 32, 18, 10, frames, draw) == 10
    assert len(drawn) == 15                                          # 10 frames, 5 of them with the end
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
        video.write(str(path), 31, 17, 10, video.plan(1, 10, False, 0), lambda t: bytes(31 * 17 * 4))
    assert path.read_bytes() == b"the earlier one" and sorted(p.name for p in tmp_path.iterdir()) == ["a.mp4"]


def test_a_video_stopped_halfway_leaves_nothing(tmp_path):
    need(shutil.which("ffmpeg") is not None, "no ffmpeg")
    path = tmp_path / "a.mp4"
    writer = video.Writer(str(path), 32, 18, 10, video.plan(2, 10, False, 0), lambda t: bytes(32 * 18 * 4))
    for _ in range(5):
        assert not writer.step()
    writer.abort()
    assert list(tmp_path.iterdir()) == []
