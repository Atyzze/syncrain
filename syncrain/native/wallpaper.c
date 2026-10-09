/* syncrain's wallpaper on Wayland, with neither Python nor GTK in memory.
 *
 * `syncrain` (syncrain/app.py) reads the options, and on a Wayland session it prepares a scene
 * (syncrain/native.py: the shader sources, the textures' pixels, the uniforms set once, all made by
 * the same code as the GTK host's) and replaces its own process with this program. What stays in
 * memory for as long as the wallpaper runs is this program, libwayland, libEGL, libdbus and the
 * graphics driver: no interpreter, no toolkit, one OpenGL context for every screen.
 *
 * Every screen gets a layer-shell surface (the bottom layer on KDE Plasma, chosen by the launcher,
 * the background layer elsewhere), click-through, opaque, at the screen's own pixel size. A frame
 * is drawn when the pacer asks for it (syncrain/pacing.py, ported to timing.c), for the refresh it
 * will be shown on, and only after the compositor has called back for the frame before, as GTK's
 * frame clock does: a screen the compositor stops asking for frames costs nothing. The refresh
 * grid comes from the compositor's presentation feedback, read the way GTK reads it
 * (gdk/gdkframeclock.c, get_refresh_info; gdk/wayland/gdksurface-wayland.c), so the pacer is fed
 * what it was built and tested on. On KDE Plasma a screen a window covers is not drawn (kwin.c).
 *
 * Whatever fails before the first frame (no Wayland, no layer-shell, no EGL, OpenGL too old, a
 * shader the driver refuses) hands over to the GTK host by running the command the scene names,
 * so the wallpaper draws wherever build 7 drew. `--probe` reports what this program finds without
 * drawing (syncrain --diagnose shows it); `--selftest` serves tests/native.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <malloc.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/signalfd.h>
#include <time.h>
#include <unistd.h>

#include <wayland-client.h>

#include "fractional-scale-v1.h"
#include "presentation-time.h"
#include "syncrain.h"
#include "viewporter.h"
#include "wlr-layer-shell-unstable-v1.h"

int selftest(const char *what);

/* ------------------------------------------------------------------ options */

enum pause { PAUSE_MAXIMIZED, PAUSE_FULLSCREEN, PAUSE_NEVER };

static struct {
	int scene_fd;
	double fps;
	enum pause pause_under;
	double scale;
	bool bottom;
	double offset;
	bool has_time;
	double time;
	bool probe;
	double debug_fps;                    /* SYNCRAIN_DEBUG_FPS */
} opt = { .scene_fd = -1, .fps = 30.0, .scale = 1.0 };

static void usage(void)
{
	fprintf(stderr, "syncrain-wallpaper is started by syncrain (syncrain/native.py), not by hand\n");
	exit(2);
}

static double number(const char *s)
{
	char *end;
	double v = strtod(s, &end);
	if (end == s || *end)
		usage();
	return v;
}

static void parse_options(int argc, char **argv)
{
	for (int i = 1; i < argc; i++) {
		const char *a = argv[i], *v = i + 1 < argc ? argv[i + 1] : NULL;
		if (strcmp(a, "--probe") == 0) {
			opt.probe = true;
			continue;
		}
		if (strcmp(a, "--selftest") == 0 && v)
			exit(selftest(v));
		if (!v)
			usage();
		i++;
		if (strcmp(a, "--scene") == 0)
			opt.scene_fd = (int)number(v);
		else if (strcmp(a, "--fps") == 0)
			opt.fps = number(v);
		else if (strcmp(a, "--pause-under") == 0)
			opt.pause_under = strcmp(v, "never") == 0 ? PAUSE_NEVER
			                  : strcmp(v, "fullscreen") == 0 ? PAUSE_FULLSCREEN : PAUSE_MAXIMIZED;
		else if (strcmp(a, "--scale") == 0)
			opt.scale = number(v);
		else if (strcmp(a, "--layer") == 0)
			opt.bottom = strcmp(v, "bottom") == 0;
		else if (strcmp(a, "--offset") == 0)
			opt.offset = number(v);
		else if (strcmp(a, "--time") == 0)
			opt.has_time = true, opt.time = number(v);
		else
			usage();
	}
	if (opt.scene_fd < 0)
		usage();
	const char *debug = getenv("SYNCRAIN_DEBUG_FPS");   /* app.py, debug_fps_interval */
	if (debug && *debug) {
		char *end;
		double v = strtod(debug, &end);
		opt.debug_fps = end == debug || *end ? 5.0 : (v > 0.5 ? v : 0.5);
	}
}

/* ------------------------------------------------------------------ state */

#define HISTORY 16                           /* GTK keeps sixteen frames' timings */
#define DEFAULT_REFRESH_US 16667
#define MAX_HISTORY_AGE_US 150000
#define MAX_SHOWN 65536

struct output {
	struct wl_list link;
	uint32_t global;
	struct wl_output *wl;
	char name[64];
	int scale;
	int refresh_mhz;
	int mode_width, mode_height;
	bool done;
	struct screen *screen;
};

/* One frame's timings, as GdkFrameTimings keeps them. */
struct frame {
	bool used;
	int64_t counter;
	int64_t presentation;                    /* monotonic microseconds; 0 until known */
	int64_t refresh;
	bool complete;
	bool pending_note;                       /* not yet passed to the pacer (app.py, _drawn) */
	bool has_target;
	double target, drawn_for;
	struct wp_presentation_feedback *feedback;
	struct screen *screen;
};

