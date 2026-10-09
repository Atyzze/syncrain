# Working with the operator

The same person GSD's documents describe; syncrain adopted that project's ways at build 3.

## What they send

* **Screenshots** (Konsole, btop): read the commands, paths, versions and numbers, not only the
  error.
* **Several requests in one message**, and more during a build: answer every one, and give a new
  idea its line in `docs/ROADMAP.md` the same turn.

## How they decide

* Give **options with a recommendation**, cost first, numbered so they can answer briefly. Write the
  question into the roadmap, and the answer under "Decisions answered".
* Say **what was verified, on what machine**, and what was not: the sandbox is not their desktop.
* **Never ask them to type a command of your own.** Ask for what an existing command prints; if
  none prints it, build one into the next build.

## How to answer

* One plain sentence first, then what was done, then what they do.
* **Short**: bullets and tables, no walls of text, in replies and in the documents (2026-10-09:
  "Keep it minimal please").
* No long dashes. "The operator" or "they". Never send their email address anywhere.
* Deliver only the release tool's archive, after its gate; say what to do with it (unpack,
  `./install.sh`) and what to look for.
* A build that changes their desktop as much as build 8 did goes to GitHub after their trial.

## Pace

* Keep building while nothing waits on them; stop only for what they must decide, send or run.
* Remember by pointer: what is open lives in the roadmap and the handoff, not only in a reply.
* Consolidations are fixed at every number ending in 0; never propose moving one.
