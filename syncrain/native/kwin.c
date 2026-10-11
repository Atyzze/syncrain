/* Which screens a window covers, as KWin knows it: syncrain/hidden.py's Watch, in C, over libdbus.
 *
 * KWin keeps asking a covered wallpaper for frames, so on Plasma the wallpaper asks KWin instead:
 * it writes the script syncrain/hidden.py holds (the scene carries it, "@SERVICE@" left to fill in)
 * to $XDG_RUNTIME_DIR, loads it into KWin over D-Bus and runs it; the script calls back
 * org.syncrain.Watch.Covered(screen, covered) whenever a screen's answer changes, and only KWin's
 * own bus name is believed. KWin's show desktop uncovers everything while it lasts. The script is
 * unloaded and its file deleted when the wallpaper stops; scripts left by a syncrain that died are
 * unloaded by the next one. hidden.py's docstring has the reasons, case by case.
 */
#define _GNU_SOURCE
#include <dirent.h>
#include <fcntl.h>
#include <limits.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <dbus/dbus.h>

#include "syncrain.h"

#define KWIN "org.kde.KWin"
#define WATCH_PATH "/org/syncrain/Watch"
#define WATCH_INTERFACE "org.syncrain.Watch"
#define TIMEOUT_MS 3000
#define MAX_SCREENS 32

struct watch {
	DBusConnection *bus;
	char *kwin_owner;
	char plugin[64];
	char path[PATH_MAX];
	bool registered, matched, filtered;
	bool answered, showing_desktop;
	struct {
		char name[64];
		bool covered;
	} screen[MAX_SCREENS];
	int screens;
	void (*on_change)(void);
	char why[512];
};

static const char *const MATCH =
	"type='signal',sender='" KWIN "',interface='" KWIN "',member='showingDesktopChanged',path='/KWin'";

struct watch *watch_new(void (*on_change)(void))
{
	struct watch *w = calloc(1, sizeof *w);
	if (w) {
		w->on_change = on_change;
		snprintf(w->plugin, sizeof w->plugin, "syncrain-watch-%d", (int)getpid());
	}
	return w;
}

/* A method call that waits for its reply, as Gio's call_sync does (3 s). NULL on error, with `err` set. */
static DBusMessage *call(struct watch *w, const char *dest, const char *path, const char *iface,
                         const char *method, DBusError *err, int first_type, ...)
{
	DBusMessage *m = dbus_message_new_method_call(dest, path, iface, method);
	if (!m) {
		dbus_set_error_const(err, DBUS_ERROR_NO_MEMORY, "out of memory");
		return NULL;
	}
	va_list args;
	va_start(args, first_type);
	bool ok = first_type == DBUS_TYPE_INVALID || dbus_message_append_args_valist(m, first_type, args);
	va_end(args);
	if (!ok) {
		dbus_message_unref(m);
		dbus_set_error_const(err, DBUS_ERROR_NO_MEMORY, "out of memory");
		return NULL;
	}
	DBusMessage *reply = dbus_connection_send_with_reply_and_block(w->bus, m, TIMEOUT_MS, err);
	dbus_message_unref(m);
	return reply;
}

static void unload(struct watch *w, const char *plugin)
{
	DBusError err;
	dbus_error_init(&err);
	DBusMessage *r = call(w, KWIN, "/Scripting", "org.kde.kwin.Scripting", "unloadScript", &err,
	                      DBUS_TYPE_STRING, &plugin, DBUS_TYPE_INVALID);
	if (r)
		dbus_message_unref(r);
	dbus_error_free(&err);
}

static int find_screen(struct watch *w, const char *name)
{
	for (int i = 0; i < w->screens; i++)
		if (strcmp(w->screen[i].name, name) == 0)
			return i;
	return -1;
}

static void reply_error(DBusConnection *c, DBusMessage *m, const char *name, const char *text)
{
	DBusMessage *e = dbus_message_new_error(m, name, text);
	if (e) {
		dbus_connection_send(c, e, NULL);
		dbus_message_unref(e);
	}
}

