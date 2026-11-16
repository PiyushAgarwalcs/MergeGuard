# Phase 6: The agent team, the graph, pipeline evals, ablations

Goal: the full multi-agent pipeline, end to end, with numbers. Read `02-architecture.md` fully and `04-evaluation.md` (L4, L7).
Depends on: Phase 5.

## Tasks

- [x] **P6.1** `agents/correctness_reviewer.py` and `agents/test_reviewer.py` with prompts `correctness_reviewer.v1.md` and `test_reviewer.v1.md` (own categories, same rules as the security reviewer). Tests with `ScriptedLLM`.
- [x] **P6.2** `agents/skeptic.py` and `skeptic.v1.md`: input is one finding, its hunk and its evidence; output is `SkepticVerdict`. Orchestration helper runs it only on verified LLM findings of severity medium or higher, never on rule findings. Tests including that rule findings are never sent.
- [x] **P6.3** `agents/reporter.py`: deterministic markdown comment from verified findings (file, line, severity, explanation, suggestion, finding id, how to dismiss), decision and reasons; optional one-paragraph LLM summary off by default. Faithfulness check function: every file, line and count mentioned in the comment maps to a verified finding. Tests.
- [x] **P6.4** `graph.py`: the pipeline from `02-architecture.md` with parallel reviewers and the append reducer, conditional edges, timeouts and one retry per LLM node, failed agents set `complete=False`, LangGraph SQLite checkpointer. Provide `build_graph(checkpointer, variant='full')` where `variant` supports the five ablations: `single_agent`, `no_skeptic`, `no_verifier`, `no_context`, `no_rules`. Human gate may be a pass-through for now (Phase 7). Replace the pipeline inside `mergeguard review` with the graph. Tests: every conditional edge taken at least once with `ScriptedLLM`; one failed reviewer still yields a decision with `complete=False`.
- [x] **P6.5** `evals/suites/agents_other.py` (correctness, test reviewer, skeptic, reporter faithfulness, format reliability) and `evals/suites/pipeline.py` (L4: confusion matrix, unsafe-pass, over-block, over-escalation, finding recall, precision, localization, severity agreement, latency, cost, slices). Same live, replay and stub rules as P5.5.
- [x] **P6.6** `evals/suites/ablations.py`: run the five variants plus the full design on the dev split, compute differences with bootstrap intervals, store them, and write the outcome (including the case where a single agent matches the team) to `docs/evaluation.md`.
- [x] **P6.7** Dashboard pages `3_Pipeline.py`, `7_Ablations.py`, `8_Cost_Latency.py` with AppTest smoke tests.

## Verify

`make check`; `mergeguard review examples/<flawed>.diff` runs the graph and prints a decision; `python -m evals.run --layer pipeline --split dev --mode replay`; `python -m evals.run --layer ablations --split dev --mode replay`.

## Done when

The full pipeline runs end to end, pipeline and ablation numbers are stored (live or marked `stub`), and `docs/evaluation.md` reports the ablation result.
