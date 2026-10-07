"""The app takes whichever OpenGL GTK hands out and checks only that the shaders can run on it.

Build 2 asked GTK for "version 3.3", which exists only for desktop OpenGL. GTK 4.14 and later
create every context to share with the display's own, which is OpenGL ES unless told otherwise,
so on a driver that will not share across the two APIs no context could be made and the
wallpaper stayed grey. The render lane runs the real thing with only OpenGL ES allowed; this
pins the rule the check applies.
"""
from __future__ import annotations

import pytest

from syncrain.app import EXIT_NO_GL, MIN_GL, gl_context_problem


class FakeGdk:
    class GLAPI:
        GL = 1
        GLES = 2


class FakeContext:
    def __init__(self, es, version):
        self.api, self.version = (FakeGdk.GLAPI.GLES if es else FakeGdk.GLAPI.GL), version

    def get_api(self):
        return self.api

    def get_version(self):
        return self.version


@pytest.mark.parametrize("es, version", [(True, (3, 0)), (True, (3, 2)), (False, (3, 3)), (False, (4, 6))])
def test_what_the_shaders_compile_on_is_accepted(es, version):
    assert gl_context_problem(FakeContext(es, version), FakeGdk) == (es, None)


@pytest.mark.parametrize("es, version, words", [(True, (2, 0), "OpenGL ES 2.0 is too old"),
                                                 (False, (3, 2), "OpenGL 3.2 is too old")])
def test_an_older_context_is_refused_with_the_reason(es, version, words):
    used_es, problem = gl_context_problem(FakeContext(es, version), FakeGdk)
    assert used_es == es and words in problem


def test_the_minimums_are_the_shading_languages_the_shaders_are_written_in():
    assert MIN_GL == {False: (3, 3), True: (3, 0)}    # GLSL 3.30 core; GLSL ES 3.00, what WebGL2 runs


def test_no_opengl_has_its_own_exit_status():
    assert EXIT_NO_GL == 69                            # listed in RestartPreventExitStatus by every service