struct shown {
	double shown, refresh, drawn_for;
};

struct screen {
	struct wl_list link;
	struct output *output;
	struct wl_surface *surface;
	struct zwlr_layer_surface_v1 *layer;
	struct wp_viewport *viewport;
	struct wp_fractional_scale_v1 *fractional;
	struct render_surface *render;
	int width, height;                       /* surface size from the compositor */
	int buffer_width, buffer_height;
	int scale120;                            /* fractional scale in 120ths (0: not offered) */
	int preferred_scale;                     /* wl_surface's preferred buffer scale (0: not said) */
	bool configured;
	bool hidden;
	bool want_draw;                          /* asked to draw while the compositor's callback was pending */
	bool draw_now;
	struct wl_callback *frame_callback;
	int64_t callback_counter;
	int64_t counter;                         /* frames committed */
	struct frame history[HISTORY];
	struct pacer pacer;
	int64_t due;                             /* monotonic microseconds when the next frame is asked for */
	double drawn_for;
	int frames;
	double since;
	bool since_set;
	struct shown *shown;
	int nshown, shown_capacity;
	int64_t failing_since;                   /* monotonic microseconds of the first of the last failed swaps */
};

static struct {
	struct wl_display *display;
	struct wl_registry *registry;
	struct wl_compositor *compositor;
	uint32_t compositor_version;
	struct zwlr_layer_shell_v1 *layer_shell;
	uint32_t layer_shell_version;
	struct wp_presentation *presentation;
	struct wp_viewporter *viewporter;
	struct wp_fractional_scale_manager_v1 *fractional;
	struct wl_list outputs, screens;
	struct scene scene;
	bool ready;                              /* OpenGL is up: outputs get screens */
	bool announced;
	bool drawn;                              /* a frame was committed: no more handing over */
	const char *lost;                        /* why the wallpaper must stop with status 1 */
	bool settled;                            /* memory handed back since the screens last changed */
	bool running;
	struct watch *watch;
	bool watch_said, watch_retried;
	int64_t watch_check;
	int signal_fd;
	sigset_t old_mask;
} W;

/* ------------------------------------------------------------------ handing over */

static void restore_environment(void)
{
	const char *preload = getenv("SYNCRAIN_LD_PRELOAD");
	if (preload)
		setenv("LD_PRELOAD", preload, 1);
	unsetenv("SYNCRAIN_LD_PRELOAD");
}

/* Before the first frame, anything this program cannot do the GTK host may still do. */
static void hand_over(const char *why, int code, const char *headline)
{
	if (W.scene.fallback && !opt.probe && !W.drawn) {
		fprintf(stderr, "syncrain: the native wallpaper cannot draw here (%s); the GTK host takes over\n", why);
		fflush(NULL);
		restore_environment();
		sigprocmask(SIG_SETMASK, &W.old_mask, NULL);
		execvp(W.scene.fallback[0], W.scene.fallback);
		fprintf(stderr, "syncrain: the GTK host did not start: %s\n", strerror(errno));
	}
	if (headline)
		fprintf(stderr, "syncrain: %s\n", headline);
	else
		fprintf(stderr, "syncrain: %s\nsyncrain: nothing can be drawn, so the wallpaper is closed again. "
		                "`syncrain --diagnose` shows what this machine offers.\n", why);
	exit(code);
}

/* ------------------------------------------------------------------ frame timings, as GTK keeps them */

static struct frame *frame_of(struct screen *s, int64_t counter)
{
	if (counter <= 0)
		return NULL;
	struct frame *f = &s->history[counter % HISTORY];
	return f->used && f->counter == counter ? f : NULL;
}

static int64_t output_refresh(const struct screen *s)
{
	int mhz = s->output ? s->output->refresh_mhz : 0;
	return mhz > 0 ? 1000000000LL / mhz : DEFAULT_REFRESH_US;
}

/* gdk/wayland/gdksurface-wayland.c, fill_presentation_time_from_frame_time: the callback's
 * millisecond timestamp plus a refresh, until the presentation feedback says better. */
static void guess_presentation(struct frame *f, uint32_t frame_time)
{
	int64_t now = monotonic_us();
	uint32_t now_low = (uint32_t)(now / 1000);
	if (frame_time - now_low < 1000 || frame_time - now_low > (uint32_t)-1000) {
		int64_t last = now + (int64_t)1000 * (int32_t)(frame_time - now_low);
		if ((int32_t)now_low < 0 && (int32_t)frame_time > 0)
			last += (int64_t)1000 * 0x100000000LL;
		else if ((int32_t)now_low > 0 && (int32_t)frame_time < 0)
			last -= (int64_t)1000 * 0x100000000LL;
		f->presentation = last + f->refresh;
	}
}

static void frame_done(void *data, struct wl_callback *callback, uint32_t time)
{
	struct screen *s = data;
	wl_callback_destroy(callback);
	s->frame_callback = NULL;
	struct frame *f = frame_of(s, s->callback_counter);
	if (f) {
		f->refresh = output_refresh(s);
		guess_presentation(f, time);
		f->complete = true;
	}
	if (s->want_draw) {
		s->want_draw = false;
		s->draw_now = true;
	}
}

static const struct wl_callback_listener frame_listener = { frame_done };

static void feedback_sync_output(void *data, struct wp_presentation_feedback *fb, struct wl_output *output)
{
	(void)data, (void)fb, (void)output;
}

