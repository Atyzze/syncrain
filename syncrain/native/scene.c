/* The scene the Python launcher hands over (syncrain/native.py, `scene_bytes`): a memfd holding a
 * text header, line by line up to "end", and then the shader sources and pixels the header points
 * into. Offsets count from the first byte after the "end" line.
 *
 *   syncrain-scene-2
 *   describe syncrain build 8 (stream 48e6bf9c)
 *   epoch0 1704067200
 *   cols 64
 *   keep logo <size> <drift> | keep mask <x0> <y0> <x1> <y1> <drift> | keep none
 *   bg <width> <height>                          (only with a background image)
 *   lock-rest <seconds>                          (only when set: the lock screen's rest; the wallpaper ignores it)
 *   shader <vert|state|field|glyphs|blur|composite> <offset> <length>
 *   texture <atlas|table|words|logo|bg|mask> <width> <height> <nearest|linear|mip> <offset> <length>
 *   uniform <program> <name> <i|ui|f|f2|f3|f4|f4v> <values...>
 *   kwin-script <offset> <length>
 *   fallback <offset> <length>                   (NUL-separated arguments)
 *   end
 */
#define _GNU_SOURCE
#include <errno.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include "syncrain.h"

#define CONTRACT "syncrain-scene-2"

static const char *const PROGRAMS[PROGRAM_COUNT] = { "state", "field", "glyphs", "blur", "composite" };
static const char *const TEXTURES[TEXTURE_COUNT] = { "atlas", "table", "words", "logo", "bg", "mask" };
static const char *const FILTERS[] = { "nearest", "linear", "mip" };

const char *scene_program_name(enum program program)
{
	return PROGRAMS[program];
}

static int lookup(const char *word, const char *const *names, int count)
{
	for (int i = 0; i < count; i++)
		if (strcmp(word, names[i]) == 0)
			return i;
	return -1;
}

static bool span(const char *a, const char *b, const char *data, size_t data_size, struct blob *out)
{
	char *end;
	errno = 0;
	unsigned long long offset = strtoull(a, &end, 10);
	if (errno || *end)
		return false;
	unsigned long long length = strtoull(b, &end, 10);
	if (errno || *end || offset > data_size || length > data_size - offset)
		return false;
	out->data = data + offset;
	out->size = (size_t)length;
	return true;
}

static char *copy_blob(struct blob b)
{
	char *s = malloc(b.size + 1);
	if (s) {
		memcpy(s, b.data, b.size);
		s[b.size] = '\0';
	}
	return s;
}

/* NUL-separated arguments to a NULL-terminated argv, in one allocation. */
static char **split_arguments(struct blob b)
{
	size_t n = 0;
	for (size_t i = 0; i < b.size; i++)
		n += b.data[i] == '\0';
	if (b.size == 0 || b.data[b.size - 1] != '\0')
		return NULL;
	char **argv = malloc((n + 1) * sizeof(char *) + b.size);
	if (!argv)
		return NULL;
	char *text = (char *)(argv + n + 1);
	memcpy(text, b.data, b.size);
	size_t k = 0;
	for (size_t i = 0; i < b.size; i += strlen(text + i) + 1)
		argv[k++] = text + i;
	argv[k] = NULL;
	return argv;
}

#define FAIL(...) do { snprintf(why, why_size, __VA_ARGS__); goto fail; } while (0)
#define MAX_WORDS (UNIFORM_VALUES + 8)

/* A whole number or a finite real, all of the word and nothing else ("0,44" or "64junk" is no
 * number): what Python wrote, or the scene is refused. */
static bool whole(const char *s, long long lo, long long hi, long long *out)
{
	char *end;
	errno = 0;
	long long v = strtoll(s, &end, 10);
	if (end == s || *end || errno || v < lo || v > hi)
		return false;
	*out = v;
	return true;
}

static bool real(const char *s, double *out)
{
	char *end;
	double v = c_strtod(s, &end);
	if (end == s || *end || !isfinite(v))
		return false;
	*out = v;
	return true;
}

