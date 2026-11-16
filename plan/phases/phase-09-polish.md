# Phase 9: Dashboard completion, monitoring, documentation, final report

Goal: a stranger can understand, run and trust the project.
Depends on: Phase 8.

## Tasks

- [x] **P9.1** Dashboard page `10_Live_Runs.py`: runs, decisions, findings, trace, feedback, drift (rolling 14-day metrics versus baseline), and the alert banners from `03-observability.md`. AppTest smoke test.
- [x] **P9.2** Monitoring helpers: shadow-mode summary command `mergeguard shadow-report`, dismissal rate per category, approve-after-block list. Tests.
- [x] **P9.3** Documentation: `docs/how-it-works.md` (one page with the flow diagram), `docs/evaluation.md` (how to run each layer, how to read the dashboard, ablation result), final `docs/threat-model.md`.
- [x] **P9.4** `README.md`: one-line pitch; the flow diagram; a quick start that works in replay mode with no API key (`pip install -e .`, `mergeguard review examples/<flawed>.diff`, `streamlit run dashboard/app.py`); a results table filled only with numbers actually stored in SQLite (dataset version, model, split, recall, false findings per clean PR, unsafe-pass rate, decision agreement, latency, cost), and the text "not yet measured" for anything missing; the ablation outcome; limits and non-goals.
- [x] **P9.5** Code-quality pass: any file over about 200 lines is split; remove dead code; `make check` clean; every module has its header comment; `.env.example` matches `settings.py`.
- [x] **P9.6** Write `plan/FINAL-REPORT.md`: what was built, the latest evaluation numbers, every deviation from the plan, all open blockers, and suggested next steps.
- [x] **P9.7** Add an optional local Ollama provider with schema-constrained output, test it against an installed model, and document its environment configuration. Do not run the full evaluation without user approval.
- [x] **P9.8** Add an optional Groq structured-output fallback and verify its provider schemas; keep the full evaluation approval-gated.
- [x] **P9.9** Remove manual dataset labeling and score-validation workflows, synchronize project checklists and manifests, and finish the final report and consistency artifact.

## Verify

`make check`; a fresh clone follows the README quick start successfully.

## Done when

All tasks ticked, README results are real, FINAL-REPORT.md exists.
