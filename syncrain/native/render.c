/* EGL for the native wallpaper: one OpenGL context, a window surface per screen; the six passes
 * themselves are passes.c's.
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
	struct gl_info info;
	long fail_from, fail_count, swaps;      /* SYNCRAIN_TEST_SWAP_FAILURES, for tests/wayland only */
	struct passes *passes;
	struct render_surface *current;
} R;

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
	if (!passes_load_gl(gl_address, why, why_size)) {
		eglMakeCurrent(R.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
		eglDestroyContext(R.display, context);
		return false;
	}
	int major = 0, minor = 0;
	const char *renderer = NULL;
	passes_gl_version(&major, &minor, &renderer);
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
	snprintf(R.info.renderer, sizeof R.info.renderer, "%s", renderer ? renderer : "unknown renderer");
	return true;
}

bool render_init(struct wl_display *display, const struct scene *scene, char *why, size_t why_size)
{
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
	R.passes = passes_create(scene, R.info.es, why, why_size);
	return R.passes != NULL;
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

bool render_frame(struct render_surface *rs, double unix_time, double scale, unsigned *error)
{
	if (R.current != rs) {
		/* cached only once it holds: a failed switch is tried again next frame, not taken for done
		 * (drawing into another screen's surface meanwhile). EGL keeps what was current then, so the
		 * record stays as it is: that surface is still unbound before it is destroyed. */
		if (!eglMakeCurrent(R.display, rs->surface, rs->surface, R.context)) {
			*error = (unsigned)eglGetError();
			return false;
		}
		R.current = rs;
	}
	if (!rs->interval_set) {
		eglSwapInterval(R.display, 0);       /* the frame callbacks pace the frames, never the swap */
		rs->interval_set = true;
	}
	passes_draw_scaled(R.passes, unix_time, 0, rs->width, rs->height, scale);
	return true;
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
		passes_destroy(R.passes);
		R.passes = NULL;
		eglMakeCurrent(R.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
		eglDestroyContext(R.display, R.context);
	}
	eglTerminate(R.display);
	eglReleaseThread();
	R.display = EGL_NO_DISPLAY;
	R.context = EGL_NO_CONTEXT;
}