/* org.syncrain.Watch.Covered(screen, covered), from KWin's script and from nobody else. */
static DBusHandlerResult on_call(DBusConnection *c, DBusMessage *m, void *data)
{
	struct watch *w = data;
	if (dbus_message_get_type(m) != DBUS_MESSAGE_TYPE_METHOD_CALL)
		return DBUS_HANDLER_RESULT_NOT_YET_HANDLED;
	const char *iface = dbus_message_get_interface(m);
	if (!iface || strcmp(iface, WATCH_INTERFACE) != 0)
		return DBUS_HANDLER_RESULT_NOT_YET_HANDLED;
	const char *sender = dbus_message_get_sender(m);
	if (!sender || !w->kwin_owner || strcmp(sender, w->kwin_owner) != 0 ||
	    !dbus_message_is_method_call(m, WATCH_INTERFACE, "Covered")) {
		reply_error(c, m, DBUS_ERROR_ACCESS_DENIED, "not KWin");
		return DBUS_HANDLER_RESULT_HANDLED;
	}
	DBusError err;
	dbus_error_init(&err);
	const char *screen = NULL;
	dbus_bool_t covered = FALSE;
	if (!dbus_message_get_args(m, &err, DBUS_TYPE_STRING, &screen, DBUS_TYPE_BOOLEAN, &covered,
	                           DBUS_TYPE_INVALID)) {
		reply_error(c, m, DBUS_ERROR_INVALID_ARGS, err.message ? err.message : "Covered(sb)");
		dbus_error_free(&err);
		return DBUS_HANDLER_RESULT_HANDLED;
	}
	DBusMessage *r = dbus_message_new_method_return(m);
	if (r) {
		dbus_connection_send(c, r, NULL);
		dbus_message_unref(r);
	}
	w->answered = true;
	int i = find_screen(w, screen);
	if (i < 0 && w->screens < MAX_SCREENS) {
		i = w->screens++;
		snprintf(w->screen[i].name, sizeof w->screen[i].name, "%s", screen);
		w->screen[i].covered = !covered;                  /* so that it counts as a change */
	}
	if (i >= 0 && w->screen[i].covered != (bool)covered) {
		w->screen[i].covered = covered;
		w->on_change();
	}
	return DBUS_HANDLER_RESULT_HANDLED;
}

/* KWin's showingDesktopChanged(bool), from KWin itself. */
static DBusHandlerResult on_signal(DBusConnection *c, DBusMessage *m, void *data)
{
	(void)c;
	struct watch *w = data;
	if (!dbus_message_is_signal(m, KWIN, "showingDesktopChanged"))
		return DBUS_HANDLER_RESULT_NOT_YET_HANDLED;
	const char *path = dbus_message_get_path(m), *sender = dbus_message_get_sender(m);
	if (!path || strcmp(path, "/KWin") != 0 || !sender || !w->kwin_owner || strcmp(sender, w->kwin_owner) != 0)
		return DBUS_HANDLER_RESULT_NOT_YET_HANDLED;
	dbus_bool_t showing = FALSE;
	if (dbus_message_get_args(m, NULL, DBUS_TYPE_BOOLEAN, &showing, DBUS_TYPE_INVALID) &&
	    (bool)showing != w->showing_desktop) {
		w->showing_desktop = showing;
		w->on_change();
	}
	return DBUS_HANDLER_RESULT_NOT_YET_HANDLED;
}

static const DBusObjectPathVTable VTABLE = { .message_function = on_call };

/* syncrain/power.py, is_syncrain_command: `python -m syncrain`, the Nix package's wrapped script, or
 * this program; a pid taken over by anything else is not a syncrain. */
bool is_syncrain_command(char **argv, int argc)
{
	if (argc <= 0)
		return false;
	for (int i = 1; i < argc; i++)
		if (strcmp(argv[i], "syncrain") == 0 && strcmp(argv[i - 1], "-m") == 0)
			return true;
	const char *a = strrchr(argv[0], '/');
	a = a ? a + 1 : argv[0];
	if (strcmp(a, ".syncrain-wrapped") == 0 || strcmp(a, "syncrain-wallpaper") == 0)
		return true;
	if (argc > 1 && strncmp(a, "python", 6) == 0) {
		const char *b = strrchr(argv[1], '/');
		b = b ? b + 1 : argv[1];
		return strcmp(b, "syncrain") == 0 || strcmp(b, ".syncrain-wrapped") == 0;
	}
	return false;
}

static bool alive(int pid)
{
	char path[64], buf[8192];
	snprintf(path, sizeof path, "/proc/%d/cmdline", pid);
	int fd = open(path, O_RDONLY | O_CLOEXEC);
	if (fd < 0)
		return false;
	ssize_t n = read(fd, buf, sizeof buf - 1);
	close(fd);
	if (n <= 0)
		return false;
	buf[n] = '\0';
	char *argv[64];
	int argc = 0;
	for (ssize_t i = 0; i < n && argc < 64; i += (ssize_t)strlen(buf + i) + 1)
		if (buf[i])
			argv[argc++] = buf + i;
	return is_syncrain_command(argv, argc);
}

