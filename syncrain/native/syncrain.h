/* The native wallpaper (syncrain/native/): what its parts share. wallpaper.c says what it is. */
#ifndef SYNCRAIN_H
#define SYNCRAIN_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

struct wl_display;
struct wl_surface;

/* ------------------------------------------------------------------ the scene (scene.c)
 * Everything a frame needs that never changes, prepared by the Python launcher (syncrain/native.py)
 * from the same code the GTK host uses: the shader sources, the textures' pixels, the uniforms set
 * once. It arrives as a memfd and is unmapped once it is on the graphics card. */

enum program { PROGRAM_STATE, PROGRAM_FIELD, PROGRAM_GLYPHS, PROGRAM_BLUR, PROGRAM_COMPOSITE, PROGRAM_COUNT };
/* The textures every frame reads, in the order a frame binds them (renderer.py, STATIC_TEXTURES). */
enum texture { TEXTURE_ATLAS, TEXTURE_LUT, TEXTURE_WORDS, TEXTURE_LOGO, TEXTURE_BG, TEXTURE_MASK, TEXTURE_COUNT };
enum filter { FILTER_NEAREST, FILTER_LINEAR, FILTER_MIP };
enum keep { KEEP_NONE, KEEP_LOGO, KEEP_MASK };

struct blob {
	const char *data;
	size_t size;
};

struct texture_source {
	bool set;
	int width, height;
	enum filter filter;
	struct blob pixels;
};

#define UNIFORM_VALUES 16

struct uniform_source {
	enum program program;
	char name[40];
	char kind[4];                       /* i, ui, f, f2, f3, f4 or f4v */
	int count;
	double value[UNIFORM_VALUES];
	long long integer[UNIFORM_VALUES];
};

struct scene {
	char describe[160];                 /* "syncrain build <N> (stream <id>)" */
	long long epoch0;
	int cols;
	enum keep keep;                     /* which cells the hidden words keep clear */
	double logo_size, drift, mask_bbox[4];
	int bg_width, bg_height;            /* 0 without a background image */
	struct blob vertex, fragment[PROGRAM_COUNT];
	struct texture_source texture[TEXTURE_COUNT];
	struct uniform_source *uniform;
	int uniforms;
	char *kwin_script;                  /* the KWin script, "@SERVICE@" still to fill in */
	char **fallback;                    /* the GTK host's command line, or NULL */
	void *map;
	size_t map_size;
};

const char *scene_program_name(enum program program);
bool scene_load(struct scene *scene, int fd, char *why, size_t why_size);
void scene_unmap(struct scene *scene);  /* the sources and pixels, once they are on the card */

/* ------------------------------------------------------------------ arithmetic (timing.c)
 * Every value here must equal what the Python host computes (renderer.py, engine.py, pacing.py),
 * double for double, so the same moment draws the same frame; tests/native compares them. */

double py_floordiv(double x, double y);   /* Python's float // */
double py_round(double x);                /* Python's round(): halves to even */

struct geometry {
	int width, height, cols, rows, qw, qh;
	double cell, col0;
	double keep[4], bg_scale[2], bg_offset[2], sigma, step_h[2], step_v[2];
};

void geometry_compute(struct geometry *g, const struct scene *scene, int width, int height);
void split_time(double unix_seconds, long long epoch0, uint32_t *seconds, float *fraction);
int64_t monotonic_us(void);
double monotonic_s(void);
double realtime_s(void);

struct pacer {
	double period;
	bool has_target;
	double target;                      /* the refresh the frame being asked for is drawn for */
	double shift;                       /* microseconds added to the lead by what was reported */
	bool has_settled;
	double settled_after;               /* frames drawn for refreshes up to this one predate the last nudge */
};

void pacer_init(struct pacer *p, double fps);
int pacer_step(const struct pacer *p, double refresh);
double pacer_lead(const struct pacer *p, double refresh);
void pacer_shown(struct pacer *p, double target, double presented, double refresh);
double pacer_plan(struct pacer *p, double now, double refresh, double vblank);
void pacer_restart(struct pacer *p);

int spacing(const double *presented, int n, double refresh, int *steps);
double steady(const double *delays, int n);

/* ------------------------------------------------------------------ drawing (render.c) */

struct gl_info {
	bool es;
	int major, minor;
	char renderer[160];
	char egl[160];
};

struct render_surface;

/* EGL and OpenGL with no surface yet, the programs compiled, the textures uploaded: whatever cannot
 * work here fails before a screen is covered. */
bool render_init(struct wl_display *display, const struct scene *scene, char *why, size_t why_size);
void render_info(struct gl_info *info);
struct render_surface *render_surface_create(struct wl_surface *surface, int width, int height,
                                             char *why, size_t why_size);
void render_surface_resize(struct render_surface *rs, int width, int height);
void render_surface_destroy(struct render_surface *rs);
/* Draws the frame for `unix_time` into the surface's back buffer (at `scale` of its size, blown up,
 * below 0.999); the caller then asks for the compositor's callbacks and calls render_swap, which
 * says whether the frame went to the compositor (false: nothing was committed; the EGL error is in
 * *error). */
void render_frame(struct render_surface *rs, double unix_time, double scale);
bool render_swap(struct render_surface *rs, unsigned *error);
void render_shutdown(void);

/* ------------------------------------------------------------------ KWin (kwin.c) */

/* Asks KWin which screens a window covers (syncrain/hidden.py, Watch). */
struct watch;

struct watch *watch_new(void (*on_change)(void));
const char *watch_start(struct watch *w, const char *script_template, bool maximized); /* NULL: running */
void watch_stop(struct watch *w);
void watch_free(struct watch *w);
void watch_retry(struct watch *w);
int watch_fd(const struct watch *w);
void watch_dispatch(struct watch *w);
bool watch_answered(const struct watch *w);
bool watch_hidden(const struct watch *w, const char *screen);
bool is_syncrain_command(char **argv, int argc);

#endif
