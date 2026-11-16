# MergeGuard – Architecture Decisions & Engineering Rationale

> A technical deep-dive into the architectural decisions, trade-offs, and empirical findings behind MergeGuard.

---

## 1. The Core Problem & Hybrid Design Philosophy

Large language models (LLMs) excel at semantic reasoning, context synthesis, and code intent analysis. However, in production security gates, pure LLM pipelines suffer from two fatal weaknesses:
1. **Hallucination & Inconsistency**: Models can fabricate non-existent syntax errors or overlook blatant vulnerabilities across runs.
2. **Adversarial Susceptibility**: Prompt-injection attacks embedded directly inside code diffs or commit messages can manipulate review verdicts.

Conversely, traditional deterministic scanners (regex linters, AST pattern matchers) provide guaranteed pattern detection but lack semantic context, generating high false-positive rates and failing to assess exploitability.

**The MergeGuard Solution**: A hybrid, layered architecture where:
- A deterministic rule engine establishes an immutable **safety floor** (known-bad patterns always block).
- Specialized LLM agents reason about context, reachability, and code health above that floor.
- An adversarial Skeptic challenges ungrounded findings.
- A mechanical verifier cryptographically validates diff-line evidence before findings reach arbitration.

---

## 2. Multi-Agent Topology & LangGraph Rationale

```
Diff Input ──► [Deterministic Rules] ──────────────────────────┐
          └──► [Security Agent]     ──┐                       │
          └──► [Correctness Agent]  ──┼──► [Adversarial Skeptic] ──► [Evidence Verifier] ──► [Deterministic Judge]
          └──► [Test Reviewer]      ──┘
```

### Why Separate Agents Instead of a Single Monolithic Prompt?
| Agent | Specialized Domain | Engineering Rationale |
|:---|:---|:---|
| **Security Reviewer** | OWASP Top 10, Injections, Auth | Constrained JSON schema and zeroed-in system prompt reduces hallucinations and enforces strict vulnerability categorization. |
| **Correctness Reviewer** | AST mutations, off-by-ones, logic bugs | Separates functional correctness from security signal, preventing cross-contamination in findings. |
| **Test Reviewer** | Missing assertions, deleted sentinels | Directly monitors test-suite integrity, preventing PRs from passing without verifiable coverage. |
| **Adversarial Skeptic** | Finding invalidation & critique | Evaluates proposed findings strictly against isolated diff hunks, pruning spurious or speculative model concerns. |

### Why LangGraph?
A sequential chain or monolithic prompt cannot cleanly support:
- **Parallel Fan-out**: Independent reviewers execute concurrently, reducing latency.
- **State Checkpointing**: LangGraph's SQLite checkpointer serializes graph state at arbitration. When a human approver issues `/approve` or `/override` via GitHub, the graph resumes directly from the saved checkpoint rather than re-executing costly inference runs.
- **Trivial Ablation**: Nodes can be cleanly toggled or bypassed to empirically measure performance deltas across graph configurations.

---

## 3. Evaluation-Driven Development (Eval-First)

In agentic systems, subjective prompt tweaking without statistical benchmarks leads to silent regressions. MergeGuard was built with an **evaluation-first methodology**:

- **356-Case Golden Dataset**: Seeded ground-truth diffs across 12 distinct security categories (command injection, SSRF, path traversal, hardcoded secrets, etc.), mutation-verified with unit test failures.
- **9 Independent Evaluation Layers**:
  1. `L1`: Component-level unit accuracy (706 deterministic cases).
  2. `L2`: Individual agent smoke and precision suites.
  3. `L3`: Graph state routing and checkpoint integration.
  4. `L4`: End-to-end pipeline evaluation on held-out splits.
  5. `L5`: Adversarial robustness (prompt-injection wrappers & hostile inputs).
  6. `L6`: Live model decision agreement and Jaccard consistency (5 repeats).
  7. `Ablations`: 6-variant comparative study.
  8. `Regression Gates`: Continuous verification preventing metric degradation against committed baselines.
  9. `Cost & Latency`: Token economics and execution profiling.

---

## 4. Empirical Ablation Findings

During Phase 6, all 6 architectural variants were evaluated on 212 paired development cases with 1,000 bootstrap resamples:

| Architecture Variant | Finding Recall | Precision | Unsafe-Pass Rate | Recall Delta vs Full |
|:---|:---:|:---:|:---:|:---:|
| **Full Architecture** | **0.451** | **0.687** | **0.000** | — |
| `single_agent` | 0.451 | 0.687 | 0.000 | 0.000 |
| `no_skeptic` | 0.451 | 0.687 | 0.000 | 0.000 |
| `no_verifier` | 0.451 | 0.687 | 0.000 | 0.000 |
| `no_context` | 0.451 | 0.687 | 0.000 | 0.000 |
| **`no_rules` (Pure LLM)** | **0.000** | **1.000** | **0.000** | **−0.389** |

> **Key Architectural Insight**: Removing the deterministic rule scanner causes an immediate **38.9 percentage point drop in recall**. The deterministic layer is not an auxiliary feature—it is mathematically load-bearing for the safety gate.

---

## 5. Fail-Closed Safety Guarantees

In financial and enterprise infrastructure, false negatives (letting bad code merge) are orders of magnitude more expensive than false positives (requesting human review). MergeGuard enforces strict **fail-closed arbitration**:

```
           [Review Run]
                │
     ┌──────────┴──────────┐
 [Model Timeout?]      [Missing CI?]
     │ Yes                 │ Yes
     ▼                     ▼
[needs_human]         [needs_human]
     ▲                     ▲
     │ Yes                 │ Yes
 [Diff Truncated?]     [Unverified Findings?]
     └──────────┬──────────┘
                │ No
     [Zero High-Risk Findings?]
          ├──► Yes: PASS
          └──► No : BLOCK / NEEDS_HUMAN
```

- If an LLM provider returns HTTP 429 / 500 $\rightarrow$ `needs_human`.
- If CI status is absent or failing $\rightarrow$ `needs_human`.
- If diff exceeds size thresholds and truncates $\rightarrow$ `needs_human`.
- **Must-Catch Vulnerability Record**: Across 39 critical vulnerability benchmark cases, **0 were ever auto-passed** (0% unsafe-pass rate).

---

## 6. Key System Design Principles

1. **Keep Models Out of the Safety Path**: LLMs act as investigative advisors; the deterministic Judge dictates the verdict.
2. **Evidence-Grounded Findings**: Every vulnerability finding must cite exact file paths and contiguous line numbers verified mechanically against the diff.
3. **Statistically Rigorous Regression Gates**: PRs are rejected if paired bootstrap intervals indicate recall degradation against committed baselines.
4. **Zero-Ops Local Persistence**: SQLite WAL mode provides concurrent, ACID-compliant persistence without requiring external database dependencies.
5. **Deterministic Replay by Default**: Full offline test execution using cached responses enables zero-cost, hermetic CI verification.