bool scene_load(struct scene *scene, int fd, char *why, size_t why_size)
{
	memset(scene, 0, sizeof *scene);
	struct stat st;
	if (fstat(fd, &st) != 0 || st.st_size <= 0)
		FAIL("the scene is empty");
	scene->map_size = (size_t)st.st_size;
	scene->map = mmap(NULL, scene->map_size, PROT_READ, MAP_PRIVATE, fd, 0);
	if (scene->map == MAP_FAILED) {
		scene->map = NULL;
		FAIL("the scene cannot be read: %s", strerror(errno));
	}
	const char *all = scene->map, *stop = all + scene->map_size;
	const char *end = NULL;
	for (const char *p = all; p < stop; ) {
		const char *nl = memchr(p, '\n', (size_t)(stop - p));
		if (!nl)
			break;
		if (nl - p == 3 && memcmp(p, "end", 3) == 0) {
			end = nl + 1;
			break;
		}
		p = nl + 1;
	}
	if (!end)
		FAIL("the scene has no end");
	const char *data = end;
	size_t data_size = (size_t)(stop - end);
	scene->keep = KEEP_NONE;
	bool shader[PROGRAM_COUNT + 1] = { false };
	int capacity = 0;
	char line[4096];
	bool first = true;
	bool seen_epoch = false, seen_cols = false, seen_keep = false, seen_bg = false;
	long long whole_value;
	for (const char *p = all; p < end - 4; ) {
		const char *nl = memchr(p, '\n', (size_t)(end - p));
		size_t len = (size_t)(nl - p);
		if (len >= sizeof line)
			FAIL("a scene line is too long");
		memcpy(line, p, len);
		line[len] = '\0';
		p = nl + 1;
		if (first) {
			if (strcmp(line, CONTRACT) != 0)
				FAIL("the scene is %.40s, this program reads %s", line, CONTRACT);
			first = false;
			continue;
		}
		if (strncmp(line, "describe ", 9) == 0) {
			snprintf(scene->describe, sizeof scene->describe, "%.150s", line + 9);
			continue;
		}
		char *word[MAX_WORDS];
		int n = 0;
		for (char *save = NULL, *t = strtok_r(line, " ", &save); t && n < MAX_WORDS; t = strtok_r(NULL, " ", &save))
			word[n++] = t;
		if (n == 0)
			continue;
		if (strcmp(word[0], "epoch0") == 0 && n == 2) {
			if (seen_epoch || !whole(word[1], 0, LLONG_MAX, &whole_value))
				FAIL("the scene's epoch0 is no number, or said twice");
			scene->epoch0 = whole_value;
			seen_epoch = true;
		} else if (strcmp(word[0], "cols") == 0 && n == 2) {
			if (seen_cols || !whole(word[1], 1, 4096, &whole_value))
				FAIL("the scene's columns are no number, or said twice");
			scene->cols = (int)whole_value;
			seen_cols = true;
		} else if (strcmp(word[0], "keep") == 0 && n >= 2) {
			if (seen_keep)
				FAIL("the scene says what to keep twice");
			seen_keep = true;
			if (strcmp(word[1], "logo") == 0 && n == 4) {
				scene->keep = KEEP_LOGO;
				if (!real(word[2], &scene->logo_size) || !real(word[3], &scene->drift))
					FAIL("a keep line whose numbers are no numbers");
			} else if (strcmp(word[1], "mask") == 0 && n == 7) {
				scene->keep = KEEP_MASK;
				for (int i = 0; i < 4; i++)
					if (!real(word[2 + i], &scene->mask_bbox[i]))
						FAIL("a keep line whose numbers are no numbers");
				if (!real(word[6], &scene->drift))
					FAIL("a keep line whose numbers are no numbers");
			} else if (strcmp(word[1], "none") == 0) {
				scene->keep = KEEP_NONE;
			} else {
				FAIL("a keep line the native wallpaper does not know");
			}
		} else if (strcmp(word[0], "bg") == 0 && n == 3) {
			long long w, h;
			if (seen_bg || !whole(word[1], 0, 65536, &w) || !whole(word[2], 0, 65536, &h))
				FAIL("the background's size is no number, or said twice");
			scene->bg_width = (int)w;
			scene->bg_height = (int)h;
			seen_bg = true;
		} else if (strcmp(word[0], "lock-rest") == 0 && n == 2) {
			double rest;
			if (scene->lock_rest > 0.0 || !real(word[1], &rest) || !(rest > 0.0 && rest <= 86400.0))
				FAIL("the lock screen's rest is no number of seconds, or said twice");
			scene->lock_rest = rest;
		} else if (strcmp(word[0], "shader") == 0 && n == 4) {
			struct blob b;
			if (!span(word[2], word[3], data, data_size, &b))
				FAIL("shader %s lies outside the scene", word[1]);
			if (strcmp(word[1], "vert") == 0) {
				if (shader[PROGRAM_COUNT])
					FAIL("the vertex shader twice");
				scene->vertex = b;
				shader[PROGRAM_COUNT] = true;
			} else {
				int k = lookup(word[1], PROGRAMS, PROGRAM_COUNT);
				if (k < 0 || shader[k])
					FAIL("an unknown shader, or one twice: %s", word[1]);
				scene->fragment[k] = b;
				shader[k] = true;
			}
		} else if (strcmp(word[0], "texture") == 0 && n == 7) {
			int k = lookup(word[1], TEXTURES, TEXTURE_COUNT);
			int f = lookup(word[4], FILTERS, 3);
			struct texture_source *t = k >= 0 ? &scene->texture[k] : NULL;
			long long w, h;
			if (!t || f < 0 || t->set)
				FAIL("an unknown texture line for %s, or one twice", word[1]);
			if (!whole(word[2], 1, 32768, &w) || !whole(word[3], 1, 32768, &h))
				FAIL("texture %s's size is no number", word[1]);
			t->width = (int)w;
			t->height = (int)h;
			t->filter = (enum filter)f;
			if (!span(word[5], word[6], data, data_size, &t->pixels) || t->width <= 0 || t->height <= 0 ||
			    t->pixels.size != (size_t)t->width * (size_t)t->height * 4)
				FAIL("texture %s does not hold %dx%d pixels", word[1], t->width, t->height);
			t->set = true;
		} else if (strcmp(word[0], "uniform") == 0 && n >= 5) {
			int k = lookup(word[1], PROGRAMS, PROGRAM_COUNT);
			if (k < 0 || n - 4 > UNIFORM_VALUES || strlen(word[2]) >= sizeof scene->uniform->name ||
			    strlen(word[3]) >= sizeof scene->uniform->kind)
				FAIL("a uniform line the native wallpaper does not know");
			if (scene->uniforms == capacity) {
				capacity = capacity ? capacity * 2 : 64;
				struct uniform_source *u = realloc(scene->uniform, sizeof *u * (size_t)capacity);
				if (!u)
					FAIL("out of memory");
				scene->uniform = u;
			}
			struct uniform_source *u = &scene->uniform[scene->uniforms++];
			memset(u, 0, sizeof *u);
			u->program = (enum program)k;
			strcpy(u->name, word[2]);
			strcpy(u->kind, word[3]);
			u->count = n - 4;
			bool integer = strcmp(u->kind, "i") == 0 || strcmp(u->kind, "ui") == 0;
			for (int i = 0; i < u->count; i++) {
				if (integer ? !whole(word[4 + i], LLONG_MIN, LLONG_MAX, &u->integer[i])
				            : !real(word[4 + i], &u->value[i]))
					FAIL("uniform %s's value is no number: %.40s", u->name, word[4 + i]);
				if (integer)
					u->value[i] = (double)u->integer[i];
			}
		} else if (strcmp(word[0], "kwin-script") == 0 && n == 3) {
			struct blob b;
			if (scene->kwin_script)
				FAIL("the KWin script twice");
			if (!span(word[1], word[2], data, data_size, &b) || !(scene->kwin_script = copy_blob(b)))
				FAIL("the KWin script lies outside the scene");
		} else if (strcmp(word[0], "fallback") == 0 && n == 3) {
			struct blob b;
			if (scene->fallback)
				FAIL("the fallback command twice");
			if (!span(word[1], word[2], data, data_size, &b) || !(scene->fallback = split_arguments(b)))
				FAIL("the fallback command lies outside the scene");
		} else {
			FAIL("a scene line the native wallpaper does not know: %.40s", word[0]);
		}
	}
	if (first)
		FAIL("the scene names no contract");
	if (!scene->describe[0] || scene->cols <= 0)
		FAIL("the scene names no build or columns");
	for (int i = 0; i <= PROGRAM_COUNT; i++)
		if (!shader[i])
			FAIL("the scene lacks the %s shader", i < PROGRAM_COUNT ? PROGRAMS[i] : "vertex");
	for (int i = 0; i < TEXTURE_COUNT; i++)
		if (!scene->texture[i].set)
			FAIL("the scene lacks the %s texture", TEXTURES[i]);
	if (!scene->kwin_script)
		FAIL("the scene lacks the KWin script");
	return true;
fail:
	scene_unmap(scene);
	free(scene->kwin_script);
	free(scene->fallback);                /* one allocation, its strings inside it */
	scene->kwin_script = NULL;
	scene->fallback = NULL;
	return false;
}

