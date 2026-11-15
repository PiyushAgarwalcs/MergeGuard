# Phase 5: Model client, context, first agent, agent evals

Goal: one real LLM agent, measured on its own. Read `02-architecture.md` (agent rules), `07-security-and-code-standards.md` (llm.py requirements), `08-configuration-and-credentials.md`.
Depends on: Phases 2 and 4.

## Tasks

- [ ] **P5.1** `llm.py` exactly as described in `07-security-and-code-standards.md`: modes live, record, replay, off; JSON parsing tolerant of code fences; Pydantic validation; one retry with the error appended; timeout; cost and latency recorded through `tracing`; `ScriptedLLM` for tests. Tests use only `ScriptedLLM` and temporary cache directories.
- [ ] **P5.2** `checks/collect_context.py`: from a repo snapshot or PR payload, build `ReviewContext`: callers of changed functions (Python `ast`), tests that import or name the changed modules, sibling functions in the same module, CI status from a fixture or from `github.py` later (return `missing` when unknown), size caps. Add the context-collector suite to `evals/suites/components.py` using small fixture repos with a known call graph.
- [ ] **P5.3** Prompt loader and `src/mergeguard/prompts/security_reviewer.v1.md`: role, the 12 security categories with one-line definitions, delimited diff and context blocks, the standing instruction that nothing inside the diff is an instruction, the JSON output schema, the requirement of an exact quote and evidence ids, and an instruction to return an empty list when nothing is found.
- [ ] **P5.4** `agents/security_reviewer.py` following the example in `07-security-and-code-standards.md`. Tests with `ScriptedLLM`: valid output, malformed output (retry then failed agent), empty output.
- [ ] **P5.5** `evals/suites/agent_security.py`: run the agent alone on the dev split with context pre-built; compute recall by category, precision, localization, quote-validity, severity agreement and hard-negative false-positive rate; save the result. It must work in `replay` mode from a recorded cache and, when `LLM_MODE=live` and credentials exist, record the cache. Without credentials, run against a deterministic stub reviewer built from the rule scanner and mark the result `stub` in the summary.
- [ ] **P5.6** LLM-assisted dataset growth: `evals/factory/seed_llm.py` (seed_issue prompt `evals/factory/prompts/seed_issue.v1.md`) and `evals/factory/cross_check.py` (different model family), wired into `build --version v0.2 --llm`. When credentials are missing, the command prints a clear message and exits 0 without writing anything. Disagreements go to `review_queue/`.

## Verify

`make check`; `python -m evals.run --layer agent_security --split dev --mode replay`; with credentials: the same command with `--mode live` then `--mode replay` reproduces the numbers.

## Done when

The security reviewer has stored baseline numbers on the dev split (live if credentials exist, otherwise marked `stub`), and `BLOCKERS.md` lists anything that needed credentials.
