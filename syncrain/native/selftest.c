/* `syncrain-wallpaper --selftest geometry|time|pacer`: the arithmetic of timing.c on lines read from
 * standard input, printed exactly (hexadecimal floats), for tests/native/ to compare with the Python
 * host's own results, value for value. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "syncrain.h"

int selftest(const char *what);

/* "w h cols keep size drift x0 y0 x1 y1 bg_w bg_h" -> the per-size values a frame sets */
static int geometry_lines(void)
{
	char line[1024], keep[16];
	while (fgets(line, sizeof line, stdin)) {
		struct scene s = { 0 };
		int w, h;
		double b[4];
		if (sscanf(line, "%d %d %d %15s %lf %lf %lf %lf %lf %lf %d %d", &w, &h, &s.cols, keep, &s.logo_size, &s.drift,
		           &b[0], &b[1], &b[2], &b[3], &s.bg_width, &s.bg_height) != 12)
			return 2;
		s.keep = strcmp(keep, "logo") == 0 ? KEEP_LOGO : strcmp(keep, "mask") == 0 ? KEEP_MASK : KEEP_NONE;
		memcpy(s.mask_bbox, b, sizeof b);
		struct geometry g;
		geometry_compute(&g, &s, w, h);
		printf("%d %d %d %d %a %a %a %a %a %a %a %a %a %a %a %a %a %a %a\n", g.cols, g.rows, g.qw, g.qh, g.cell, g.col0,
		       g.keep[0], g.keep[1], g.keep[2], g.keep[3], g.bg_scale[0], g.bg_scale[1], g.bg_offset[0], g.bg_offset[1],
		       g.sigma, g.step_h[0], g.step_h[1], g.step_v[0], g.step_v[1]);
	}
	return 0;
}

/* "unix epoch0" -> "seconds fraction" */
static int time_lines(void)
{
	char line[256];
	while (fgets(line, sizeof line, stdin)) {
		double unix_seconds;
		long long epoch0;
		if (sscanf(line, "%lf %lld", &unix_seconds, &epoch0) != 2)
			return 2;
		uint32_t sec;
		float frac;
		split_time(unix_seconds, epoch0, &sec, &frac);
		printf("%u %a\n", sec, (double)frac);
	}
	return 0;
}

static void print_target(bool has, double value)
{
	if (has)
		printf(" %a", value);
	else
		printf(" none");
}

/* new FPS | plan NOW REFRESH VBLANK | shown TARGET PRESENTED REFRESH | lead R | step R | restart |
 * spacing R P... | steady D... */
static int pacer_lines(void)
{
	struct pacer p;
	pacer_init(&p, 30.0);
	char line[65536];
	while (fgets(line, sizeof line, stdin)) {
		char *save = NULL, *cmd = strtok_r(line, " \n", &save);
		double v[4096];
		int n = 0;
		for (char *t; n < 4096 && (t = strtok_r(NULL, " \n", &save)); )
			v[n++] = strtod(t, NULL);
		if (!cmd)
			continue;
		if (strcmp(cmd, "new") == 0 && n == 1) {
			pacer_init(&p, v[0]);
			printf("ok\n");
		} else if (strcmp(cmd, "plan") == 0 && n == 3) {
			double delay = pacer_plan(&p, v[0], v[1], v[2]);
			printf("%a", delay);
			print_target(p.has_target, p.target);
			printf("\n");
		} else if (strcmp(cmd, "shown") == 0 && n == 3) {
			pacer_shown(&p, v[0], v[1], v[2]);
			printf("%a", p.shift);
			print_target(p.has_settled, p.settled_after);
			printf("\n");
		} else if (strcmp(cmd, "lead") == 0 && n == 1) {
			printf("%a\n", pacer_lead(&p, v[0]));
		} else if (strcmp(cmd, "step") == 0 && n == 1) {
			printf("%d\n", pacer_step(&p, v[0]));
		} else if (strcmp(cmd, "restart") == 0) {
			pacer_restart(&p);
			printf("ok\n");
		} else if (strcmp(cmd, "spacing") == 0 && n >= 1) {
			static int steps[4096];
			int k = spacing(v + 1, n - 1, v[0], steps);
			for (int i = 0; i < k; i++)
				printf("%s%d", i ? " " : "", steps[i]);
			printf("\n");
		} else if (strcmp(cmd, "steady") == 0) {
			printf("%a\n", steady(v, n));
		} else {
			return 2;
		}
	}
	return 0;
}

int selftest(const char *what)
{
	setvbuf(stdout, NULL, _IOLBF, 0);
	if (strcmp(what, "geometry") == 0)
		return geometry_lines();
	if (strcmp(what, "time") == 0)
		return time_lines();
	if (strcmp(what, "pacer") == 0)
		return pacer_lines();
	fprintf(stderr, "syncrain-wallpaper: no selftest called %s\n", what);
	return 2;
}