/* The scripts of syncrains that died without unloading theirs (a crash, SIGKILL). */
static void unload_leftovers(struct watch *w, const char *runtime)
{
	DIR *d = opendir(runtime);
	if (!d)
		return;
	for (struct dirent *e; (e = readdir(d)); ) {
		int pid = 0, len = 0;
		if (sscanf(e->d_name, "syncrain-watch-%d.js%n", &pid, &len) != 1 || e->d_name[len] != '\0' ||
		    pid == (int)getpid() || alive(pid))
			continue;
		char plugin[64], path[PATH_MAX];
		snprintf(plugin, sizeof plugin, "syncrain-watch-%d", pid);
		snprintf(path, sizeof path, "%s/%s", runtime, e->d_name);
		unload(w, plugin);
		unlink(path);
	}
	closedir(d);
}

static bool write_script(struct watch *w, const char *template)
{
	const char *service = dbus_bus_get_unique_name(w->bus);
	int fd = open(w->path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
	if (fd < 0 || !service)
		return false;
	FILE *f = fdopen(fd, "w");
	if (!f) {
		close(fd);
		return false;
	}
	const char *mark = "@SERVICE@";
	for (const char *p = template; *p; ) {
		const char *hit = strstr(p, mark);
		if (!hit) {
			fputs(p, f);
			break;
		}
		fwrite(p, 1, (size_t)(hit - p), f);
		fprintf(f, "\"%s\"", service);             /* a unique name needs no JSON escaping */
		p = hit + strlen(mark);
	}
	return fclose(f) == 0;
}

static const char *failed(struct watch *w, DBusError *err)
{
	snprintf(w->why, sizeof w->why, "KWin's scripting did not answer (%s)",
	         err->message ? err->message : "no reply");
	dbus_error_free(err);
	watch_stop(w);
	return w->why;
}

const char *watch_start(struct watch *w, const char *script_template, bool maximized)
{
	(void)maximized;                                      /* already in the script the scene carries */
	DBusError err;
	dbus_error_init(&err);
	w->bus = dbus_bus_get_private(DBUS_BUS_SESSION, &err);
	if (!w->bus)
		return failed(w, &err);
	dbus_connection_set_exit_on_disconnect(w->bus, FALSE);
	const char *name = KWIN;
	DBusMessage *r = call(w, DBUS_SERVICE_DBUS, DBUS_PATH_DBUS, DBUS_INTERFACE_DBUS, "NameHasOwner", &err,
	                      DBUS_TYPE_STRING, &name, DBUS_TYPE_INVALID);
	dbus_bool_t has = FALSE;
	if (!r || !dbus_message_get_args(r, &err, DBUS_TYPE_BOOLEAN, &has, DBUS_TYPE_INVALID)) {
		if (r)
			dbus_message_unref(r);
		return failed(w, &err);
	}
	dbus_message_unref(r);
	if (!has) {
		watch_stop(w);
		return "KWin is not on the session bus";
	}
	r = call(w, DBUS_SERVICE_DBUS, DBUS_PATH_DBUS, DBUS_INTERFACE_DBUS, "GetNameOwner", &err,
	         DBUS_TYPE_STRING, &name, DBUS_TYPE_INVALID);
	const char *owner = NULL;
	if (!r || !dbus_message_get_args(r, &err, DBUS_TYPE_STRING, &owner, DBUS_TYPE_INVALID)) {
		if (r)
			dbus_message_unref(r);
		return failed(w, &err);
	}
	w->kwin_owner = strdup(owner);
	dbus_message_unref(r);
	if (!dbus_connection_register_object_path(w->bus, WATCH_PATH, &VTABLE, w)) {
		dbus_set_error_const(&err, DBUS_ERROR_NO_MEMORY, "the watch could not be registered");
		return failed(w, &err);
	}
	w->registered = true;
	dbus_bus_add_match(w->bus, MATCH, &err);
	if (dbus_error_is_set(&err))
		return failed(w, &err);
	w->matched = true;
	if (!dbus_connection_add_filter(w->bus, on_signal, w, NULL)) {
		dbus_set_error_const(&err, DBUS_ERROR_NO_MEMORY, "the signal filter could not be added");
		return failed(w, &err);
	}
	w->filtered = true;
	const char *iface = KWIN, *prop = "showingDesktop";
	r = call(w, KWIN, "/KWin", DBUS_INTERFACE_PROPERTIES, "Get", &err, DBUS_TYPE_STRING, &iface,
	         DBUS_TYPE_STRING, &prop, DBUS_TYPE_INVALID);
	w->showing_desktop = false;
	if (r) {
		DBusMessageIter it, v;
		if (dbus_message_iter_init(r, &it) && dbus_message_iter_get_arg_type(&it) == DBUS_TYPE_VARIANT) {
			dbus_message_iter_recurse(&it, &v);
			if (dbus_message_iter_get_arg_type(&v) == DBUS_TYPE_BOOLEAN) {
				dbus_bool_t b = FALSE;
				dbus_message_iter_get_basic(&v, &b);
				w->showing_desktop = b;
			}
		}
		dbus_message_unref(r);
	}
	dbus_error_free(&err);
	const char *runtime = getenv("XDG_RUNTIME_DIR");
	if (!runtime || !*runtime)
		runtime = "/tmp";
	unload_leftovers(w, runtime);
	snprintf(w->path, sizeof w->path, "%s/%s.js", runtime, w->plugin);
	if (!write_script(w, script_template)) {
		snprintf(w->why, sizeof w->why, "KWin's scripting did not answer (the script could not be written to %s)",
		         runtime);
		w->path[0] = '\0';
		watch_stop(w);
		return w->why;
	}
	unload(w, w->plugin);                                 /* a script of a process with this pid that never unloaded */
	const char *path = w->path, *plugin = w->plugin;
	r = call(w, KWIN, "/Scripting", "org.kde.kwin.Scripting", "loadScript", &err, DBUS_TYPE_STRING, &path,
	         DBUS_TYPE_STRING, &plugin, DBUS_TYPE_INVALID);
	dbus_int32_t id = -1;
	if (!r || !dbus_message_get_args(r, &err, DBUS_TYPE_INT32, &id, DBUS_TYPE_INVALID)) {
		if (r)
			dbus_message_unref(r);
		return failed(w, &err);
	}
	dbus_message_unref(r);
	if (id < 0) {
		watch_stop(w);
		return "KWin did not load the script";
	}
	char script[64];
	snprintf(script, sizeof script, "/Scripting/Script%d", (int)id);
	r = call(w, KWIN, script, "org.kde.kwin.Script", "run", &err, DBUS_TYPE_INVALID);
	if (!r)
		return failed(w, &err);
	dbus_message_unref(r);
	return NULL;
}

/* The script has not answered: perhaps `run` reached another script with the same number
 * (hidden.py's docstring). Ask KWin to run every loaded script that is not running. */
void watch_retry(struct watch *w)
{
	if (!w->bus)
		return;
	DBusError err;
	dbus_error_init(&err);
	DBusMessage *r = call(w, KWIN, "/Scripting", "org.kde.kwin.Scripting", "start", &err, DBUS_TYPE_INVALID);
	if (r)
		dbus_message_unref(r);
	dbus_error_free(&err);
}

void watch_stop(struct watch *w)
{
	if (!w->bus)
		return;
	if (dbus_connection_get_is_connected(w->bus)) {
		if (w->path[0])
			unload(w, w->plugin);
		if (w->matched)
			dbus_bus_remove_match(w->bus, MATCH, NULL);
	}
	if (w->filtered)
		dbus_connection_remove_filter(w->bus, on_signal, w);
	if (w->registered)
		dbus_connection_unregister_object_path(w->bus, WATCH_PATH);
	w->matched = w->filtered = w->registered = false;
	if (w->path[0]) {
		unlink(w->path);
		w->path[0] = '\0';
	}
	dbus_connection_close(w->bus);
	dbus_connection_unref(w->bus);
	w->bus = NULL;
	free(w->kwin_owner);
	w->kwin_owner = NULL;
}

void watch_free(struct watch *w)
{
	if (w) {
		watch_stop(w);
		free(w);
	}
}

int watch_fd(const struct watch *w)
{
	int fd = -1;
	if (w && w->bus && !dbus_connection_get_unix_fd(w->bus, &fd))
		fd = -1;
	return fd;
}

/* Reads what arrived and runs the handlers. A bus that went away takes the watch with it: then
 * nothing counts as covered, as before the watch started. */
void watch_dispatch(struct watch *w)
{
	if (!w || !w->bus)
		return;
	if (!dbus_connection_read_write(w->bus, 0)) {
		watch_stop(w);
		w->answered = false;
		w->screens = 0;
		w->on_change();
		return;
	}
	while (dbus_connection_dispatch(w->bus) == DBUS_DISPATCH_DATA_REMAINS)
		;
	dbus_connection_flush(w->bus);
}

bool watch_answered(const struct watch *w)
{
	return w && w->bus && w->answered;
}

/* hidden.is_hidden for a viewport showing one screen: covered, and KWin not showing the desktop. */
bool watch_hidden(const struct watch *w, const char *screen)
{
	if (!w || !w->bus || !screen || !*screen || w->showing_desktop)
		return false;
	for (int i = 0; i < w->screens; i++)
		if (strcmp(w->screen[i].name, screen) == 0)
			return w->screen[i].covered;
	return false;
}