static void feedback_presented(void *data, struct wp_presentation_feedback *fb, uint32_t sec_hi, uint32_t sec_lo,
                               uint32_t nsec, uint32_t refresh, uint32_t seq_hi, uint32_t seq_lo, uint32_t flags)
{
	(void)refresh, (void)seq_hi, (void)seq_lo, (void)flags;
	struct frame *f = data;
	if (f->feedback == fb) {
		f->presentation = (int64_t)((((uint64_t)sec_hi << 32) | sec_lo) * 1000000 + nsec / 1000);
		f->complete = true;
		f->feedback = NULL;
	}
	wp_presentation_feedback_destroy(fb);
}

static void feedback_discarded(void *data, struct wp_presentation_feedback *fb)
{
	struct frame *f = data;
	if (f->feedback == fb)
		f->feedback = NULL;
	wp_presentation_feedback_destroy(fb);
}

static const struct wp_presentation_feedback_listener feedback_listener = {
	feedback_sync_output, feedback_presented, feedback_discarded,
};

/* gdk_frame_clock_get_refresh_info: the latest known presentation within 150 ms, moved forward to
 * the first refresh at or after `base`, and the refresh interval; (default interval, 0) otherwise. */
static void refresh_info(struct screen *s, int64_t base, double *refresh_out, double *vblank_out)
{
	int64_t fallback = DEFAULT_REFRESH_US;
	for (int64_t c = s->counter; c > s->counter - HISTORY; c--) {
		struct frame *f = frame_of(s, c);
		if (!f)
			break;
		int64_t refresh = f->refresh;
		if (refresh == 0)
			refresh = fallback;
		else
			fallback = refresh;
		if (f->presentation != 0) {
			if (f->presentation > base - MAX_HISTORY_AGE_US) {
				int64_t p = f->presentation;
				while (p < base)
					p += refresh;
				*refresh_out = (double)refresh;
				*vblank_out = (double)p;
				return;
			}
			break;
		}
	}
	*refresh_out = (double)fallback;
	*vblank_out = 0;
}

/* ------------------------------------------------------------------ what a frame reports */

static int screen_index(const struct screen *s)
{
	int i = 0;
	const struct screen *t;
	wl_list_for_each(t, &W.screens, link) {
		if (t == s)
			return i;
		i++;
	}
	return 0;
}

static void remember_shown(struct screen *s, const struct frame *f)
{
	if (s->nshown == s->shown_capacity) {
		if (s->shown_capacity >= MAX_SHOWN) {
			memmove(s->shown, s->shown + 1, sizeof *s->shown * (size_t)(s->nshown - 1));
			s->nshown--;
		} else {
			int capacity = s->shown_capacity ? s->shown_capacity * 2 : 256;
			struct shown *more = realloc(s->shown, sizeof *more * (size_t)capacity);
			if (!more)
				return;
			s->shown = more;
			s->shown_capacity = capacity;
		}
	}
	s->shown[s->nshown++] = (struct shown){ (double)f->presentation, (double)f->refresh, f->drawn_for };
}

/* app.py, RainArea._timing */
static void timing_text(struct screen *s, char *out, size_t size)
{
	out[0] = '\0';
	int n = s->nshown;
	double refresh = n ? s->shown[n - 1].refresh : 0;
	int *steps = n > 1 ? malloc(sizeof(int) * (size_t)n) : NULL;
	double *presented = n ? malloc(sizeof(double) * (size_t)n) : NULL;
	double *delays = n ? malloc(sizeof(double) * (size_t)n) : NULL;
	int k = 0;
	if (presented && (n < 2 || steps) && delays) {
		for (int i = 0; i < n; i++)
			presented[i] = s->shown[i].shown;
		k = spacing(presented, n, refresh, steps);
		if (k >= 2 && refresh > 0) {
			int step = pacer_step(&s->pacer, refresh);
			int even = 0;
			for (int i = 0; i < k; i++)
				even += steps[i] == step;
			for (int i = 1; i < n; i++)
				delays[i - 1] = s->shown[i].shown - s->shown[i].drawn_for;
			snprintf(out, size, ", spacing %d refresh%s %.0f%%, steady %.0f%%, lead %.1f ms", step,
			         step != 1 ? "es" : "", 100.0 * even / k, 100.0 * steady(delays, n - 1),
			         pacer_lead(&s->pacer, refresh) / 1000);
		}
	}
	free(steps);
	free(presented);
	free(delays);
	if (n) {                                 /* the last one stays, so the next report counts from it */
		s->shown[0] = s->shown[n - 1];
		s->nshown = 1;
	}
}

/* app.py, RainArea._note_presented: frames GTK still has timings for (this one and the fifteen
 * before), the complete ones told to the pacer in the order they were drawn. */
static void note_presented(struct screen *s)
{
	int64_t now = s->counter + 1;
	for (int64_t c = now - HISTORY + 1; c < now; c++) {
		struct frame *f = frame_of(s, c);
		if (!f || !f->pending_note || !f->complete)
			continue;
		f->pending_note = false;
		if (f->presentation > 0) {
			if (f->has_target)
				pacer_shown(&s->pacer, f->target, (double)f->presentation, (double)f->refresh);
			if (opt.debug_fps > 0)
				remember_shown(s, f);
		}
	}
}

