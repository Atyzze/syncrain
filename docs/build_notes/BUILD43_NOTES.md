# Build 43: KDE's wallet opens after greetd's text login, and SELinux is said

**Type: fix; the picture does not change** (stream `1ad0a2dd`). Made on 2026-10-16, the second of
the builds on the roadmap's open items. This one takes the login screen's two: L8, and Fedora's
SELinux.

## The wallet after the text login (L8)

* KDE's wallet opened after a login in syncrain's box, but not after greetd's text login (the one
  that asks when the box does not come up). pam_kwallet5 opens the wallet only for a session it
  knows is graphical, by `XDG_SESSION_TYPE` when PAM opens the session: the box tells greetd
  "wayland", the text login (agreety) cannot. The wallet's session line in greetd's PAM file now has
  `force_run`. It cannot reach greetd's greeter (greetd never authenticates it, so there is no
  password to open a wallet with), pam_kwallet5 does nothing for root, and an older pam_kwallet5
  passes over an option it does not know. Where greetd's PAM file had its own wallet lines already,
  syncrain adds none and changes none.
* A login screen set up by an earlier build gets the new line at the next install; only syncrain's
  own marked lines change, and only when every other line of the file is kept (a failed read would
  otherwise have left greetd a PAM file of these optional lines alone). `--login-screen-off` still
  takes out exactly those.

## SELinux (Fedora)

* With SELinux on, every install gives the login screen's files their default labels (`restorecon`,
  keeping any the operator set on purpose), and `--login-screen` says once where to look should
  greetd's domain still be refused. Where the login screen is installed, `--diagnose` shows whether
  SELinux is enforcing and this boot's refusals of it from the journal, or says the journal could
  not be read. Nothing changes SELinux's policy; the text login asks meanwhile.

## The review of this build

An agent that did not write it read it, against kwallet-pam's and greetd's own source: nothing
critical. Its one major finding (a failed read could have written greetd a PAM file of syncrain's
lines alone) is guarded and tested; the minor ones (restorecon's `-F`, the journal unread taken for
no refusals, the SDDM refusals counted, the docs' wording) are fixed above.

## What the operator does

* With the login screen: `./install.sh` as usual. Without it: nothing.

## Verification

554 passed in 1421.87s (0:23:41)
