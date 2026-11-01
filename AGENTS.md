# AGENTS.md - how to work in this repo

**Definition of done, stated before you start.** Write down what "done" means
for the task (the behaviour, the test that proves it, the gate that must stay
green) before the first edit. Done = that test passes, `python tools/run_tests.py`
is green (on a box without film media, only the media suites may fail), and
`python tools/pre_push_guard.py` reports `GUARD: clean`.

**Unblock first, harden later.** Get the smallest change that makes the stage
work end to end, commit it, then harden (edge cases, messages, refactors) in
separate commits. Never weaken a gate to make a test pass; a check that cannot
run reports "not run", never "pass".

**Timebox.** Give each task a budget up front. When it runs out, stop, commit
what is green, and write down what is left instead of drifting.

**One review pass.** Review the diff once, fix what it finds, ship. No second
or third polishing loop unless the review found a correctness bug.

**Fast inner loop.** While iterating, run `python tools/run_tests.py --changed`
(only suites touched by your edits). Run the full suite once, before pushing.

**Tests.** Every behaviour change gets a regression test in `tools/test_*.py`,
in the existing style (TESTS dict, PASS/FAIL lines, non-zero exit on failure).
Film-specific rules live only in tests and fixtures, never in pipeline code.

**Model routing.** Use the fastest model that is adequate. Mechanical subagent
work (search, renames, payload assembly, running suites, tagging batches) goes
to a small/fast model; design, gate logic and narration judgment stay on the
strongest model.

**Parallel work in git worktrees.** Independent tasks run in separate
worktrees (`git worktree add ../rv-<task> -b <branch>`), one task per tree, so
renders and test runs never collide on `projects/` output. Merge back one task
per commit.

**Commits.** One item per commit, a clear message, and a `Co-Authored-By`
line when an agent wrote it.