static void report(struct screen *s)
{
	if (opt.debug_fps <= 0)
		return;
	double now = monotonic_s();
	s->frames++;
	if (s->since_set && now - s->since >= opt.debug_fps) {
		char timing[160];
		timing_text(s, timing, sizeof timing);
		printf("syncrain: %.1f fps at %dx%d (area %d)%s\n", s->frames / (now - s->since), s->buffer_width,
		       s->buffer_height, screen_index(s), timing);
		s->frames = 0;
		s->since = now;
	} else if (!s->since_set) {
		s->since = now;
		s->since_set = true;
	}
}

/* ------------------------------------------------------------------ drawing a screen */

/* app.py, RainArea._schedule */
static void schedule(struct screen *s)
{
	s->due = 0;
	if (s->hidden)
		return;
	int64_t now = monotonic_us();
	double refresh, vblank;
	refresh_info(s, now, &refresh, &vblank);
	double delay = pacer_plan(&s->pacer, (double)now, refresh, vblank);
	s->due = now + (int64_t)(delay > 1000 ? delay : 1000);
}

/* Once every screen shown has drawn its first frames (after startup, and after the screens changed):
 * hand back to the system what starting left free in the C heap, as the GTK host does (app.py,
 * settle_memory). The driver's shader compiler works there the first time it meets the shaders, and
 * with a cold shader cache (the first start after an install or a driver update) that held tens of
 * MiB until the process ended: on the operator's NVIDIA card the first native run of a sweep kept
 * 182 MiB, the later ones 123. Nothing is allocated per frame, so once is enough. */
static void settle_memory(void)
{
	if (W.settled)
		return;
	struct screen *s;
	int drawn = 0;
	wl_list_for_each(s, &W.screens, link) {
		if (s->hidden || (s->configured && !s->render))   /* covered, or a screen that cannot be drawn */
			continue;
		if (s->counter < 2)                       /* a new screen not yet configured counts too */
			return;
		drawn++;
	}
	if (!drawn)
		return;
	W.settled = true;
	malloc_trim(0);
	if (opt.debug_fps > 0) {
		long kib = 0;
		FILE *status = fopen("/proc/self/status", "r");
		char line[128];
		while (status && fgets(line, sizeof line, status))
			if (sscanf(line, "VmRSS: %ld", &kib) == 1)
				break;
		if (status)
			fclose(status);
		printf("syncrain: memory handed back after the first frames (%.0f MiB resident)\n", kib / 1024.0);
	}
}

/* The frame did not reach the compositor (a driver can fail a swap after a resume or a reset of the
 * card): nothing was committed, so neither its callback nor its feedback will come. Before any frame
 * was shown, the GTK host may still draw here. After, the next frame tries again at its time; frames
 * that cannot be shown for FAILING_US end the wallpaper with status 1, so its service starts it
 * afresh, as it would a crash. */
#define FAILING_US 5000000
static void swap_failed(struct screen *s, struct frame *f, unsigned error)
{
	char why[96];
	snprintf(why, sizeof why, "a frame could not be shown (EGL error 0x%x)", error);
	if (!W.drawn)
		hand_over(why, 69, NULL);
	wl_callback_destroy(s->frame_callback);
	s->frame_callback = NULL;
	s->want_draw = false;
	if (f->feedback)
		wp_presentation_feedback_destroy(f->feedback);
	f->feedback = NULL;
	f->pending_note = false;
	int64_t now = monotonic_us();
	if (!s->failing_since) {
		s->failing_since = now;
		fprintf(stderr, "syncrain: %s; the next frame tries again\n", why);
	} else if (now - s->failing_since >= FAILING_US && !W.lost) {
		static char lost[160];
		snprintf(lost, sizeof lost, "%s, again and again for %d s", why, FAILING_US / 1000000);
		W.lost = lost;
		W.running = false;
	}
}

static void draw(struct screen *s)
{
	int64_t now = monotonic_us();
	s->drawn_for = s->pacer.has_target ? s->pacer.target : (double)now;      /* RainArea._moment */
	double t = opt.has_time ? opt.time : realtime_s() + opt.offset + (s->drawn_for - (double)now) / 1e6;
	render_frame(s->render, t, opt.scale);
	note_presented(s);
	report(s);
	int64_t n = ++s->counter;
	struct frame *f = &s->history[n % HISTORY];
	if (f->feedback)
		wp_presentation_feedback_destroy(f->feedback);
	*f = (struct frame){ .used = true, .counter = n, .pending_note = true, .has_target = s->pacer.has_target,
	                     .target = s->pacer.target, .drawn_for = s->drawn_for, .screen = s };
	s->frame_callback = wl_surface_frame(s->surface);
	wl_callback_add_listener(s->frame_callback, &frame_listener, s);
	s->callback_counter = n;
	if (W.presentation) {
		f->feedback = wp_presentation_feedback(W.presentation, s->surface);
		wp_presentation_feedback_add_listener(f->feedback, &feedback_listener, f);
	}
	schedule(s);                                   /* before the commit, as the GTK host plans */
	unsigned error = 0;
	if (render_swap(s->render, &error)) {
		W.drawn = true;
		if (s->failing_since)
			fprintf(stderr, "syncrain: frames are shown again\n");
		s->failing_since = 0;
		settle_memory();
	} else {
		swap_failed(s, f, error);
	}
}

/* GTK's queue_render: now, or once the compositor has called back for the last frame. */
static void queue(struct screen *s)
{
	if (!s->render)
		return;
	if (s->frame_callback)
		s->want_draw = true;
	else
		s->draw_now = true;
}

