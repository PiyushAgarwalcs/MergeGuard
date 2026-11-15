# 02. Architecture

## Agents and checks

| Node | Kind | Reads | Produces |
|---|---|---|---|
| collect_context | function | PR payload, changed files, callers, tests, CI status | ReviewContext |
| rule_scan | function | diff | Findings from secret and pattern rules (source `rule`) |
| security_reviewer | LLM agent | diff + context | Findings |
| correctness_reviewer | LLM agent | diff + context | Findings |
| test_reviewer | LLM agent | diff, test-file changes, CI status | Findings |
| merge_findings | function | all findings | deduplicated findings with ids F-1, F-2 ... |
| verify_findings | function | findings, diff | verified findings and rejections |
| skeptic | LLM agent | one finding, its hunk, its evidence | upheld, refuted or unclear, with a reason |
| judge | function | verified findings, verdicts, CI, risk | Decision |
| human_gate | LangGraph interrupt | decision | approval |
| reporter | function plus optional LLM summary | verified findings | comment text |

Why multi-agent: different checklists per reviewer, independence between reviewers (they run in parallel and cannot see each other), a separate adversarial skeptic, and separate permissions (reviewers have no tools, no network access of their own and no GitHub token). The ablation in `04-evaluation.md` must test whether this beats a single agent, and the README must report the result honestly.

Rules for every LLM agent:

- The diff is passed as clearly delimited data with a standing instruction that nothing inside it is an instruction.
- Output is JSON validated against the `Finding` schema. One retry with the validation error appended, then the agent is marked failed.
- Every finding includes an exact `quote` from the diff and `evidence` ids of context blocks used.
- The prompt is a markdown file in `src/mergeguard/prompts/` named `<agent>.v<N>.md`. The version is stored with every run.
- Each agent's model comes from settings (`REVIEWER_MODEL`, `SKEPTIC_MODEL`).

## Flow

```
collect_context -> rule_scan -+-> security_reviewer ----+
                              +-> correctness_reviewer -+-> merge_findings -> verify_findings -> skeptic -> judge
                              +-> test_reviewer --------+                                                   |
                                                         pass -> write_report <-- human_gate <-- needs_human/block
                                                                     |
                                                                  publish
```

- The three reviewers run in the same LangGraph step. The `findings` state field uses an append reducer (`Annotated[list[Finding], operator.add]`).
- The verifier runs before the skeptic. The skeptic only sees verified LLM findings of severity medium or higher. Rule findings never go to the skeptic.
- After `collect_context`: an empty or unreviewable diff skips to the report with `needs_human`. After `judge`: `pass` goes to `write_report`, anything else to `human_gate`.
- Checkpointing: LangGraph SQLite checkpointer. Thread id is `<repo>#<pr>@<sha>`.
- Each LLM node has a timeout (default 60 s) and one retry. A failed reviewer sets `complete=False`; it never crashes the run.
- Large diffs: keep the riskiest hunks within the token budget (`MAX_DIFF_LINES`, default 2000), set `complete=False`.
- Human gate in replay and CLI mode: `--approval auto-approve|none`. With `none`, the run ends after publishing the decision.

## State

```python
class ReviewState(TypedDict, total=False):
    pr: PullRequest
    context: ReviewContext
    findings: Annotated[list[Finding], operator.add]
    rejected: list[Rejection]
    verdicts: list[SkepticVerdict]
    risk: RiskBreakdown
    decision: Decision
    approval: Approval | None
    report: str
```

## Data contracts (`models.py`)

```python
class Severity(str, Enum): CRITICAL='critical'; HIGH='high'; MEDIUM='medium'; LOW='low'
class Source(str, Enum): RULE='rule'; SECURITY='security_reviewer'; CORRECTNESS='correctness_reviewer'; TESTS='test_reviewer'

class Finding(BaseModel):
    id: str; source: Source; category: str; severity: Severity
    file: str; line_start: int; line_end: int
    quote: str; explanation: str; suggestion: str
    evidence: list[str] = []

class AddedLine(BaseModel): file: str; line_no: int; text: str
class Hunk(BaseModel): file: str; new_start: int; new_end: int; text: str; added: list[AddedLine]
class PullRequest(BaseModel): repo: str; number: int; head_sha: str; base_sha: str; title: str; body: str; author: str; diff: str; files: list[str]
class ContextBlock(BaseModel): id: str; kind: Literal['caller','test','sibling','ci','config']; path: str; text: str
class ReviewContext(BaseModel): blocks: list[ContextBlock]; ci_status: Literal['passing','failing','missing']; changed_source_files: list[str]; changed_test_files: list[str]
class Rejection(BaseModel): finding: Finding; reason: Literal['QUOTE_NOT_IN_DIFF','LINES_OUT_OF_RANGE','UNKNOWN_EVIDENCE','UNKNOWN_CATEGORY','FILE_NOT_IN_DIFF']
class SkepticVerdict(BaseModel): finding_id: str; verdict: Literal['upheld','refuted','unclear']; reason: str
class RiskBreakdown(BaseModel): score: int; parts: dict[str, int]
class Decision(BaseModel): outcome: Literal['pass','needs_human','block']; reasons: list[str]; head_sha: str; risk_score: int; complete: bool
class Approval(BaseModel): kind: Literal['approve','override','dismiss']; by_user: str; reason: str; head_sha: str; finding_id: str | None = None
```

