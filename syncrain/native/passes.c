/* The six passes, the same calls in the same order as renderer.py, on whatever OpenGL context is
 * current: the native wallpaper's own (render.c) or the one Qt Quick gives the Plasma wallpaper
 * (syncrain/plasma/). A `struct passes` is what one context made: the programs, the textures every
 * frame reads, and each viewport size's intermediate textures.
 *
 * The OpenGL functions come from the caller's getProcAddress, so building needs no OpenGL headers.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "syncrain.h"

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


#define DECLARE(ret, name, args) static ret(*name) args;
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

struct passes {
	const struct scene *scene;
	bool es;
	GLuint program[PROGRAM_COUNT];
	GLint state_u[STATE_N], field_u[FIELD_N], glyphs_u[GLYPHS_N], blur_u[BLUR_N], comp_u[COMP_N];
	GLuint texture[TEXTURE_COUNT];
	GLuint vao;
	struct targets targets[MAX_TARGETS];
	struct offscreen offscreen[MAX_OFFSCREEN];
};

static bool debug;

static void check(const char *what)
{
	if (!debug)
		return;
	for (GLenum e; (e = glGetError()) != GL_NO_ERROR; )
		fprintf(stderr, "syncrain: OpenGL error 0x%04x after %s\n", e, what);
}

bool passes_load_gl(void *(*address)(const char *name), char *why, size_t why_size)
{
	debug = getenv("SYNCRAIN_GL_DEBUG") && *getenv("SYNCRAIN_GL_DEBUG");
#define LOAD_GL(ret, name, args) \
	if (!(*(void **)&name = address(#name))) { \
		snprintf(why, why_size, "OpenGL lacks %s", #name); \
		return false; \
	}
	GL_FUNCTIONS(LOAD_GL)
	return true;
}

void passes_gl_version(int *major, int *minor, const char **renderer)
{
	GLint a = 0, b = 0;
	glGetIntegerv(GL_MAJOR_VERSION, &a);
	glGetIntegerv(GL_MINOR_VERSION, &b);
	*major = a;
	*minor = b;
	*renderer = (const char *)glGetString(GL_RENDERER);
}

/* ------------------------------------------------------------------ programs and textures */

static const char *const HEADER_ES = "#version 300 es\nprecision highp float;\nprecision highp int;\n"
                                     "precision highp sampler2D;\n";
static const char *const HEADER_GL = "#version 330 core\n";

