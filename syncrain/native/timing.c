/* What a frame computes on the processor: the viewport's geometry, the clock, the frame schedule.
 *
 * Each function is a line-for-line port of the Python host (renderer.py Targets and _keep_rect,
 * engine.py split_time and cover_fit, pacing.py), operation for operation in the same order, so
 * that the doubles come out bit for bit the same and the same moment draws the same frame on either
 * host. Python's own float floor division and round() are ported too, since C's differ at the edges.
 */
#define _GNU_SOURCE
#include <math.h>
#include <stdlib.h>
#include <time.h>

#include "syncrain.h"

/* Objects/floatobject.c, _float_div_mod: fmod, then the quotient snapped to the nearest integer. */
double py_floordiv(double vx, double wx)
{
	double mod = fmod(vx, wx);
	double div = (vx - mod) / wx;
	if (mod != 0.0) {
		if ((wx < 0) != (mod < 0)) {
			mod += wx;
			div -= 1.0;
		}
	}
	if (div != 0.0) {
		double floordiv = floor(div);
		if (div - floordiv > 0.5)
			floordiv += 1.0;
		return floordiv;
	}
	return copysign(0.0, vx / wx);
}

/* round() of a float in Python: to the nearest integer, halves to the even one (rint's default). */
double py_round(double x)
{
	return rint(x);
}

/* engine.cover_fit: the image covers the screen without distortion. */
static void cover_fit(int sw, int sh, int iw, int ih, double scale[2], double offset[2])
{
	double sa = (double)sw / sh, ia = (double)iw / ih;
	if (sa > ia) {
		double k = ia / sa;
		scale[0] = 1.0, scale[1] = k;
		offset[0] = 0.0, offset[1] = 0.5 - 0.5 * k;
	} else {
		double k = sa / ia;
		scale[0] = k, scale[1] = 1.0;
		offset[0] = 0.5 - 0.5 * k, offset[1] = 0.0;
	}
}

void geometry_compute(struct geometry *g, const struct scene *scene, int w, int h)
{
	int cols = scene->cols;
	double a = (double)w / cols;
	double cell = 12.0 > a ? 12.0 : a;                 /* max(w / cols, 12.0) */
	g->width = w, g->height = h, g->cols = cols;
	g->cell = cell;
	g->col0 = (cols - w / cell) / 2;
	g->rows = (int)(-py_floordiv(-(double)h, cell));   /* int(-(-h // cell)) */
	int qw = (int)py_round(w / 4.0), qh = (int)py_round(h / 4.0);
	g->qw = 16 > qw ? 16 : qw;
	g->qh = 9 > qh ? 9 : qh;
	if (scene->bg_width > 0) {
		cover_fit(w, h, scene->bg_width, scene->bg_height, g->bg_scale, g->bg_offset);
	} else {
		g->bg_scale[0] = g->bg_scale[1] = 1.0;
		g->bg_offset[0] = g->bg_offset[1] = 0.0;
	}
	if (scene->keep == KEEP_LOGO) {                    /* the logo's square box, widened by the drift */
		double half = scene->logo_size * h / 2 / cell + scene->drift * h / cell + 1;
		double rc = h / 2.0 / cell;
		g->keep[0] = cols / 2.0 - half, g->keep[1] = rc - half;
		g->keep[2] = cols / 2.0 + half, g->keep[3] = rc + half;
	} else if (scene->keep == KEEP_MASK) {             /* image uv -> screen px -> cells */
		const double *b = scene->mask_bbox, *s = g->bg_scale, *o = g->bg_offset;
		double sx0 = (b[0] - o[0]) / s[0] * w, sy0 = (b[1] - o[1]) / s[1] * h;
		double sx1 = (b[2] - o[0]) / s[0] * w, sy1 = (b[3] - o[1]) / s[1] * h;
		double m = 1 + scene->drift * h / cell * 2;
		g->keep[0] = g->col0 + sx0 / cell - m, g->keep[1] = sy0 / cell - m;
		g->keep[2] = g->col0 + sx1 / cell + m, g->keep[3] = sy1 / cell + m;
	} else {
		g->keep[0] = g->keep[1] = g->keep[2] = g->keep[3] = -1;
	}
	g->sigma = 0.2 * cell / 4;
	g->step_h[0] = 1.0 / g->qw, g->step_h[1] = 0.0;
	g->step_v[0] = 0.0, g->step_v[1] = 1.0 / g->qh;
}