void scene_unmap(struct scene *scene)
{
	if (scene->map)
		munmap(scene->map, scene->map_size);
	scene->map = NULL;
	scene->map_size = 0;
	scene->vertex = (struct blob){ 0 };
	for (int i = 0; i < PROGRAM_COUNT; i++)
		scene->fragment[i] = (struct blob){ 0 };
	for (int i = 0; i < TEXTURE_COUNT; i++)
		scene->texture[i].pixels = (struct blob){ 0 };
	free(scene->uniform);
	scene->uniform = NULL;
	scene->uniforms = 0;
	free(scene->sources);
	scene->sources = NULL;
}

bool scene_drop_pixels(struct scene *scene)
{
	size_t size = scene->vertex.size;
	for (int i = 0; i < PROGRAM_COUNT; i++)
		size += scene->fragment[i].size;
	char *kept = malloc(size ? size : 1);
	if (!kept) {
		scene_unmap(scene);
		return false;
	}
	char *p = kept;
	struct blob *all[PROGRAM_COUNT + 1] = { &scene->vertex };
	for (int i = 0; i < PROGRAM_COUNT; i++)
		all[i + 1] = &scene->fragment[i];
	for (int i = 0; i <= PROGRAM_COUNT; i++) {
		memcpy(p, all[i]->data, all[i]->size);
		all[i]->data = p;
		p += all[i]->size;
	}
	free(scene->sources);
	scene->sources = kept;
	if (scene->map)
		munmap(scene->map, scene->map_size);
	scene->map = NULL;
	scene->map_size = 0;
	for (int i = 0; i < TEXTURE_COUNT; i++)
		scene->texture[i].pixels = (struct blob){ 0 };
	return true;
}
