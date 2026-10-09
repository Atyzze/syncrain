/* EGL and OpenGL: the six passes, the same calls in the same order as renderer.py.
 *
 * One OpenGL context draws every screen: each screen's EGL window surface is made current in turn,
 * so the programs and textures exist once, and the frame's intermediate textures once per screen
 * size. The composite pass draws straight into the screen's back buffer; the GTK host draws it into
 * a GLArea's texture, which GTK then draws again into the window.
 *
 * libEGL is opened at run time and the OpenGL functions come from eglGetProcAddress, so building
 * needs neither EGL nor OpenGL headers, and a machine without EGL hands over to the GTK host
 * instead of failing to start. The API follows GTK's switches (GDK_DISABLE and GDK_DEBUG), so one
 * set of switches chooses OpenGL or OpenGL ES in either host: OpenGL ES unless told otherwise.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <wayland-client.h>
#include <wayland-egl.h>

#include "syncrain.h"

#ifndef SYNCRAIN_LIBEGL
#define SYNCRAIN_LIBEGL "libEGL.so.1"
#endif

/* ------------------------------------------------------------------ EGL, as much as is used */

typedef void *EGLDisplay, *EGLConfig, *EGLContext, *EGLSurface;
typedef int32_t EGLint;
typedef unsigned int EGLBoolean, EGLenum;

#define EGL_NO_DISPLAY ((EGLDisplay)0)
#define EGL_NO_CONTEXT ((EGLContext)0)
#define EGL_NO_SURFACE ((EGLSurface)0)
#define EGL_SUCCESS 0x3000
#define EGL_ALPHA_SIZE 0x3021
#define EGL_BLUE_SIZE 0x3022
#define EGL_GREEN_SIZE 0x3023
#define EGL_RED_SIZE 0x3024
#define EGL_DEPTH_SIZE 0x3025
#define EGL_STENCIL_SIZE 0x3026
#define EGL_SURFACE_TYPE 0x3033
#define EGL_NONE 0x3038
#define EGL_RENDERABLE_TYPE 0x3040
#define EGL_VENDOR 0x3053
#define EGL_VERSION 0x3054
#define EGL_EXTENSIONS 0x3055
#define EGL_WINDOW_BIT 0x0004
#define EGL_OPENGL_BIT 0x0008
#define EGL_OPENGL_ES3_BIT 0x0040
#define EGL_OPENGL_ES_API 0x30A0
#define EGL_OPENGL_API 0x30A2
#define EGL_CONTEXT_MAJOR_VERSION 0x3098
#define EGL_CONTEXT_MINOR_VERSION 0x30FB
#define EGL_CONTEXT_OPENGL_PROFILE_MASK 0x30FD
#define EGL_CONTEXT_OPENGL_CORE_PROFILE_BIT 0x0001
#define EGL_PLATFORM_WAYLAND_EXT 0x31D8

#define EGL_FUNCTIONS(X) \
	X(void *, eglGetProcAddress, (const char *)) \
	X(const char *, eglQueryString, (EGLDisplay, EGLint)) \
	X(EGLDisplay, eglGetDisplay, (void *)) \
	X(EGLBoolean, eglInitialize, (EGLDisplay, EGLint *, EGLint *)) \
	X(EGLBoolean, eglTerminate, (EGLDisplay)) \
	X(EGLBoolean, eglBindAPI, (EGLenum)) \
	X(EGLBoolean, eglChooseConfig, (EGLDisplay, const EGLint *, EGLConfig *, EGLint, EGLint *)) \
	X(EGLBoolean, eglGetConfigAttrib, (EGLDisplay, EGLConfig, EGLint, EGLint *)) \
	X(EGLContext, eglCreateContext, (EGLDisplay, EGLConfig, EGLContext, const EGLint *)) \
	X(EGLBoolean, eglDestroyContext, (EGLDisplay, EGLContext)) \
	X(EGLSurface, eglCreateWindowSurface, (EGLDisplay, EGLConfig, void *, const EGLint *)) \
	X(EGLBoolean, eglDestroySurface, (EGLDisplay, EGLSurface)) \
	X(EGLBoolean, eglMakeCurrent, (EGLDisplay, EGLSurface, EGLSurface, EGLContext)) \
	X(EGLBoolean, eglSwapBuffers, (EGLDisplay, EGLSurface)) \
	X(EGLBoolean, eglSwapInterval, (EGLDisplay, EGLint)) \
	X(EGLBoolean, eglReleaseThread, (void)) \
	X(EGLint, eglGetError, (void))

#define DECLARE(ret, name, args) static ret(*name) args;
EGL_FUNCTIONS(DECLARE)
static EGLDisplay (*eglGetPlatformDisplayEXT)(EGLenum, void *, const EGLint *);
static EGLSurface (*eglCreatePlatformWindowSurfaceEXT)(EGLDisplay, EGLConfig, void *, const EGLint *);

/* ------------------------------------------------------------------ OpenGL, as much as is used */

typedef unsigned int GLenum, GLuint, GLbitfield;
typedef int GLint, GLsizei;
typedef float GLfloat;
typedef char GLchar;
typedef unsigned char GLboolean, GLubyte;