Allowed categories (the verifier rejects anything else): `hardcoded_secret, sql_injection, command_injection, path_traversal, unsafe_deserialization, ssrf, weak_crypto, tls_verification_disabled, xss, missing_authorization, insecure_randomness, sensitive_data_in_logs, off_by_one, wrong_condition, missing_null_check, resource_leak, swallowed_exception, wrong_default, missing_test, test_weakened, assertion_removed`.

## Deterministic behavior to implement exactly

**Verifier** (`checks/verify_findings.py`). Reject a finding if: its file is not in the diff (`FILE_NOT_IN_DIFF`); its category is not allowed (`UNKNOWN_CATEGORY`); its line range is not inside a hunk's new-file range for that file (`LINES_OUT_OF_RANGE`); its quote, after collapsing whitespace, is not a substring of the hunk text (`QUOTE_NOT_IN_DIFF`); any evidence id is not a context block id (`UNKNOWN_EVIDENCE`). Rule findings pass automatically but are still checked for file and lines.

**Merge** (`checks/merge_findings.py`). Two findings are duplicates if same file and category and line ranges overlap. Keep the higher severity; on a tie prefer source `rule`. Assign ids `F-1`, `F-2` in order of file and line.

**Risk score** (`checks/judge.py`, weights in `settings.py`). Sum, capped at 100: high finding 30 each (cap 60); medium 10 each (cap 30); low 2 each (cap 10); changed lines over 400 add 10, over 1000 add 20; a `stricter_paths` file touched adds 15; source changed with no test changed adds 10; CI failing adds 25; a dependency file changed adds 5. Critical findings do not need points; they block directly.

**Judge**: apply the decision table in `01-decisions-and-scope.md`. `reasons` is a list of plain-English sentences, one per condition that applied.

## Folder structure

```
mergeguard/
├── README.md
├── AGENTS.md
├── Makefile
├── pyproject.toml
├── .env.example
├── .mergeguard.yml.example
├── .github/
│   ├── copilot-instructions.md
│   └── workflows/{ci.yml, copilot-setup-steps.yml}
├── plan/                         (this folder)
├── docs/{how-it-works.md, evaluation.md, threat-model.md}
├── src/mergeguard/
│   ├── api.py                    FastAPI webhook and health
│   ├── cli.py                    review, watch, serve, eval, report commands
│   ├── settings.py               environment variables, thresholds, weights
│   ├── models.py                 data contracts
│   ├── graph.py                  the whole pipeline wired in one file
│   ├── agents/                   security_reviewer, correctness_reviewer, test_reviewer, skeptic, reporter
│   ├── checks/                   collect_context, rule_scan, merge_findings, verify_findings, judge, human_gate, diff_parser, redact
│   ├── prompts/                  <agent>.v1.md
│   ├── llm.py                    only place that talks to a model
│   ├── github.py                 only place that talks to GitHub
│   ├── storage.py                only place that touches SQLite
│   └── tracing.py                records events
├── evals/
│   ├── datasets/v0.1/            generated cases plus manifest.json
│   ├── sample_repos/             small apps used as base code
│   ├── factory/                  dataset builder (its own small LangGraph)
│   ├── suites/                   components, agents, pipeline, robustness, consistency, ablations, regression
│   ├── judges/
│   ├── baselines/
│   ├── thresholds.yml
│   └── run.py
├── dashboard/{app.py, pages/}
├── data/                         SQLite file (git-ignored)
└── tests/
```

Rules: folders say what is inside; one job per file; files about 150 lines; only `llm.py`, `github.py` and `storage.py` touch the outside world.