/* app.py, RainArea.set_hidden */
static void set_hidden(struct screen *s, bool hidden)
{
	if (hidden == s->hidden)
		return;
	s->hidden = hidden;
	if (opt.debug_fps > 0)
		printf("syncrain: %s %s\n", s->output ? s->output->name : "",
		       hidden ? "covered, drawing stops" : "shown again, drawing resumes");
	if (hidden) {
		s->due = 0;
	} else {
		pacer_restart(&s->pacer);
		s->frames = 0;
		s->since = monotonic_s();
		s->since_set = true;
		for (int i = 0; i < HISTORY; i++)
			s->history[i].pending_note = false;
		s->nshown = 0;
		queue(s);
	}
}

/* app.py, App.update_hidden */
static void update_hidden(void)
{
	if (W.watch && watch_answered(W.watch) && !W.watch_said) {
		W.watch_said = true;
		printf("syncrain: drawing pauses on a screen under %s windows (KWin)\n",
		       opt.pause_under == PAUSE_MAXIMIZED ? "maximized and full-screen" : "full-screen");
	}
	struct screen *s;
	wl_list_for_each(s, &W.screens, link)
		set_hidden(s, W.watch ? watch_hidden(W.watch, s->output ? s->output->name : NULL) : false);
}

/* ------------------------------------------------------------------ screens */

static void announce(void)
{
	if (W.announced)
		return;
	W.announced = true;
	struct gl_info info;
	render_info(&info);
	int n = wl_list_length(&W.screens);
	printf("%s: %s %d.%d on %s, native wallpaper, %d screen%s\n", W.scene.describe, info.es ? "OpenGL ES" : "OpenGL",
	       info.major, info.minor, info.renderer, n, n == 1 ? "" : "s");
	if (opt.pause_under == PAUSE_NEVER)
		return;
	W.watch = watch_new(update_hidden);
	const char *why = W.watch ? watch_start(W.watch, W.scene.kwin_script, opt.pause_under == PAUSE_MAXIMIZED)
	                          : "out of memory";
	if (!why) {
		W.watch_check = monotonic_us() + 1500000;
		watch_dispatch(W.watch);
		return;
	}
	const char *desktop = getenv("XDG_CURRENT_DESKTOP");
	if ((desktop && strstr(desktop, "KDE")) || !strstr(why, "not on the session bus"))
		printf("syncrain: %s; drawing goes on under covering windows\n", why);
	watch_free(W.watch);
	W.watch = NULL;
}

static void apply_size(struct screen *s)
{
	int w = s->width, h = s->height, bw, bh;
	if (s->viewport && s->scale120 > 0) {
		bw = (w * s->scale120 + 60) / 120;         /* rounded half away from zero, as the protocol says */
		bh = (h * s->scale120 + 60) / 120;
		wp_viewport_set_destination(s->viewport, w, h);
	} else {
		int scale = s->preferred_scale > 0 ? s->preferred_scale : s->output && s->output->scale > 0 ? s->output->scale : 1;
		bw = w * scale;
		bh = h * scale;
		wl_surface_set_buffer_scale(s->surface, scale);
	}
	struct wl_region *opaque = wl_compositor_create_region(W.compositor);
	wl_region_add(opaque, 0, 0, w, h);
	wl_surface_set_opaque_region(s->surface, opaque);
	wl_region_destroy(opaque);
	if (!s->render) {
		char why[256];
		s->render = render_surface_create(s->surface, bw, bh, why, sizeof why);
		if (!s->render) {
			if (!W.drawn)
				hand_over(why, 69, NULL);
			fprintf(stderr, "syncrain: a screen cannot be drawn: %s\n", why);
			return;
		}
	} else if (bw != s->buffer_width || bh != s->buffer_height) {
		render_surface_resize(s->render, bw, bh);
	}
	s->buffer_width = bw;
	s->buffer_height = bh;
}

static void layer_configure(void *data, struct zwlr_layer_surface_v1 *layer, uint32_t serial, uint32_t w,
                            uint32_t h)
{
	struct screen *s = data;
	zwlr_layer_surface_v1_ack_configure(layer, serial);
	if (w == 0 || h == 0) {                        /* anchored to every edge, so the compositor says */
		int scale = s->output && s->output->scale > 0 ? s->output->scale : 1;
		w = s->output && s->output->mode_width > 0 ? (uint32_t)(s->output->mode_width / scale) : 640;
		h = s->output && s->output->mode_height > 0 ? (uint32_t)(s->output->mode_height / scale) : 360;
	}
	bool changed = !s->configured || (int)w != s->width || (int)h != s->height;
	s->width = (int)w;
	s->height = (int)h;
	s->configured = true;
	if (changed) {
		apply_size(s);
		announce();
		queue(s);
	}
}

static void destroy_screen(struct screen *s);

static void layer_closed(void *data, struct zwlr_layer_surface_v1 *layer)
{
	(void)layer;
	destroy_screen(data);                          /* until the monitors change, as gtk4-layer-shell leaves it */
}

static const struct zwlr_layer_surface_v1_listener layer_listener = { layer_configure, layer_closed };

static void preferred_scale(void *data, struct wp_fractional_scale_v1 *fractional, uint32_t scale)
{
	(void)fractional;
	struct screen *s = data;
	if ((int)scale == s->scale120)
		return;
	s->scale120 = (int)scale;
	if (s->configured) {
		apply_size(s);
		queue(s);
	}
}

static const struct wp_fractional_scale_v1_listener fractional_listener = { preferred_scale };

static void surface_enter(void *data, struct wl_surface *surface, struct wl_output *output)
{
	(void)data, (void)surface, (void)output;
}

