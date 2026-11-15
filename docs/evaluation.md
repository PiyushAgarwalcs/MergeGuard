# Evaluation

## Phase 6 ablations (stub)

Ran 212 paired development cases across 6 variants for 1 repeat(s).

| Variant | Finding recall | Precision | Unsafe-pass | Cost USD/PR | Median latency (s) | Incomplete |
|---|---:|---:|---:|---:|---:|---:|
| full | 0.451 | 0.687 | 0.000 | 0.000 | 0.0589 | 0 |
| single_agent | 0.451 | 0.687 | 0.000 | 0.000 | 0.0389 | 0 |
| no_skeptic | 0.451 | 0.687 | 0.000 | 0.000 | 0.0583 | 0 |
| no_verifier | 0.451 | 0.687 | 0.000 | 0.000 | 0.0586 | 0 |
| no_context | 0.451 | 0.687 | 0.000 | 0.000 | 0.0450 | 0 |
| no_rules | 0.000 | 1.000 | 0.000 | 0.000 | 0.0582 | 0 |

### Paired differences versus full design

Differences are candidate minus full; positive latency means the ablation is slower. Intervals are paired bootstrap 95% percentile intervals (1,000 resamples, seed 42). Stub cost is zero and latency reflects local graph execution only.

CI is missing in this offline dataset run, so the judge returns needs_human for clean cases. The zero unsafe-pass rate is a safe fallback outcome; these decisions do not establish decision accuracy or live-model quality.

| Variant | Metric | Difference | 95% interval |
|---|---|---:|---:|
| single_agent | finding_recall | 0.0000 | [0.0000, 0.0000] |
| single_agent | precision | 0.0000 | [0.0000, 0.0000] |
| single_agent | unsafe_pass_rate | 0.0000 | [0.0000, 0.0000] |
| single_agent | cost_usd_per_pr | 0.0000 | [0.0000, 0.0000] |
| single_agent | latency_seconds | -0.0208 | [-0.0233, -0.0186] |
| no_skeptic | finding_recall | 0.0000 | [0.0000, 0.0000] |
| no_skeptic | precision | 0.0000 | [0.0000, 0.0000] |
| no_skeptic | unsafe_pass_rate | 0.0000 | [0.0000, 0.0000] |
| no_skeptic | cost_usd_per_pr | 0.0000 | [0.0000, 0.0000] |
| no_skeptic | latency_seconds | -0.0012 | [-0.0039, 0.0014] |
| no_verifier | finding_recall | 0.0000 | [0.0000, 0.0000] |
| no_verifier | precision | 0.0000 | [0.0000, 0.0000] |
| no_verifier | unsafe_pass_rate | 0.0000 | [0.0000, 0.0000] |
| no_verifier | cost_usd_per_pr | 0.0000 | [0.0000, 0.0000] |
| no_verifier | latency_seconds | 0.0012 | [-0.0018, 0.0042] |
| no_context | finding_recall | 0.0000 | [0.0000, 0.0000] |
| no_context | precision | 0.0000 | [0.0000, 0.0000] |
| no_context | unsafe_pass_rate | 0.0000 | [0.0000, 0.0000] |
| no_context | cost_usd_per_pr | 0.0000 | [0.0000, 0.0000] |
| no_context | latency_seconds | -0.0132 | [-0.0158, -0.0100] |
| no_rules | finding_recall | -0.3892 | [-0.4599, -0.3255] |
| no_rules | precision | 0.1226 | [0.0802, 0.1651] |
| no_rules | unsafe_pass_rate | 0.0000 | [0.0000, 0.0000] |
| no_rules | cost_usd_per_pr | 0.0000 | [0.0000, 0.0000] |
| no_rules | latency_seconds | -0.0014 | [-0.0039, 0.0008] |

On these stub measurements, the single agent matches the full team on finding recall, precision and unsafe-pass rate. This is not a live-model comparison; the offline scripted reviewers return empty findings, so the deterministic scanner drives detections.
