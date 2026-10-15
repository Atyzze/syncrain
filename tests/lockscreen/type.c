/* Types on KWin's keyboard as a person would: type FD WORD... (each word, then Enter, a second apart).
 * FD is a libei socket KWin handed out (org.kde.KWin.EIS.RemoteDesktop.connectToEIS, asked for by
 * tests/lockscreen/); what is typed goes where KWin sends keys, so to a locked screen's greeter.
 * Built by tests/lockscreen/ against Nix's libei. Only lower-case letters and digits. */
#include <libei.h>
#include <linux/input-event-codes.h>
#include <poll.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static struct ei *ei;
static struct ei_device *keyboard;
static bool resumed;

static int code(char c)
{
	static const char *rows[] = { "1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm" };
	static const int first[] = { KEY_1, KEY_Q, KEY_A, KEY_Z };
	for (int r = 0; r < 4; r++) {
		const char *at = strchr(rows[r], c);
		if (c && at)
			return first[r] + (int)(at - rows[r]);
	}
	return -1;
}

/* Handles what KWin says for up to `ms` milliseconds, or until `done` holds. */
static void pump(int ms, bool *done)
{
	for (int waited = 0; waited < ms && !(done && *done); waited += 20) {
		struct pollfd p = { .fd = ei_get_fd(ei), .events = POLLIN };
		if (poll(&p, 1, 20) > 0)
			ei_dispatch(ei);
		struct ei_event *e;
		while ((e = ei_get_event(ei))) {
			switch (ei_event_get_type(e)) {
			case EI_EVENT_SEAT_ADDED:
				ei_seat_bind_capabilities(ei_event_get_seat(e), EI_DEVICE_CAP_KEYBOARD, NULL);
				break;
			case EI_EVENT_DEVICE_ADDED:
				if (!keyboard && ei_device_has_capability(ei_event_get_device(e), EI_DEVICE_CAP_KEYBOARD))
					keyboard = ei_device_ref(ei_event_get_device(e));
				break;
			case EI_EVENT_DEVICE_RESUMED:
				if (ei_event_get_device(e) == keyboard) {
					ei_device_start_emulating(keyboard, 1);
					resumed = true;
				}
				break;
			case EI_EVENT_DISCONNECT:
				fprintf(stderr, "type: KWin closed the connection\n");
				exit(1);
			default:
				break;
			}
			ei_event_unref(e);
		}
	}
}

static void key(int k, bool down)
{
	ei_device_keyboard_key(keyboard, (uint32_t)k, down);
	ei_device_frame(keyboard, ei_now(ei));
	pump(30, NULL);
}

int main(int argc, char **argv)
{
	if (argc < 2) {
		fprintf(stderr, "usage: type FD WORD...\n");
		return 2;
	}
	ei = ei_new_sender(NULL);
	ei_configure_name(ei, "syncrain tests");
	if (ei_setup_backend_fd(ei, atoi(argv[1])) != 0) {
		fprintf(stderr, "type: not a libei socket\n");
		return 1;
	}
	pump(5000, &resumed);
	if (!resumed) {
		fprintf(stderr, "type: KWin gave no keyboard\n");
		return 1;
	}
	for (int i = 2; i < argc; i++) {
		for (const char *c = argv[i]; *c; c++) {
			const int k = code(*c);
			if (k < 0) {
				fprintf(stderr, "type: cannot type '%c'\n", *c);
				return 2;
			}
			key(k, true);
			key(k, false);
		}
		key(KEY_ENTER, true);
		key(KEY_ENTER, false);
		pump(1000, NULL);
	}
	ei_device_stop_emulating(keyboard);
	pump(100, NULL);
	ei_device_unref(keyboard);
	ei_unref(ei);
	return 0;
}