static void surface_leave(void *data, struct wl_surface *surface, struct wl_output *output)
{
	(void)data, (void)surface, (void)output;
}

#ifdef WL_SURFACE_PREFERRED_BUFFER_SCALE_SINCE_VERSION
static void surface_preferred_scale(void *data, struct wl_surface *surface, int32_t factor)
{
	(void)surface;
	struct screen *s = data;
	if (factor == s->preferred_scale)
		return;
	s->preferred_scale = factor;
	if (s->configured && !(s->viewport && s->scale120 > 0)) {
		apply_size(s);
		queue(s);
	}
}

static void surface_preferred_transform(void *data, struct wl_surface *surface, uint32_t transform)
{
	(void)data, (void)surface, (void)transform;
}

static const struct wl_surface_listener surface_listener = {
	surface_enter, surface_leave, surface_preferred_scale, surface_preferred_transform,
};
#else
static const struct wl_surface_listener surface_listener = { surface_enter, surface_leave };
#endif

static void create_screen(struct output *o)
{
	struct screen *s = calloc(1, sizeof *s);
	if (!s)
		return;
	W.settled = false;                             /* settle again once the new screen has drawn */
	s->output = o;
	o->screen = s;
	pacer_init(&s->pacer, opt.fps);
	s->surface = wl_compositor_create_surface(W.compositor);
	wl_surface_add_listener(s->surface, &surface_listener, s);
	struct wl_region *none = wl_compositor_create_region(W.compositor);
	wl_surface_set_input_region(s->surface, none);     /* clicks fall through to the desktop */
	wl_region_destroy(none);
	if (W.fractional && W.viewporter) {
		s->fractional = wp_fractional_scale_manager_v1_get_fractional_scale(W.fractional, s->surface);
		wp_fractional_scale_v1_add_listener(s->fractional, &fractional_listener, s);
		s->viewport = wp_viewporter_get_viewport(W.viewporter, s->surface);
	}
	s->layer = zwlr_layer_shell_v1_get_layer_surface(W.layer_shell, s->surface, o->wl,
	                                                 opt.bottom ? ZWLR_LAYER_SHELL_V1_LAYER_BOTTOM
	                                                            : ZWLR_LAYER_SHELL_V1_LAYER_BACKGROUND,
	                                                 "syncrain");
	zwlr_layer_surface_v1_set_anchor(s->layer, ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP | ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
	                                           ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT | ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT);
	zwlr_layer_surface_v1_set_exclusive_zone(s->layer, -1);
	zwlr_layer_surface_v1_set_keyboard_interactivity(s->layer, ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE);
	zwlr_layer_surface_v1_set_size(s->layer, 0, 0);
	zwlr_layer_surface_v1_add_listener(s->layer, &layer_listener, s);
	wl_surface_commit(s->surface);
	wl_list_insert(W.screens.prev, &s->link);
	if (W.watch)
		set_hidden(s, watch_hidden(W.watch, o->name));
}

static void destroy_screen(struct screen *s)
{
	if (!s)
		return;
	W.settled = false;
	wl_list_remove(&s->link);
	if (s->output)
		s->output->screen = NULL;
	for (int i = 0; i < HISTORY; i++)
		if (s->history[i].feedback)
			wp_presentation_feedback_destroy(s->history[i].feedback);
	if (s->frame_callback)
		wl_callback_destroy(s->frame_callback);
	render_surface_destroy(s->render);
	if (s->viewport)
		wp_viewport_destroy(s->viewport);
	if (s->fractional)
		wp_fractional_scale_v1_destroy(s->fractional);
	zwlr_layer_surface_v1_destroy(s->layer);
	wl_surface_destroy(s->surface);
	free(s->shown);
	free(s);
}

/* ------------------------------------------------------------------ outputs and globals */

static void output_geometry(void *data, struct wl_output *o, int32_t x, int32_t y, int32_t pw, int32_t ph,
                            int32_t subpixel, const char *make, const char *model, int32_t transform)
{
	(void)data, (void)o, (void)x, (void)y, (void)pw, (void)ph, (void)subpixel, (void)make, (void)model;
	(void)transform;
}

static void output_mode(void *data, struct wl_output *wl, uint32_t flags, int32_t w, int32_t h, int32_t refresh)
{
	(void)wl;
	struct output *o = data;
	if (flags & WL_OUTPUT_MODE_CURRENT) {
		o->mode_width = w;
		o->mode_height = h;
		o->refresh_mhz = refresh;
	}
}

static void output_done(void *data, struct wl_output *wl)
{
	(void)wl;
	struct output *o = data;
	o->done = true;
	if (W.ready && !o->screen)
		create_screen(o);
}

static void output_scale(void *data, struct wl_output *wl, int32_t factor)
{
	(void)wl;
	((struct output *)data)->scale = factor;
}

static void output_name(void *data, struct wl_output *wl, const char *name)
{
	(void)wl;
	struct output *o = data;
	snprintf(o->name, sizeof o->name, "%s", name);
}

static void output_description(void *data, struct wl_output *wl, const char *description)
{
	(void)data, (void)wl, (void)description;
}

static const struct wl_output_listener output_listener = {
	output_geometry, output_mode, output_done, output_scale, output_name, output_description,
};

static uint32_t at_most(uint32_t offered, uint32_t wanted)
{
	return offered < wanted ? offered : wanted;
}