static GLuint compile(bool es, GLenum kind, struct blob body, const char *name, char *why, size_t why_size)
{
	const char *header = es ? HEADER_ES : HEADER_GL;
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

static bool build_program(struct passes *P, enum program p, char *why, size_t why_size)
{
	const char *name = scene_program_name(p);
	GLuint vert = compile(P->es, GL_VERTEX_SHADER, P->scene->vertex, name, why, why_size);
	if (!vert)
		return false;
	GLuint frag = compile(P->es, GL_FRAGMENT_SHADER, P->scene->fragment[p], name, why, why_size);
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
	P->program[p] = program;
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
static void set_static_uniforms(struct passes *P)
{
	for (int i = 0; i < P->scene->uniforms; i++) {
		const struct uniform_source *u = &P->scene->uniform[i];
		glUseProgram(P->program[u->program]);
		GLint loc = glGetUniformLocation(P->program[u->program], u->name);
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

static void locate(struct passes *P, enum program p, const char *const *names, int n, GLint *out)
{
	for (int i = 0; i < n; i++)
		out[i] = glGetUniformLocation(P->program[p], names[i]);
}

struct passes *passes_create(const struct scene *scene, bool es, char *why, size_t why_size)
{
	struct passes *P = calloc(1, sizeof *P);
	if (!P) {
		snprintf(why, why_size, "out of memory");
		return NULL;
	}
	P->scene = scene;
	P->es = es;
	for (int p = 0; p < PROGRAM_COUNT; p++)
		if (!build_program(P, (enum program)p, why, why_size)) {
			passes_destroy(P);
			return NULL;
		}
	for (int t = 0; t < TEXTURE_COUNT; t++) {
		const struct texture_source *src = &scene->texture[t];
		P->texture[t] = make_texture(src->width, src->height, src->pixels.data, src->filter);
	}
	set_static_uniforms(P);
	locate(P, PROGRAM_STATE, STATE_U, STATE_N, P->state_u);
	locate(P, PROGRAM_FIELD, FIELD_U, FIELD_N, P->field_u);
	locate(P, PROGRAM_GLYPHS, GLYPHS_U, GLYPHS_N, P->glyphs_u);
	locate(P, PROGRAM_BLUR, BLUR_U, BLUR_N, P->blur_u);
	locate(P, PROGRAM_COMPOSITE, COMP_U, COMP_N, P->comp_u);
	glGenVertexArrays(1, &P->vao);
	glFinish();                                    /* the pixels can go once the card has them */
	check("setting up");
	return P;
}

/* ------------------------------------------------------------------ a frame */

static void delete_targets(struct targets *t)
{
	glDeleteFramebuffers(T_COUNT, t->fbo);
	glDeleteTextures(T_COUNT, t->tex);
	t->used = false;
}

static struct targets *targets_for(struct passes *P, int w, int h)
{
	int used = 0;
	for (int i = 0; i < MAX_TARGETS; i++) {
		if (P->targets[i].used && P->targets[i].g.width == w && P->targets[i].g.height == h)
			return &P->targets[i];
		used += P->targets[i].used;
	}
	if (used == MAX_TARGETS)
		for (int i = 0; i < MAX_TARGETS; i++)
			delete_targets(&P->targets[i]);
	struct targets *t = NULL;
	for (int i = 0; i < MAX_TARGETS && !t; i++)
		if (!P->targets[i].used)
			t = &P->targets[i];
	geometry_compute(&t->g, P->scene, w, h);
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

static GLuint offscreen_for(struct passes *P, int w, int h)
{
	for (int i = 0; i < MAX_OFFSCREEN; i++)
		if (P->offscreen[i].used && P->offscreen[i].width == w && P->offscreen[i].height == h)
			return P->offscreen[i].fbo;
	struct offscreen *o = &P->offscreen[0];
	for (int i = 0; i < MAX_OFFSCREEN; i++)
		if (!P->offscreen[i].used) {
			o = &P->offscreen[i];
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
void passes_draw(struct passes *P, double unix_time, unsigned out, int x, int y, int w, int h)
{
	uint32_t sec;
	float frac;
	split_time(unix_time, P->scene->epoch0, &sec, &frac);
	struct targets *tg = targets_for(P, w, h);
	const struct geometry *g = &tg->g;
	glDisable(GL_BLEND);
	glDisable(GL_DEPTH_TEST);
	glDisable(GL_SCISSOR_TEST);
	glBindVertexArray(P->vao);
	for (int t = 0; t < TEXTURE_COUNT; t++)
		bind(STATIC_UNIT[t], P->texture[t]);

	glUseProgram(P->program[PROGRAM_STATE]);
	glUniform1ui(P->state_u[STATE_SEC], sec);
	glUniform1f(P->state_u[STATE_FRAC], frac);
	glUniform1i(P->state_u[STATE_COLS], g->cols);
	glUniform1i(P->state_u[STATE_ROWS], g->rows);
	glUniform4f(P->state_u[STATE_KEEP], (GLfloat)g->keep[0], (GLfloat)g->keep[1], (GLfloat)g->keep[2],
	            (GLfloat)g->keep[3]);
	run_pass(tg->fbo[T_STATE], g->cols, g->rows, 0, 0);

	bind(UNIT_STATE, tg->tex[T_STATE]);
	glUseProgram(P->program[PROGRAM_FIELD]);
	glUniform1i(P->field_u[FIELD_COLS], g->cols);
	glUniform1i(P->field_u[FIELD_ROWS], g->rows);
	run_pass(tg->fbo[T_FIELD], g->cols, g->rows, 0, 0);

	glUseProgram(P->program[PROGRAM_GLYPHS]);
	glUniform1ui(P->glyphs_u[GLYPHS_SEC], sec);
	glUniform1f(P->glyphs_u[GLYPHS_FRAC], frac);
	glUniform1i(P->glyphs_u[GLYPHS_COLS], g->cols);
	glUniform1i(P->glyphs_u[GLYPHS_ROWS], g->rows);
	glUniform1f(P->glyphs_u[GLYPHS_CELL], (GLfloat)g->cell);
	glUniform1f(P->glyphs_u[GLYPHS_COL0], (GLfloat)g->col0);
	glUniform2f(P->glyphs_u[GLYPHS_RES], (GLfloat)w, (GLfloat)h);
	glUniform2f(P->glyphs_u[GLYPHS_TARGET], (GLfloat)g->qw, (GLfloat)g->qh);
	run_pass(tg->fbo[T_GLYPHS], g->qw, g->qh, 0, 0);

	glUseProgram(P->program[PROGRAM_BLUR]);
	glUniform1f(P->blur_u[BLUR_SIGMA], (GLfloat)g->sigma);
	bind(UNIT_SRC, tg->tex[T_GLYPHS]);
	glUniform2f(P->blur_u[BLUR_STEP], (GLfloat)g->step_h[0], (GLfloat)g->step_h[1]);
	run_pass(tg->fbo[T_BLUR_A], g->qw, g->qh, 0, 0);
	bind(UNIT_SRC, tg->tex[T_BLUR_A]);
	glUniform2f(P->blur_u[BLUR_STEP], (GLfloat)g->step_v[0], (GLfloat)g->step_v[1]);
	run_pass(tg->fbo[T_BLUR_B], g->qw, g->qh, 0, 0);

	bind(UNIT_FIELD, tg->tex[T_FIELD]);
	bind(UNIT_BLOOM, tg->tex[T_BLUR_B]);
	glUseProgram(P->program[PROGRAM_COMPOSITE]);
	glUniform1ui(P->comp_u[COMP_SEC], sec);
	glUniform1f(P->comp_u[COMP_FRAC], frac);
	glUniform1i(P->comp_u[COMP_COLS], g->cols);
	glUniform1i(P->comp_u[COMP_ROWS], g->rows);
	glUniform1f(P->comp_u[COMP_CELL], (GLfloat)g->cell);
	glUniform1f(P->comp_u[COMP_COL0], (GLfloat)g->col0);
	glUniform2f(P->comp_u[COMP_RES], (GLfloat)w, (GLfloat)h);
	glUniform2f(P->comp_u[COMP_ORIGIN], (GLfloat)x, (GLfloat)y);
	glUniform2f(P->comp_u[COMP_BGSCALE], (GLfloat)g->bg_scale[0], (GLfloat)g->bg_scale[1]);
	glUniform2f(P->comp_u[COMP_BGOFFSET], (GLfloat)g->bg_offset[0], (GLfloat)g->bg_offset[1]);
	run_pass(out, w, h, x, y);
}

/* At `scale` below 0.999 the frame is drawn smaller and blown up (app.py, RainArea._draw). */
void passes_draw_scaled(struct passes *P, double unix_time, unsigned out, int w, int h, double scale)
{
	if (scale < 0.999) {
		int sw = (int)py_round(w * scale), sh = (int)py_round(h * scale);
		sw = 64 > sw ? 64 : sw;
		sh = 36 > sh ? 36 : sh;
		GLuint off = offscreen_for(P, sw, sh);
		passes_draw(P, unix_time, off, 0, 0, sw, sh);
		glBindFramebuffer(GL_READ_FRAMEBUFFER, off);
		glBindFramebuffer(GL_DRAW_FRAMEBUFFER, out);
		glBlitFramebuffer(0, 0, sw, sh, 0, 0, w, h, GL_COLOR_BUFFER_BIT, GL_LINEAR);
		glBindFramebuffer(GL_FRAMEBUFFER, out);
	} else {
		passes_draw(P, unix_time, out, 0, 0, w, h);
	}
	check("a frame");
}

/* With its context current. */
void passes_destroy(struct passes *P)
{
	if (!P)
		return;
	for (int i = 0; i < MAX_TARGETS; i++)
		if (P->targets[i].used)
			delete_targets(&P->targets[i]);
	for (int i = 0; i < MAX_OFFSCREEN; i++)
		if (P->offscreen[i].used) {
			glDeleteFramebuffers(1, &P->offscreen[i].fbo);
			glDeleteTextures(1, &P->offscreen[i].tex);
		}
	glDeleteTextures(TEXTURE_COUNT, P->texture);
	for (int p = 0; p < PROGRAM_COUNT; p++)
		if (P->program[p])
			glDeleteProgram(P->program[p]);
	if (P->vao)
		glDeleteVertexArrays(1, &P->vao);
	free(P);
}