#define GL_NO_ERROR 0
#define GL_TRIANGLES 0x0004
#define GL_COLOR_BUFFER_BIT 0x00004000
#define GL_BLEND 0x0BE2
#define GL_DEPTH_TEST 0x0B71
#define GL_SCISSOR_TEST 0x0C11
#define GL_UNPACK_ALIGNMENT 0x0CF5
#define GL_TEXTURE_2D 0x0DE1
#define GL_UNSIGNED_BYTE 0x1401
#define GL_RGBA 0x1908
#define GL_RENDERER 0x1F01
#define GL_NEAREST 0x2600
#define GL_LINEAR 0x2601
#define GL_LINEAR_MIPMAP_LINEAR 0x2703
#define GL_TEXTURE_MAG_FILTER 0x2800
#define GL_TEXTURE_MIN_FILTER 0x2801
#define GL_TEXTURE_WRAP_S 0x2802
#define GL_TEXTURE_WRAP_T 0x2803
#define GL_CLAMP_TO_EDGE 0x812F
#define GL_RGBA8 0x8058
#define GL_MAJOR_VERSION 0x821B
#define GL_MINOR_VERSION 0x821C
#define GL_TEXTURE0 0x84C0
#define GL_FRAGMENT_SHADER 0x8B30
#define GL_VERTEX_SHADER 0x8B31
#define GL_COMPILE_STATUS 0x8B81
#define GL_LINK_STATUS 0x8B82
#define GL_INFO_LOG_LENGTH 0x8B84
#define GL_READ_FRAMEBUFFER 0x8CA8
#define GL_DRAW_FRAMEBUFFER 0x8CA9
#define GL_COLOR_ATTACHMENT0 0x8CE0
#define GL_FRAMEBUFFER 0x8D40

#define GL_FUNCTIONS(X) \
	X(void, glActiveTexture, (GLenum)) \
	X(void, glAttachShader, (GLuint, GLuint)) \
	X(void, glBindFramebuffer, (GLenum, GLuint)) \
	X(void, glBindTexture, (GLenum, GLuint)) \
	X(void, glBindVertexArray, (GLuint)) \
	X(void, glBlitFramebuffer, (GLint, GLint, GLint, GLint, GLint, GLint, GLint, GLint, GLbitfield, GLenum)) \
	X(void, glCompileShader, (GLuint)) \
	X(GLuint, glCreateProgram, (void)) \
	X(GLuint, glCreateShader, (GLenum)) \
	X(void, glDeleteFramebuffers, (GLsizei, const GLuint *)) \
	X(void, glDeleteProgram, (GLuint)) \
	X(void, glDeleteShader, (GLuint)) \
	X(void, glDeleteTextures, (GLsizei, const GLuint *)) \
	X(void, glDeleteVertexArrays, (GLsizei, const GLuint *)) \
	X(void, glDetachShader, (GLuint, GLuint)) \
	X(void, glDisable, (GLenum)) \
	X(void, glDrawArrays, (GLenum, GLint, GLsizei)) \
	X(void, glFinish, (void)) \
	X(void, glFramebufferTexture2D, (GLenum, GLenum, GLenum, GLuint, GLint)) \
	X(void, glGenFramebuffers, (GLsizei, GLuint *)) \
	X(void, glGenTextures, (GLsizei, GLuint *)) \
	X(void, glGenVertexArrays, (GLsizei, GLuint *)) \
	X(void, glGenerateMipmap, (GLenum)) \
	X(GLenum, glGetError, (void)) \
	X(void, glGetIntegerv, (GLenum, GLint *)) \
	X(void, glGetProgramInfoLog, (GLuint, GLsizei, GLsizei *, GLchar *)) \
	X(void, glGetProgramiv, (GLuint, GLenum, GLint *)) \
	X(void, glGetShaderInfoLog, (GLuint, GLsizei, GLsizei *, GLchar *)) \
	X(void, glGetShaderiv, (GLuint, GLenum, GLint *)) \
	X(const GLubyte *, glGetString, (GLenum)) \
	X(GLint, glGetUniformLocation, (GLuint, const GLchar *)) \
	X(void, glLinkProgram, (GLuint)) \
	X(void, glPixelStorei, (GLenum, GLint)) \
	X(void, glShaderSource, (GLuint, GLsizei, const GLchar *const *, const GLint *)) \
	X(void, glTexImage2D, (GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void *)) \
	X(void, glTexParameteri, (GLenum, GLenum, GLint)) \
	X(void, glUniform1f, (GLint, GLfloat)) \
	X(void, glUniform1i, (GLint, GLint)) \
	X(void, glUniform1ui, (GLint, GLuint)) \
	X(void, glUniform2f, (GLint, GLfloat, GLfloat)) \
	X(void, glUniform3f, (GLint, GLfloat, GLfloat, GLfloat)) \
	X(void, glUniform4f, (GLint, GLfloat, GLfloat, GLfloat, GLfloat)) \
	X(void, glUniform4fv, (GLint, GLsizei, const GLfloat *)) \
	X(void, glUseProgram, (GLuint)) \
	X(void, glViewport, (GLint, GLint, GLsizei, GLsizei))

GL_FUNCTIONS(DECLARE)

