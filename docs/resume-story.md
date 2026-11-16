# MergeGuard – Interview Prep / Resume Story

## The core problem

LLMs miss subtle security bugs (they hallucinate fixes and lose context in long diffs).
Deterministic scanners catch known patterns but generate noisy false positives and lack
the semantic understanding to judge exploitability.  MergeGuard combines both: a
deterministic rule engine that never misses known-bad patterns, plus a panel of LLM agents
that reason about context, intent, and exploitability — with the deterministic layer
overriding the LLMs when they would let an unsafe diff pass.

---

## LangGraph multi-agent design

| Agent | Role | Why it exists |
|---|---|---|
| Security Reviewer | Scans for CVE patterns, injection vectors, auth bypasses | LLMs reason about exploitability better than regex |
| Correctness Reviewer | Logic bugs, off-by-ones, type safety | Separates security signal from correctness noise |
| Test Reviewer | Test coverage gaps, test quality | Ensures reviewers can't be gamed by test-less PRs |
| Skeptic | Challenges the other reviewers' findings | Reduces false positives; forces citation of evidence |
| Deterministic Judge | Rule-based final decision | Fail-closed: unsafe patterns always block even if LLMs disagree |

LangGraph was chosen over a simple chain because the agents share a typed state graph,
the Skeptic node can send work back to any reviewer, and the graph is trivially ablatable
(remove a node, re-run evals, measure the delta).

---

## The evaluation system

**Why build it at all?**  LLM outputs are non-deterministic and prompt changes break things
silently.  Without a golden dataset you have no way to know if a "fix" made things worse.

- **356-case golden dataset** – hand-labelled diffs across 12 security categories.
  Split: 60 % train / 20 % dev / 20 % test.  Dev is for tuning; test is held out.
- **9 evaluation layers** – components (unit-level), integration (graph), agent smoke,
  pipeline end-to-end, robustness (prompt injection, malformed diffs), consistency
  (5-repeat Ollama), ablations (6 graph variants), regression gate, baseline comparison.
- **706 component eval cases** covering every deterministic component individually.
- **Regression gate** – after any change, the gate compares the new run against the
  committed baseline JSON.  A metric regression fails CI.
- **Ablation study** – 6 graph variants (full, single_agent, no_skeptic, no_verifier,
  no_context, no_rules) run on 212 paired dev cases.  Results committed to `evaluation.md`.

---

## Fail-closed safety philosophy

The system is designed so that **uncertainty defaults to blocking**, not passing:
- If the LLM API is unavailable → `needs_human`
- If confidence is below threshold → `needs_human`
- If any deterministic rule fires → minimum risk is `high`; decision is `unsafe` or
  `needs_human` regardless of LLM output
- **0 / 39 must-catch cases ever auto-passed** in component eval

---

## Numbers at a glance

| Metric | Value |
|---|---|
| Unit + integration tests | 294 passing |
| Component eval cases | 706 |
| Component eval pass rate | 100 % (all 9 bars) |
| Golden dataset size | 356 labelled diffs |
| Security categories | 12 |
| Evaluation layers | 9 |
| Unsafe-pass rate (must-catch) | 0 % (0 / 39) |
| Ollama live decision agreement | 100 % (8 cases × 5 repeats) |
| Ollama finding Jaccard | 0.925 |

---

## 5 strong talking points

1. **"I built the eval system before tuning the model."**  Explain that eval-first forces
   you to define success concretely, not subjectively.  You built the golden dataset,
   wrote the regression gate, then iterated on agent prompts — so every change was
   measurable.

2. **"The deterministic layer is what makes it safe."**  LLMs are good at reasoning but
   unreliable at consistency.  The rule engine provides a floor: known-bad patterns always
   block.  The LLMs add context above that floor.  Neither alone is sufficient.

3. **"I ran an ablation study to validate the agent design."**  Removing the Skeptic agent
   costs precision; removing the rules causes recall to drop 39 pp.  The study gave
   concrete justification for each node's existence — not just intuition.

4. **"Fail-closed is a deliberate architectural choice."**  Walk through the decision tree:
   every uncertainty path leads to `needs_human`, never to `safe`.  This is a security
   property, not a UX convenience.

5. **"294 tests, 706 component cases, 9 eval layers — this is production-grade
   observability on a side project."**  Explain the tradeoffs: SQLite for zero-ops
   persistence, replay mode for offline CI, Streamlit dashboard for ad-hoc analysis.
   Show that you thought about operability, not just accuracy.