/* engine.split_time: whole seconds since epoch0 as uint32 and the fraction, on a millisecond grid. */
void split_time(double unix_seconds, long long epoch0, uint32_t *seconds, float *fraction)
{
	long long ms = (long long)floor(unix_seconds * 1000.0 + 1e-6);
	long long whole = ms / 1000;
	if (ms % 1000 < 0)
		whole -= 1;                                    /* Python's // floors */
	*seconds = (uint32_t)((unsigned long long)(whole - epoch0) & 0xFFFFFFFFull);
	*fraction = (float)((double)(ms - whole * 1000) / 1000.0);
}

int64_t monotonic_us(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (int64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000;
}

double monotonic_s(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (double)((int64_t)ts.tv_sec * 1000000000 + ts.tv_nsec) / 1e9;
}

/* time.time(): nanoseconds since 1970 as a double, divided once. */
double realtime_s(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_REALTIME, &ts);
	return (double)((int64_t)ts.tv_sec * 1000000000 + ts.tv_nsec) / 1e9;
}

/* ------------------------------------------------------------------ pacing.py */

#define LEAD_US 6000.0
#define GRACE 0.05
#define MAX_MISS 2
#define NUDGE_US 500.0
#define MIN_LEAD_US 2000.0

void pacer_init(struct pacer *p, double fps)
{
	p->period = 1e6 / (fps > 1.0 ? fps : 1.0);
	p->has_target = false;
	p->target = 0;
	p->shift = 0.0;
	p->has_settled = false;
	p->settled_after = 0;
}

int pacer_step(const struct pacer *p, double refresh)
{
	int n = (int)ceil(p->period / refresh - GRACE);
	return n > 1 ? n : 1;
}

double pacer_lead(const struct pacer *p, double refresh)
{
	double lead = refresh / 2 + LEAD_US + p->shift;
	if (!(lead > MIN_LEAD_US))
		lead = MIN_LEAD_US;
	double most = 2 * refresh + LEAD_US;
	return lead < most ? lead : most;
}

void pacer_shown(struct pacer *p, double target, double presented, double refresh)
{
	if (refresh <= 0 || (p->has_settled && target <= p->settled_after))
		return;
	long off = (long)py_round((presented - target) / refresh);
	if (off == 0 || labs(off) > MAX_MISS)
		return;
	double base = refresh / 2 + LEAD_US;
	double moved = p->shift + (off > 0 ? NUDGE_US : -NUDGE_US);
	double least = MIN_LEAD_US - base, most = 1.5 * refresh;
	double shift = moved > least ? moved : least;     /* min(max(moved, least), most) */
	p->shift = shift < most ? shift : most;
	p->has_settled = p->has_target;
	p->settled_after = p->target;
}

/* Microseconds until the next frame is asked for; sets p->has_target and p->target. */
double pacer_plan(struct pacer *p, double now, double refresh, double vblank)
{
	if (refresh <= 0 || vblank <= 0) {
		p->has_target = false;
		return p->period;
	}
	double lead = pacer_lead(p, refresh);
	double earliest = vblank + ceil((now + lead - vblank) / refresh) * refresh;
	bool has = p->has_target;
	double target = 0;
	if (has) {
		target = p->target + pacer_step(p, refresh) * refresh;
		target = vblank + py_round((target - vblank) / refresh) * refresh;
	}
	if (!has || target < earliest)
		target = earliest;
	p->has_target = true;
	p->target = target;
	return target - lead - now;
}

void pacer_restart(struct pacer *p)
{
	p->has_target = false;
}

/* pacing.spacing: refreshes between consecutive presentation times. */
int spacing(const double *presented, int n, double refresh, int *steps)
{
	if (refresh <= 0)
		return 0;
	int k = 0;
	for (int i = 1; i < n; i++)
		steps[k++] = (int)py_round((presented[i] - presented[i - 1]) / refresh);
	return k;
}

static int compare_doubles(const void *a, const void *b)
{
	double x = *(const double *)a, y = *(const double *)b;
	return (x > y) - (x < y);
}

#define STEADY_US 2000.0

/* pacing.steady: the share of frames shown within STEADY_US of the usual delay. Sorts in place. */
double steady(const double *delays, int n)
{
	if (n <= 0)
		return 0.0;
	double *sorted = malloc(sizeof(double) * (size_t)n);
	if (!sorted)
		return 0.0;
	for (int i = 0; i < n; i++)
		sorted[i] = delays[i];
	qsort(sorted, (size_t)n, sizeof(double), compare_doubles);
	double usual = sorted[n / 2];
	free(sorted);
	int within = 0;
	for (int i = 0; i < n; i++)
		within += fabs(delays[i] - usual) <= STEADY_US;
	return (double)within / n;
}