/* renderer.py, UNIT: the texture unit each sampler reads. */
enum { UNIT_STATE = 0, UNIT_FIELD = 1, UNIT_ATLAS = 2, UNIT_LUT = 3, UNIT_WORDS = 4, UNIT_BLOOM = 5,
       UNIT_LOGO = 6, UNIT_BG = 7, UNIT_MASK = 8, UNIT_SRC = 9 };
static const int STATIC_UNIT[TEXTURE_COUNT] = { UNIT_ATLAS, UNIT_LUT, UNIT_WORDS, UNIT_LOGO, UNIT_BG, UNIT_MASK };

/* The per-frame uniforms of each program, in the order renderer.py sets them. */
enum { STATE_SEC, STATE_FRAC, STATE_COLS, STATE_ROWS, STATE_KEEP, STATE_N };
static const char *const STATE_U[] = { "uSec", "uFrac", "uCols", "uRows", "uKeep" };
enum { FIELD_COLS, FIELD_ROWS, FIELD_N };
static const char *const FIELD_U[] = { "uCols", "uRows" };
enum { GLYPHS_SEC, GLYPHS_FRAC, GLYPHS_COLS, GLYPHS_ROWS, GLYPHS_CELL, GLYPHS_COL0, GLYPHS_RES, GLYPHS_TARGET,
       GLYPHS_N };
static const char *const GLYPHS_U[] = { "uSec", "uFrac", "uCols", "uRows", "uCell", "uColOffset", "uRes",
                                        "uTarget" };
enum { BLUR_SIGMA, BLUR_STEP, BLUR_N };
static const char *const BLUR_U[] = { "uSigma", "uStep" };
enum { COMP_SEC, COMP_FRAC, COMP_COLS, COMP_ROWS, COMP_CELL, COMP_COL0, COMP_RES, COMP_ORIGIN, COMP_BGSCALE,
       COMP_BGOFFSET, COMP_N };
static const char *const COMP_U[] = { "uSec", "uFrac", "uCols", "uRows", "uCell", "uColOffset", "uRes",
                                      "uOrigin", "uBgScale", "uBgOffset" };

/* One viewport size's intermediate textures (renderer.py, Targets), and every value that depends
 * only on the size. Two screens of one size share them: a frame overwrites them before reading. */
enum { T_STATE, T_FIELD, T_GLYPHS, T_BLUR_A, T_BLUR_B, T_COUNT };

struct targets {
	bool used;
	struct geometry g;
	GLuint tex[T_COUNT], fbo[T_COUNT];
};

#define MAX_TARGETS 9            /* renderer.py clears its cache when it holds more than 8 */
#define MAX_OFFSCREEN 4

struct offscreen {
	bool used;
	int width, height;
	GLuint fbo, tex;
};

struct render_surface {
	struct wl_egl_window *window;
	EGLSurface surface;
	int width, height;
	bool interval_set;
};

static struct {
	void *egl_library;
	EGLDisplay display;
	EGLConfig config;
	EGLContext context;
	const struct scene *scene;
	struct gl_info info;
	bool debug;
	long fail_from, fail_count, swaps;      /* SYNCRAIN_TEST_SWAP_FAILURES, for tests/wayland only */
	GLuint program[PROGRAM_COUNT];
	GLint state_u[STATE_N], field_u[FIELD_N], glyphs_u[GLYPHS_N], blur_u[BLUR_N], comp_u[COMP_N];
	GLuint texture[TEXTURE_COUNT];
	GLuint vao;
	struct targets targets[MAX_TARGETS];
	struct offscreen offscreen[MAX_OFFSCREEN];
	struct render_surface *current;
} R;

static void check(const char *what)
{
	if (!R.debug)
		return;
	for (GLenum e; (e = glGetError()) != GL_NO_ERROR; )
		fprintf(stderr, "syncrain: OpenGL error 0x%04x after %s\n", e, what);
}

/* ------------------------------------------------------------------ the API, as GTK would choose it */

static bool has_word(const char *list, const char *word)
{
	if (!list)
		return false;
	size_t n = strlen(word);
	for (const char *p = list; *p; ) {
		while (*p && strchr(":;, \t", *p))
			p++;
		const char *e = p;
		while (*e && !strchr(":;, \t", *e))
			e++;
		if ((size_t)(e - p) == n && strncmp(p, word, n) == 0)
			return true;
		p = e;
	}
	return false;
}

/* GTK 4.14 and 4.15 read these as GDK_DEBUG flags, 4.16 and later as GDK_DISABLE features. */
static void allowed_apis(bool *gles, bool *gl, bool *gl_first)
{
	const char *disable = getenv("GDK_DISABLE"), *debug = getenv("GDK_DEBUG");
	bool none = has_word(disable, "gl") || has_word(disable, "all") || has_word(debug, "gl-disable");
	*gles = !none && !has_word(disable, "gles-api") && !has_word(debug, "gl-disable-gles");
	*gl = !none && !has_word(disable, "gl-api") && !has_word(debug, "gl-disable-gl");
	*gl_first = has_word(debug, "gl-prefer-gl");
}

