# Judge calibration rubric

Use this rubric only for qualities that cannot be checked mechanically, such as reviewer-comment clarity. Do not ask a judge model to establish whether a vulnerability exists when the case has mechanical ground truth.

## Scoring

Score each reviewed sample from 1 to 5:

| Score | Meaning |
|---:|---|
| 1 | Substantially misleading, unsupported, or unusable. |
| 2 | Major omissions or unsupported claims make it hard to use. |
| 3 | Mixed quality; useful content exists but important issues remain. |
| 4 | Clear and mostly faithful, with only minor issues. |
| 5 | Clear, concise, fully supported by the verified findings, and actionable. |

Human raters should score independently before seeing the model score. A sample must include the case, the exact report being rated, and the same rubric version for both raters.

## Calibration procedure

Collect at least 40 complete paired samples in `calibration.jsonl`. Use a judge model family different from the model that produced the report. Include varied report lengths and randomized first/last presentation positions. Record the judge model, reviewed model, rubric version, and presentation position with every sample. The placeholder row in the JSONL file is ignored until it has numeric human and judge scores and all required identifiers.

Report Cohen's kappa for categorical labels and Spearman rank correlation for ordinal scores. Treat 0.6 as the initial minimum agreement target. Inspect disagreements, position bias, and length bias before using a judge score as a quality metric. Recalibrate after changing the judge model or rubric. Until 40 complete samples exist, every judge-based metric must be marked `uncalibrated`.

## JSONL fields

- `sample_id`, `case_id`: stable sample and evaluation case identifiers.
- `human_score`, `judge_score`: paired numeric scores on the same scale.
- `judge_model`, `reviewer_model`: model identifiers for the evaluator and report author.
- `rubric_version`: version label for the scoring rules.
- `evaluated_at`: UTC timestamp.
- `position`, `length_bucket`: fields for position and report-length bias checks.
- `notes`: optional human rationale or disagreement note.
