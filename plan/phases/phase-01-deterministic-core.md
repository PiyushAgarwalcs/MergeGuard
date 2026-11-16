# Phase 1: Deterministic core (no model, no network)

Goal: the parts that must give the same answer every time, fully tested.
Depends on: Phase 0. Read: `02-architecture.md` (verifier, merge, risk, judge sections).

## Tasks

- [x] **P1.1** `checks/diff_parser.py`: parse a unified diff into `Hunk` and `AddedLine` with correct new-file line numbers. Handle renames, binary files, deleted files, CRLF, no newline at end, unicode, multiple hunks. Tests with at least 15 tricky diffs in `tests/fixtures/diffs/`.
- [x] **P1.2** `checks/redact.py`: replace detected secrets with `[REDACTED:<type>]` in diff text. Tests: 100% of synthetic secrets removed, ordinary text unchanged.
- [x] **P1.3** `checks/rule_scan.py`: rules as a list of (name, pattern, severity, category). Secrets: AWS access key, generic API key assignments, private key blocks, JWT-like tokens, high-entropy strings in assignments. Patterns: `verify=False`, `shell=True` with variable input, `pickle.loads`, `yaml.load` without safe loader, `eval`/`exec` on non-literals, SQL built with f-strings or `%` or `+` on execute calls, `md5`/`sha1` for passwords, `random` for tokens, debug flags enabled, logging of password or token variables. Only scan added lines. Tests: precision and recall on at least 60 labeled snippets including placeholders and test-fixture keys that must not fire.
- [x] **P1.4** `checks/verify_findings.py`: exactly as specified in `02-architecture.md`. Tests: four adversarial sets (fabricated quote, wrong lines, invented evidence, quote from unchanged context) all rejected; genuine findings all accepted.
- [x] **P1.5** `checks/merge_findings.py`: dedupe and id assignment as specified. Tests for overlap, tie-breaking and ordering.
- [x] **P1.6** `checks/judge.py`: risk score and decision exactly as specified, with reasons. Tests: full truth table of conditions; property tests (adding a critical never lowers outcome severity; more changed lines never lowers the score; any missing input never gives `pass`; the LLM-sourced findings cannot remove a rule finding).
- [x] **P1.7** Create ten hand-made diffs in `examples/` (five with an obvious flaw, five clean) and `cli.py` command `mergeguard review <diff-file>` that runs parse, redact, rule_scan, verify, merge and judge and prints a readable result (Rich) and exits 0 for pass, 1 for needs_human, 2 for block.

## Verify

`make check` and `mergeguard review examples/<flawed>.diff` prints a `block` decision with file and line; `mergeguard review examples/<clean>.diff` prints `pass`.

## Done when

All tasks ticked and every L1 bar in `04-evaluation.md` that applies to these modules is met by tests.
