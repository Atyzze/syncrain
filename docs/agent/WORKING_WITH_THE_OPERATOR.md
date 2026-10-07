# Working with the operator

How the work with them goes. The operator is the same person GSD's own page on working with them
describes, and build 3 adopted that project's ways at their request; this is the part that
applies here, and what syncrain has added.

## What they send, and how to read it

* **Screenshots of a terminal** (Konsole, fish): read them for the commands they ran, the paths and
  the versions pacman printed, not only the error. Build 3's diagnosis came from one: the two
  "OpenGL unavailable" lines meant two screens, and the traceback's paths showed the launcher had
  started the unpacked copy.
* **A whole codebase as an archive** (GSD592): practices to adopt. Read its README, its agent
  documents and its release tool before copying anything, and adopt the reasons, not only the
  shapes.
* **Several requests in one message**, and more while a build is under way. Answer every one; give
  a new idea its line in `docs/ROADMAP.md` at once and say which build it goes in.

## How they decide

* When a decision is theirs, give **options and a recommendation**, and what each costs, cost
  first. Numbered options let them answer briefly. Write the question into `docs/ROADMAP.md`,
  "Questions for the operator", the same turn, and the answer into "Decisions answered".
* **"Did we check?"** They want what was verified, on what, and what was not. Say which machine a
  result comes from: the sandbox is not their desktop (Mesa hid build 2's bug).
* **Never ask them to type a command of your own.** Ask for what an existing command prints, and
  if none prints it, build one into the next build and name it (`syncrain --diagnose` is that).

## How to answer them

* **No long dashes** in anything written to them or kept in the tree: a hyphen, a comma, a
  semicolon or a full stop.
* **They are "the operator" or "they"**, never a gendered pronoun.
* **One plain sentence first**, on what it means; then what was done; then what they do. The
  project on one page is `docs/WHERE_WE_ARE.md`; point them to it rather than re-explaining.
* **Deliver builds only as the archive `tools/package_release.py` writes**, after its gate has
  passed. Never a patch, never edits for them to make, never a tar made by hand.
* **Say what they do after a build** (unpack, `./install.sh`, restart or not) and what to look for.
* Never send their email address to any service.

## The pace

* **Keep building while nothing waits on them.** Stop only for what they must decide, send or run,
  and say which.
* **Remember by pointer, not by prose**: what is open lives in the roadmap and the handoff, not only
  in a reply, because a context is summarised when it fills.
* **Consolidations are fixed at every build number ending in 0.** Plan around them; never propose
  moving one.