static void registry_global(void *data, struct wl_registry *registry, uint32_t name, const char *interface,
                            uint32_t version)
{
	(void)data;
	if (strcmp(interface, wl_compositor_interface.name) == 0) {
		W.compositor_version = at_most(version, 6);
		W.compositor = wl_registry_bind(registry, name, &wl_compositor_interface, W.compositor_version);
	} else if (strcmp(interface, zwlr_layer_shell_v1_interface.name) == 0) {
		W.layer_shell_version = at_most(version, 4);
		W.layer_shell = wl_registry_bind(registry, name, &zwlr_layer_shell_v1_interface, W.layer_shell_version);
	} else if (strcmp(interface, wp_presentation_interface.name) == 0) {
		W.presentation = wl_registry_bind(registry, name, &wp_presentation_interface, 1);
	} else if (strcmp(interface, wp_viewporter_interface.name) == 0) {
		W.viewporter = wl_registry_bind(registry, name, &wp_viewporter_interface, 1);
	} else if (strcmp(interface, wp_fractional_scale_manager_v1_interface.name) == 0) {
		W.fractional = wl_registry_bind(registry, name, &wp_fractional_scale_manager_v1_interface, 1);
	} else if (strcmp(interface, wl_output_interface.name) == 0 && version >= 2) {
		struct output *o = calloc(1, sizeof *o);
		if (!o)
			return;
		o->global = name;
		o->scale = 1;
		o->wl = wl_registry_bind(registry, name, &wl_output_interface, at_most(version, 4));
		wl_output_add_listener(o->wl, &output_listener, o);
		wl_list_insert(W.outputs.prev, &o->link);
	}
}

static void registry_remove(void *data, struct wl_registry *registry, uint32_t name)
{
	(void)data, (void)registry;
	struct output *o, *next;
	wl_list_for_each_safe(o, next, &W.outputs, link) {
		if (o->global != name)
			continue;
		destroy_screen(o->screen);
		if (wl_output_get_version(o->wl) >= 3)
			wl_output_release(o->wl);
		else
			wl_output_destroy(o->wl);
		wl_list_remove(&o->link);
		free(o);
	}
}

static const struct wl_registry_listener registry_listener = { registry_global, registry_remove };

/* ------------------------------------------------------------------ the loop */

static void watch_check(void)
{
	W.watch_check = 0;
	if (!W.watch || watch_answered(W.watch))
		return;
	if (!W.watch_retried) {                        /* app.py, App._watch_check */
		W.watch_retried = true;
		watch_retry(W.watch);
		watch_dispatch(W.watch);
		W.watch_check = monotonic_us() + 1500000;
		return;
	}
	printf("syncrain: KWin loaded the script but it reported nothing (KWin 5?); "
	       "drawing goes on under covering windows\n");
	watch_free(W.watch);
	W.watch = NULL;
	update_hidden();
}

static void run_timers(int64_t now)
{
	struct screen *s;
	wl_list_for_each(s, &W.screens, link) {
		if (s->due && s->due <= now) {
			s->due = 0;
			if (!s->hidden)                        /* RainArea._on_due */
				queue(s);
		}
	}
	if (W.watch_check && W.watch_check <= now)
		watch_check();
}

static int64_t next_deadline(void)
{
	int64_t next = 0;
	struct screen *s;
	wl_list_for_each(s, &W.screens, link)
		if (s->due && (!next || s->due < next))
			next = s->due;
	if (W.watch_check && (!next || W.watch_check < next))
		next = W.watch_check;
	return next;
}

static void draw_ready(void)
{
	struct screen *s, *next;
	wl_list_for_each_safe(s, next, &W.screens, link) {
		if (s->draw_now) {
			s->draw_now = false;
			if (s->render && s->configured)
				draw(s);
		}
	}
}

static bool any_ready(void)
{
	struct screen *s;
	wl_list_for_each(s, &W.screens, link)
		if (s->draw_now)
			return true;
	return false;
}

/* The compositor went away, or said this client did something wrong: as GTK does then, the wallpaper
 * stops with status 1, and its service (Restart=on-failure) starts it again. */
static void lose_compositor(const char *what)
{
	static char why[200];
	int error = wl_display_get_error(W.display);
	const struct wl_interface *interface = NULL;
	uint32_t id = 0;
	if (error == EPROTO) {
		uint32_t code = wl_display_get_protocol_error(W.display, &interface, &id);
		snprintf(why, sizeof why, "%s: protocol error %u on %s@%u", what, code,
		         interface ? interface->name : "an unknown object", id);
	} else {
		snprintf(why, sizeof why, "%s (%s)", what, strerror(error ? error : errno ? errno : EPIPE));
	}
	W.lost = why;
}