static bool load_egl(char *why, size_t why_size)
{
	R.egl_library = dlopen(SYNCRAIN_LIBEGL, RTLD_NOW | RTLD_LOCAL);
	if (!R.egl_library) {
		snprintf(why, why_size, "no EGL (%s)", dlerror());
		return false;
	}
#define LOAD_EGL(ret, name, args) \
	if (!(*(void **)&name = dlsym(R.egl_library, #name))) { \
		snprintf(why, why_size, "EGL lacks %s", #name); \
		return false; \
	}
	EGL_FUNCTIONS(LOAD_EGL)
	return true;
}

static void *gl_address(const char *name)
{
	return eglGetProcAddress(name);
}

static bool load_gl(char *why, size_t why_size)
{
#define LOAD_GL(ret, name, args) \
	if (!(*(void **)&name = gl_address(#name))) { \
		snprintf(why, why_size, "OpenGL lacks %s", #name); \
		return false; \
	}
	GL_FUNCTIONS(LOAD_GL)
	return true;
}

/* A configuration for window surfaces: 8 bits a colour and none for alpha where the driver has one
 * (the compositor then knows every pixel is opaque), no depth, no stencil. */
static EGLConfig choose_config(EGLint renderable)
{
	const EGLint want[] = { EGL_SURFACE_TYPE, EGL_WINDOW_BIT, EGL_RENDERABLE_TYPE, renderable,
	                        EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_NONE };
	EGLConfig configs[256];
	EGLint n = 0;
	if (!eglChooseConfig(R.display, want, configs, 256, &n) || n <= 0)
		return NULL;
	EGLConfig best = NULL;
	int best_score = -1;
	for (EGLint i = 0; i < n; i++) {
		EGLint r, g, b, a, d, s;
		eglGetConfigAttrib(R.display, configs[i], EGL_RED_SIZE, &r);
		eglGetConfigAttrib(R.display, configs[i], EGL_GREEN_SIZE, &g);
		eglGetConfigAttrib(R.display, configs[i], EGL_BLUE_SIZE, &b);
		eglGetConfigAttrib(R.display, configs[i], EGL_ALPHA_SIZE, &a);
		eglGetConfigAttrib(R.display, configs[i], EGL_DEPTH_SIZE, &d);
		eglGetConfigAttrib(R.display, configs[i], EGL_STENCIL_SIZE, &s);
		if (r != 8 || g != 8 || b != 8 || (a != 0 && a != 8))
			continue;
		int score = (a == 0) * 4 + (d == 0) * 2 + (s == 0);
		if (score > best_score) {
			best = configs[i];
			best_score = score;
		}
	}
	return best;
}

static bool try_api(bool es, char *why, size_t why_size)
{
	if (!eglBindAPI(es ? EGL_OPENGL_ES_API : EGL_OPENGL_API)) {
		snprintf(why, why_size, "EGL offers no %s", es ? "OpenGL ES" : "OpenGL");
		return false;
	}
	EGLConfig config = choose_config(es ? EGL_OPENGL_ES3_BIT : EGL_OPENGL_BIT);
	if (!config) {
		snprintf(why, why_size, "EGL has no 8-bit window configuration for %s", es ? "OpenGL ES 3" : "OpenGL");
		return false;
	}
	const EGLint gles[] = { EGL_CONTEXT_MAJOR_VERSION, 3, EGL_NONE };
	const EGLint core[] = { EGL_CONTEXT_MAJOR_VERSION, 3, EGL_CONTEXT_MINOR_VERSION, 3,
	                        EGL_CONTEXT_OPENGL_PROFILE_MASK, EGL_CONTEXT_OPENGL_CORE_PROFILE_BIT, EGL_NONE };
	EGLContext context = eglCreateContext(R.display, config, EGL_NO_CONTEXT, es ? gles : core);
	if (context == EGL_NO_CONTEXT) {
		snprintf(why, why_size, "%s 3.%d could not be created (EGL error 0x%x)", es ? "OpenGL ES" : "OpenGL",
		         es ? 0 : 3, (unsigned)eglGetError());
		return false;
	}
	if (!eglMakeCurrent(R.display, EGL_NO_SURFACE, EGL_NO_SURFACE, context)) {
		snprintf(why, why_size, "a context without a surface cannot be made current (EGL error 0x%x)",
		         (unsigned)eglGetError());
		eglDestroyContext(R.display, context);
		return false;
	}
	if (!load_gl(why, why_size)) {
		eglMakeCurrent(R.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
		eglDestroyContext(R.display, context);
		return false;
	}
	GLint major = 0, minor = 0;
	glGetIntegerv(GL_MAJOR_VERSION, &major);
	glGetIntegerv(GL_MINOR_VERSION, &minor);
	/* app.py, MIN_GL: GLSL ES 3.00 or GLSL 3.30, what the shaders are written in */
	if (es ? major < 3 : (major < 3 || (major == 3 && minor < 3))) {
		snprintf(why, why_size, "%s %d.%d is too old; syncrain needs %s", es ? "OpenGL ES" : "OpenGL", major, minor,
		         es ? "OpenGL ES 3.0" : "OpenGL 3.3");
		eglMakeCurrent(R.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
		eglDestroyContext(R.display, context);
		return false;
	}
	R.config = config;
	R.context = context;
	R.info.es = es;
	R.info.major = major;
	R.info.minor = minor;
	const char *renderer = (const char *)glGetString(GL_RENDERER);
	snprintf(R.info.renderer, sizeof R.info.renderer, "%s", renderer ? renderer : "unknown renderer");
	return true;
}

/* ------------------------------------------------------------------ programs and textures */

static const char *const HEADER_ES = "#version 300 es\nprecision highp float;\nprecision highp int;\n"
                                     "precision highp sampler2D;\n";
static const char *const HEADER_GL = "#version 330 core\n";

static GLuint compile(GLenum kind, struct blob body, const char *name, char *why, size_t why_size)
{
	const char *header = R.info.es ? HEADER_ES : HEADER_GL;
	const GLchar *parts[2] = { header, body.data };
	const GLint lengths[2] = { (GLint)strlen(header), (GLint)body.size };
	GLuint shader = glCreateShader(kind);
	glShaderSource(shader, 2, parts, lengths);
	glCompileShader(shader);
	GLint ok = 0;
	glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
	if (!ok) {
		char log[1024] = "";
		glGetShaderInfoLog(shader, sizeof log, NULL, log);
		snprintf(why, why_size, "the shaders did not compile here: %s: %s", name, log);
		glDeleteShader(shader);
		return 0;
	}
	return shader;
}

static bool build_program(enum program p, char *why, size_t why_size)
{
	const char *name = scene_program_name(p);
	GLuint vert = compile(GL_VERTEX_SHADER, R.scene->vertex, name, why, why_size);
	if (!vert)
		return false;
	GLuint frag = compile(GL_FRAGMENT_SHADER, R.scene->fragment[p], name, why, why_size);
	if (!frag) {
		glDeleteShader(vert);
		return false;
	}
	GLuint program = glCreateProgram();
	glAttachShader(program, vert);
	glAttachShader(program, frag);
	glLinkProgram(program);
	GLint ok = 0;
	glGetProgramiv(program, GL_LINK_STATUS, &ok);
	glDetachShader(program, vert);
	glDetachShader(program, frag);
	glDeleteShader(vert);
	glDeleteShader(frag);
	if (!ok) {
		char log[1024] = "";
		glGetProgramInfoLog(program, sizeof log, NULL, log);
		snprintf(why, why_size, "the shaders did not compile here: %s: %s", name, log);
		glDeleteProgram(program);
		return false;
	}
	R.program[p] = program;
	return true;
}

/* renderer.py, _tex */
static GLuint make_texture(int w, int h, const void *pixels, enum filter filter)
{
	GLuint t = 0;
	glGenTextures(1, &t);
	glBindTexture(GL_TEXTURE_2D, t);
	glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
	if (filter == FILTER_MIP)
		glGenerateMipmap(GL_TEXTURE_2D);
	GLint minify = filter == FILTER_MIP ? GL_LINEAR_MIPMAP_LINEAR : filter == FILTER_LINEAR ? GL_LINEAR : GL_NEAREST;
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, minify);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, filter == FILTER_NEAREST ? GL_NEAREST : GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	return t;
}

/* The uniforms a frame never changes, as the scene lists them (renderer.py, static_uniforms). */
static void set_static_uniforms(void)
{
	for (int i = 0; i < R.scene->uniforms; i++) {
		const struct uniform_source *u = &R.scene->uniform[i];
		glUseProgram(R.program[u->program]);
		GLint loc = glGetUniformLocation(R.program[u->program], u->name);
		const double *v = u->value;
		if (strcmp(u->kind, "i") == 0) {
			glUniform1i(loc, (GLint)u->integer[0]);
		} else if (strcmp(u->kind, "ui") == 0) {
			glUniform1ui(loc, (GLuint)(u->integer[0] & 0xFFFFFFFFll));
		} else if (strcmp(u->kind, "f") == 0) {
			glUniform1f(loc, (GLfloat)v[0]);
		} else if (strcmp(u->kind, "f2") == 0) {
			glUniform2f(loc, (GLfloat)v[0], (GLfloat)v[1]);
		} else if (strcmp(u->kind, "f3") == 0) {
			glUniform3f(loc, (GLfloat)v[0], (GLfloat)v[1], (GLfloat)v[2]);
		} else if (strcmp(u->kind, "f4") == 0) {
			glUniform4f(loc, (GLfloat)v[0], (GLfloat)v[1], (GLfloat)v[2], (GLfloat)v[3]);
		} else if (strcmp(u->kind, "f4v") == 0) {
			GLfloat flat[UNIFORM_VALUES];
			for (int k = 0; k < u->count; k++)
				flat[k] = (GLfloat)v[k];
			glUniform4fv(loc, u->count / 4, flat);
		}
	}
}

static void locate(enum program p, const char *const *names, int n, GLint *out)
{
	for (int i = 0; i < n; i++)
		out[i] = glGetUniformLocation(R.program[p], names[i]);
}

bool render_init(struct wl_display *display, const struct scene *scene, char *why, size_t why_size)
{
	R.scene = scene;
	R.debug = getenv("SYNCRAIN_GL_DEBUG") && *getenv("SYNCRAIN_GL_DEBUG");
	/* "FIRST:COUNT": swaps FIRST to FIRST + COUNT - 1 fail as a driver's can, without committing,
	 * so the lanes can show what the wallpaper does then. */
	const char *fail = getenv("SYNCRAIN_TEST_SWAP_FAILURES");
	if (fail && sscanf(fail, "%ld:%ld", &R.fail_from, &R.fail_count) != 2)
		R.fail_from = R.fail_count = 0;
	if (!load_egl(why, why_size))
		return false;
	const char *client = eglQueryString(EGL_NO_DISPLAY, EGL_EXTENSIONS);
	if (client && (has_word(client, "EGL_EXT_platform_wayland") || has_word(client, "EGL_KHR_platform_wayland"))) {
		*(void **)&eglGetPlatformDisplayEXT = eglGetProcAddress("eglGetPlatformDisplayEXT");
		*(void **)&eglCreatePlatformWindowSurfaceEXT = eglGetProcAddress("eglCreatePlatformWindowSurfaceEXT");
	}
	R.display = eglGetPlatformDisplayEXT && eglCreatePlatformWindowSurfaceEXT
	            ? eglGetPlatformDisplayEXT(EGL_PLATFORM_WAYLAND_EXT, display, NULL)
	            : eglGetDisplay(display);
	EGLint major = 0, minor = 0;
	if (R.display == EGL_NO_DISPLAY || !eglInitialize(R.display, &major, &minor)) {
		snprintf(why, why_size, "OpenGL is not available: EGL found no display (EGL error 0x%x)",
		         (unsigned)eglGetError());
		return false;
	}
	const char *vendor = eglQueryString(R.display, EGL_VENDOR);
	snprintf(R.info.egl, sizeof R.info.egl, "EGL %d.%d %s", major, minor, vendor ? vendor : "");
	const char *extensions = eglQueryString(R.display, EGL_EXTENSIONS);
	if (!has_word(extensions, "EGL_KHR_surfaceless_context")) {
		snprintf(why, why_size, "OpenGL is not available here without a window (no EGL_KHR_surfaceless_context)");
		return false;
	}
	bool gles, gl, gl_first;
	allowed_apis(&gles, &gl, &gl_first);
	char reason[512] = "OpenGL is disabled (GDK_DISABLE or GDK_DEBUG)";
	bool order[2] = { !gl_first, gl_first };       /* true: OpenGL ES */
	bool made = false;
	for (int i = 0; i < 2 && !made; i++) {
		bool es = order[i];
		if (es ? gles : gl)
			made = try_api(es, reason, sizeof reason);
	}
	if (!made) {
		snprintf(why, why_size, "OpenGL is not available: %s", reason);
		return false;
	}
	for (int p = 0; p < PROGRAM_COUNT; p++)
		if (!build_program((enum program)p, why, why_size))
			return false;
	for (int t = 0; t < TEXTURE_COUNT; t++) {
		const struct texture_source *src = &scene->texture[t];
		R.texture[t] = make_texture(src->width, src->height, src->pixels.data, src->filter);
	}
	set_static_uniforms();
	locate(PROGRAM_STATE, STATE_U, STATE_N, R.state_u);
	locate(PROGRAM_FIELD, FIELD_U, FIELD_N, R.field_u);
	locate(PROGRAM_GLYPHS, GLYPHS_U, GLYPHS_N, R.glyphs_u);
	locate(PROGRAM_BLUR, BLUR_U, BLUR_N, R.blur_u);
	locate(PROGRAM_COMPOSITE, COMP_U, COMP_N, R.comp_u);
	glGenVertexArrays(1, &R.vao);
	glFinish();                                    /* the pixels can go once the card has them */
	check("setting up");
	return true;
}

void render_info(struct gl_info *info)
{
	*info = R.info;
}

/* ------------------------------------------------------------------ surfaces */

struct render_surface *render_surface_create(struct wl_surface *surface, int width, int height,
                                             char *why, size_t why_size)
{
	struct render_surface *rs = calloc(1, sizeof *rs);
	if (!rs) {
		snprintf(why, why_size, "out of memory");
		return NULL;
	}
	rs->window = wl_egl_window_create(surface, width, height);
	if (!rs->window) {
		snprintf(why, why_size, "no EGL window for a screen");
		free(rs);
		return NULL;
	}
	rs->surface = eglCreatePlatformWindowSurfaceEXT
	              ? eglCreatePlatformWindowSurfaceEXT(R.display, R.config, rs->window, NULL)
	              : eglCreateWindowSurface(R.display, R.config, rs->window, NULL);
	if (rs->surface == EGL_NO_SURFACE) {
		snprintf(why, why_size, "no EGL surface for a screen (EGL error 0x%x)", (unsigned)eglGetError());
		wl_egl_window_destroy(rs->window);
		free(rs);
		return NULL;
	}
	rs->width = width;
	rs->height = height;
	return rs;
}

void render_surface_resize(struct render_surface *rs, int width, int height)
{
	if (rs->width == width && rs->height == height)
		return;
	wl_egl_window_resize(rs->window, width, height, 0, 0);
	rs->width = width;
	rs->height = height;
}

void render_surface_destroy(struct render_surface *rs)
{
	if (!rs)
		return;
	if (R.current == rs) {
		eglMakeCurrent(R.display, EGL_NO_SURFACE, EGL_NO_SURFACE, R.context);
		R.current = NULL;
	}
	eglDestroySurface(R.display, rs->surface);
	wl_egl_window_destroy(rs->window);
	free(rs);
}

/* ------------------------------------------------------------------ a frame */

static void delete_targets(struct targets *t)
{
	glDeleteFramebuffers(T_COUNT, t->fbo);
	glDeleteTextures(T_COUNT, t->tex);
	t->used = false;
}

static struct targets *targets_for(int w, int h)
{
	int used = 0;
	for (int i = 0; i < MAX_TARGETS; i++) {
		if (R.targets[i].used && R.targets[i].g.width == w && R.targets[i].g.height == h)
			return &R.targets[i];
		used += R.targets[i].used;
	}
	if (used == MAX_TARGETS)
		for (int i = 0; i < MAX_TARGETS; i++)
			delete_targets(&R.targets[i]);
	struct targets *t = NULL;
	for (int i = 0; i < MAX_TARGETS && !t; i++)
		if (!R.targets[i].used)
			t = &R.targets[i];
	geometry_compute(&t->g, R.scene, w, h);
	const struct geometry *g = &t->g;
	const int size[T_COUNT][2] = { { g->cols, g->rows }, { g->cols, g->rows }, { g->qw, g->qh }, { g->qw, g->qh },
	                               { g->qw, g->qh } };
	const enum filter filter[T_COUNT] = { FILTER_NEAREST, FILTER_LINEAR, FILTER_LINEAR, FILTER_LINEAR,
	                                      FILTER_LINEAR };
	glGenFramebuffers(T_COUNT, t->fbo);
	for (int i = 0; i < T_COUNT; i++) {
		t->tex[i] = make_texture(size[i][0], size[i][1], NULL, filter[i]);
		glBindFramebuffer(GL_FRAMEBUFFER, t->fbo[i]);
		glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, t->tex[i], 0);
	}
	t->used = true;
	return t;
}

static GLuint offscreen_for(int w, int h)
{
	for (int i = 0; i < MAX_OFFSCREEN; i++)
		if (R.offscreen[i].used && R.offscreen[i].width == w && R.offscreen[i].height == h)
			return R.offscreen[i].fbo;
	struct offscreen *o = &R.offscreen[0];
	for (int i = 0; i < MAX_OFFSCREEN; i++)
		if (!R.offscreen[i].used) {
			o = &R.offscreen[i];
			break;
		}
	if (o->used) {
		glDeleteFramebuffers(1, &o->fbo);
		glDeleteTextures(1, &o->tex);
	}
	glGenFramebuffers(1, &o->fbo);
	glGenTextures(1, &o->tex);
	glBindTexture(GL_TEXTURE_2D, o->tex);
	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
	glBindFramebuffer(GL_FRAMEBUFFER, o->fbo);
	glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, o->tex, 0);
	o->used = true;
	o->width = w;
	o->height = h;
	return o->fbo;
}

static void bind(int unit, GLuint texture)
{
	glActiveTexture(GL_TEXTURE0 + (GLenum)unit);
	glBindTexture(GL_TEXTURE_2D, texture);
}

static void run_pass(GLuint fbo, int w, int h, int x, int y)
{
	glBindFramebuffer(GL_FRAMEBUFFER, fbo);
	glViewport(x, y, w, h);
	glDrawArrays(GL_TRIANGLES, 0, 3);
}

/* renderer.py, Renderer.render: one viewport (x, y, w, h, origin bottom-left) into `out`. */
static void draw(double unix_time, GLuint out, int x, int y, int w, int h)
{
	uint32_t sec;
	float frac;
	split_time(unix_time, R.scene->epoch0, &sec, &frac);
	struct targets *tg = targets_for(w, h);
	const struct geometry *g = &tg->g;
	glDisable(GL_BLEND);
	glDisable(GL_DEPTH_TEST);
	glDisable(GL_SCISSOR_TEST);
	glBindVertexArray(R.vao);
	for (int t = 0; t < TEXTURE_COUNT; t++)
		bind(STATIC_UNIT[t], R.texture[t]);

	glUseProgram(R.program[PROGRAM_STATE]);
	glUniform1ui(R.state_u[STATE_SEC], sec);
	glUniform1f(R.state_u[STATE_FRAC], frac);
	glUniform1i(R.state_u[STATE_COLS], g->cols);
	glUniform1i(R.state_u[STATE_ROWS], g->rows);
	glUniform4f(R.state_u[STATE_KEEP], (GLfloat)g->keep[0], (GLfloat)g->keep[1], (GLfloat)g->keep[2],
	            (GLfloat)g->keep[3]);
	run_pass(tg->fbo[T_STATE], g->cols, g->rows, 0, 0);

	bind(UNIT_STATE, tg->tex[T_STATE]);
	glUseProgram(R.program[PROGRAM_FIELD]);
	glUniform1i(R.field_u[FIELD_COLS], g->cols);
	glUniform1i(R.field_u[FIELD_ROWS], g->rows);
	run_pass(tg->fbo[T_FIELD], g->cols, g->rows, 0, 0);

	glUseProgram(R.program[PROGRAM_GLYPHS]);
	glUniform1ui(R.glyphs_u[GLYPHS_SEC], sec);
	glUniform1f(R.glyphs_u[GLYPHS_FRAC], frac);
	glUniform1i(R.glyphs_u[GLYPHS_COLS], g->cols);
	glUniform1i(R.glyphs_u[GLYPHS_ROWS], g->rows);
	glUniform1f(R.glyphs_u[GLYPHS_CELL], (GLfloat)g->cell);
	glUniform1f(R.glyphs_u[GLYPHS_COL0], (GLfloat)g->col0);
	glUniform2f(R.glyphs_u[GLYPHS_RES], (GLfloat)w, (GLfloat)h);
	glUniform2f(R.glyphs_u[GLYPHS_TARGET], (GLfloat)g->qw, (GLfloat)g->qh);
	run_pass(tg->fbo[T_GLYPHS], g->qw, g->qh, 0, 0);

	glUseProgram(R.program[PROGRAM_BLUR]);
	glUniform1f(R.blur_u[BLUR_SIGMA], (GLfloat)g->sigma);
	bind(UNIT_SRC, tg->tex[T_GLYPHS]);
	glUniform2f(R.blur_u[BLUR_STEP], (GLfloat)g->step_h[0], (GLfloat)g->step_h[1]);
	run_pass(tg->fbo[T_BLUR_A], g->qw, g->qh, 0, 0);
	bind(UNIT_SRC, tg->tex[T_BLUR_A]);
	glUniform2f(R.blur_u[BLUR_STEP], (GLfloat)g->step_v[0], (GLfloat)g->step_v[1]);
	run_pass(tg->fbo[T_BLUR_B], g->qw, g->qh, 0, 0);

	bind(UNIT_FIELD, tg->tex[T_FIELD]);
	bind(UNIT_BLOOM, tg->tex[T_BLUR_B]);
	glUseProgram(R.program[PROGRAM_COMPOSITE]);
	glUniform1ui(R.comp_u[COMP_SEC], sec);
	glUniform1f(R.comp_u[COMP_FRAC], frac);
	glUniform1i(R.comp_u[COMP_COLS], g->cols);
	glUniform1i(R.comp_u[COMP_ROWS], g->rows);
	glUniform1f(R.comp_u[COMP_CELL], (GLfloat)g->cell);
	glUniform1f(R.comp_u[COMP_COL0], (GLfloat)g->col0);
	glUniform2f(R.comp_u[COMP_RES], (GLfloat)w, (GLfloat)h);
	glUniform2f(R.comp_u[COMP_ORIGIN], (GLfloat)x, (GLfloat)y);
	glUniform2f(R.comp_u[COMP_BGSCALE], (GLfloat)g->bg_scale[0], (GLfloat)g->bg_scale[1]);
	glUniform2f(R.comp_u[COMP_BGOFFSET], (GLfloat)g->bg_offset[0], (GLfloat)g->bg_offset[1]);
	run_pass(out, w, h, x, y);
}

void render_frame(struct render_surface *rs, double unix_time, double scale)
{
	if (R.current != rs) {
		eglMakeCurrent(R.display, rs->surface, rs->surface, R.context);
		R.current = rs;
	}
	if (!rs->interval_set) {
		eglSwapInterval(R.display, 0);       /* the frame callbacks pace the frames, never the swap */
		rs->interval_set = true;
	}
	int w = rs->width, h = rs->height;
	if (scale < 0.999) {                     /* app.py, RainArea._draw */
		int sw = (int)py_round(w * scale), sh = (int)py_round(h * scale);
		sw = 64 > sw ? 64 : sw;
		sh = 36 > sh ? 36 : sh;
		GLuint off = offscreen_for(sw, sh);
		draw(unix_time, off, 0, 0, sw, sh);
		glBindFramebuffer(GL_READ_FRAMEBUFFER, off);
		glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
		glBlitFramebuffer(0, 0, sw, sh, 0, 0, w, h, GL_COLOR_BUFFER_BIT, GL_LINEAR);
		glBindFramebuffer(GL_FRAMEBUFFER, 0);
	} else {
		draw(unix_time, 0, 0, 0, w, h);
	}
	check("a frame");
}

bool render_swap(struct render_surface *rs, unsigned *error)
{
	R.swaps++;
	if (R.fail_count > 0 && R.swaps >= R.fail_from && R.swaps < R.fail_from + R.fail_count) {
		*error = 0x3003;                           /* EGL_BAD_ALLOC */
		return false;
	}
	if (eglSwapBuffers(R.display, rs->surface))
		return true;
	*error = (unsigned)eglGetError();
	return false;
}

void render_shutdown(void)
{
	if (R.display == EGL_NO_DISPLAY)
		return;
	if (R.context != EGL_NO_CONTEXT) {
		eglMakeCurrent(R.display, EGL_NO_SURFACE, EGL_NO_SURFACE, R.context);
		for (int i = 0; i < MAX_TARGETS; i++)
			if (R.targets[i].used)
				delete_targets(&R.targets[i]);
		for (int i = 0; i < MAX_OFFSCREEN; i++)
			if (R.offscreen[i].used) {
				glDeleteFramebuffers(1, &R.offscreen[i].fbo);
				glDeleteTextures(1, &R.offscreen[i].tex);
			}
		glDeleteTextures(TEXTURE_COUNT, R.texture);
		for (int p = 0; p < PROGRAM_COUNT; p++)
			glDeleteProgram(R.program[p]);
		glDeleteVertexArrays(1, &R.vao);
		eglMakeCurrent(R.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
		eglDestroyContext(R.display, R.context);
	}
	eglTerminate(R.display);
	eglReleaseThread();
	R.display = EGL_NO_DISPLAY;
	R.context = EGL_NO_CONTEXT;
}
