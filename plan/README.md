# START HERE

You are an autonomous coding agent. Your job is to build **MergeGuard**: a LangGraph multi-agent pull-request review and merge gate, together with its evaluation system and a dashboard. Everything you need is in this folder. The human will not answer questions, so decide and keep going.

## Read first, in this order

1. `01-decisions-and-scope.md`: what the product does and the fixed technical decisions
2. `02-architecture.md`: agents, flow, state, data contracts, folder structure
3. `07-security-and-code-standards.md`: how the code must look
4. `08-configuration-and-credentials.md`: environment variables and what to do without them
5. `DECISIONS.md` and `PROGRESS.md`

Read these only when their phase needs them: `03-observability.md`, `04-evaluation.md`, `05-golden-dataset.md`, `06-dashboard.md`.

## The work loop

Repeat until nothing unblocked is left:

1. Open `PROGRESS.md`. Take the first unchecked task whose phase dependencies are done.
2. Read the phase file in `phases/` for that task, and the documents it points to.
3. Implement the task. Write its tests in the same change.
4. Run `make check` (created in task P0.2). It must pass. If it fails, fix it. Do not skip or weaken tests to get green.
5. Tick the task in `PROGRESS.md`, add one line under Session notes, and commit as `P<phase>.<task>: <summary>`.
6. At the end of a phase, run every command in that phase's Verify section and paste the result summary into `PROGRESS.md`.
7. Continue with the next task.

## Rules for working without a human

- **Ambiguity:** use the default in `DECISIONS.md`. If it has none, choose the simplest option that satisfies the plan, and add a line to `DECISIONS.md` (date, decision, reason).
- **Missing credential:** follow `08-configuration-and-credentials.md`. Use the fake or replay mode, add a line to `BLOCKERS.md`, and continue with tasks that do not need it. Never stop the whole build for one blocker.
- **A plan item looks wrong or impossible:** implement the closest working version, record the deviation in `DECISIONS.md`, and continue.
- **A library API differs from the plan:** read the installed package (`help()`, source, docs) and adapt. The plan names libraries, not exact call signatures.
- **Scope:** do not add features that are not in the plan. Do not remove tests, checks or evaluations.
- **Green repository:** every commit leaves `make check` passing.

## Sessions

A session may end at any time (time limit, pull request boundary). Before ending, make sure the repository is green and `PROGRESS.md` is accurate, so the next session can resume from the first unchecked task. If your environment opens one pull request per session, title it `phase-N: <what was done>`.

## When you are finished

All tasks in `PROGRESS.md` are ticked, or the only unticked ones are listed in `BLOCKERS.md` with the reason. Then write `plan/FINAL-REPORT.md`: what was built, the latest evaluation numbers, deviations, and open blockers.