static void loop(void)
{
	while (W.running) {
		run_timers(monotonic_us());
		draw_ready();
		if (!W.running)
			return;
		while (wl_display_prepare_read(W.display) != 0)
			if (wl_display_dispatch_pending(W.display) < 0) {
				lose_compositor("the connection to the compositor is gone");
				return;
			}
		bool want_out = wl_display_flush(W.display) < 0 && errno == EAGAIN;
		struct pollfd fds[3] = {
			{ .fd = wl_display_get_fd(W.display), .events = POLLIN | (want_out ? POLLOUT : 0) },
			{ .fd = W.signal_fd, .events = POLLIN },
			{ .fd = watch_fd(W.watch), .events = POLLIN },
		};
		struct timespec wait, *timeout = NULL;
		if (any_ready()) {
			wait = (struct timespec){ 0, 0 };
			timeout = &wait;
		} else {
			int64_t deadline = next_deadline();
			if (deadline) {
				int64_t us = deadline - monotonic_us();
				us = us > 0 ? us : 0;
				wait = (struct timespec){ (time_t)(us / 1000000), (long)(us % 1000000) * 1000 };
				timeout = &wait;
			}
		}
		int n = ppoll(fds, 3, timeout, NULL);
		if (n < 0 && errno != EINTR) {
			wl_display_cancel_read(W.display);
			lose_compositor("waiting for the compositor failed");
			return;
		}
		/* A hung-up socket can say so without POLLIN; reading then reports it, rather than polling
		 * the same hang-up again and again. */
		if (n > 0 && (fds[0].revents & (POLLIN | POLLHUP | POLLERR))) {
			if (wl_display_read_events(W.display) < 0) {
				lose_compositor("the connection to the compositor is gone");
				return;
			}
		} else {
			wl_display_cancel_read(W.display);
		}
		if (wl_display_dispatch_pending(W.display) < 0) {
			lose_compositor("the connection to the compositor is gone");
			return;
		}
		if (n > 0 && (fds[1].revents & POLLIN)) {
			struct signalfd_siginfo info;
			if (read(W.signal_fd, &info, sizeof info) > 0)
				W.running = false;
		}
		if (n > 0 && fds[2].fd >= 0 && (fds[2].revents & (POLLIN | POLLHUP | POLLERR)))
			watch_dispatch(W.watch);
	}
}

/* ------------------------------------------------------------------ probe */

static void probe(void)
{
	printf("compositor: layer-shell %s, presentation-time %s, fractional scale %s, viewporter %s\n",
	       W.layer_shell ? "yes" : "no", W.presentation ? "yes" : "no", W.fractional ? "yes" : "no",
	       W.viewporter ? "yes" : "no");
	struct output *o;
	wl_list_for_each(o, &W.outputs, link)
		printf("screen %s: %dx%d, %.2f Hz, scale %d\n", o->name[0] ? o->name : "(unnamed)", o->mode_width,
		       o->mode_height, o->refresh_mhz / 1000.0, o->scale);
	if (!W.layer_shell) {
		printf("verdict: no layer-shell, so the GTK host would say why\n");
		exit(2);
	}
	char why[1024];
	if (!render_init(W.display, &W.scene, why, sizeof why)) {
		printf("verdict: %s\n", why);
		exit(69);
	}
	struct gl_info info;
	render_info(&info);
	printf("%s %d.%d on %s (%s), the shaders compiled\n", info.es ? "OpenGL ES" : "OpenGL", info.major, info.minor,
	       info.renderer, info.egl);
	printf("verdict: the native wallpaper can draw here\n");
	render_shutdown();
	exit(0);
}

/* ------------------------------------------------------------------ main */

int main(int argc, char **argv)
{
	setvbuf(stdout, NULL, _IOLBF, 0);
	parse_options(argc, argv);
	/* Few threads allocate here (the driver's); two arenas keep what they free from spreading out. */
	mallopt(M_ARENA_MAX, 2);
	char why[1024];
	if (!scene_load(&W.scene, opt.scene_fd, why, sizeof why)) {
		fprintf(stderr, "syncrain: the native wallpaper cannot read its scene: %s\n", why);
		return 70;
	}
	close(opt.scene_fd);
	signal(SIGPIPE, SIG_IGN);
	sigset_t mask;
	sigemptyset(&mask);
	sigaddset(&mask, SIGINT);
	sigaddset(&mask, SIGTERM);
	sigaddset(&mask, SIGHUP);
	sigprocmask(SIG_BLOCK, &mask, &W.old_mask);
	W.signal_fd = signalfd(-1, &mask, SFD_CLOEXEC | SFD_NONBLOCK);
	wl_list_init(&W.outputs);
	wl_list_init(&W.screens);
	W.display = wl_display_connect(NULL);
	if (!W.display)
		hand_over("no Wayland display", 1, "no display (run it inside your desktop session)");
	W.registry = wl_display_get_registry(W.display);
	wl_registry_add_listener(W.registry, &registry_listener, NULL);
	if (wl_display_roundtrip(W.display) < 0 || wl_display_roundtrip(W.display) < 0)
		hand_over("the compositor went away", 1, "no display (run it inside your desktop session)");
	if (opt.probe)
		probe();
	if (!W.compositor || !W.layer_shell)
		hand_over("no layer-shell", 2, "this Wayland compositor has no wlr-layer-shell support (GNOME?). "
		                               "Use --window, or the web version in web/index.html.");
	if (!render_init(W.display, &W.scene, why, sizeof why))
		hand_over(why, 69, NULL);
	scene_unmap(&W.scene);                         /* the pixels are on the card now */
	malloc_trim(0);
	W.ready = true;
	W.running = true;
	struct output *o;
	wl_list_for_each(o, &W.outputs, link)
		if (o->done && !o->screen)
			create_screen(o);
	loop();
	if (W.watch)                                   /* the script leaves KWin with the wallpaper */
		watch_free(W.watch);
	if (W.lost) {
		/* What is left of the connection and the driver's state goes with the process. */
		fprintf(stderr, "syncrain: %s; the wallpaper stops with status 1, so that it is started again\n", W.lost);
		return 1;
	}
	struct screen *s, *next;
	wl_list_for_each_safe(s, next, &W.screens, link)
		destroy_screen(s);
	render_shutdown();
	wl_display_flush(W.display);
	wl_display_disconnect(W.display);
	return 0;
}
