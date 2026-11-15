# Produces a static HTML summary of the latest evaluation run per layer.
# Database reads go through the shared storage module; rendered values are escaped.

from __future__ import annotations

import html
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mergeguard.storage import connect, list_eval_runs

DEFAULT_REPORT_PATH = Path(__file__).resolve().parent / "results" / "report.html"


def render_report(runs: Sequence[Mapping[str, Any]]) -> str:
    """Render a self-contained summary page for the newest run in each layer."""
    latest_by_layer: dict[str, Mapping[str, Any]] = {}
    for run in runs:
        layer = str(run.get("layer", "unknown"))
        current = latest_by_layer.get(layer)
        if current is None or str(run.get("started_at", "")) > str(current.get("started_at", "")):
            latest_by_layer[layer] = run
    cards = "".join(_render_run(layer, run) for layer, run in sorted(latest_by_layer.items()))
    if not cards:
        cards = '<p class="empty">No evaluation runs have been saved yet.</p>'
    generated = datetime.now(UTC).isoformat(timespec="seconds")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MergeGuard evaluation report</title>
  <style>
    body {{ font: 16px system-ui, sans-serif; margin: 2rem auto; max-width: 960px; padding: 0 1rem; color: #17212b; }}
    h1 {{ margin-bottom: .25rem; }} .muted {{ color: #52616b; }}
    article {{ border: 1px solid #ccd5dc; border-radius: 8px; margin: 1rem 0; padding: 1rem; }}
    pre {{ background: #f3f6f8; overflow-wrap: anywhere; padding: 1rem; white-space: pre-wrap; }}
    .empty {{ background: #f3f6f8; padding: 1rem; }}
  </style>
</head>
<body>
  <h1>MergeGuard evaluation report</h1>
  <p class="muted">Generated {html.escape(generated)} · Latest saved run per layer</p>
  {cards}
</body>
</html>
"""


def write_static_report(
    path: Path = DEFAULT_REPORT_PATH, database_path: str | Path | None = None
) -> Path:
    """Write the latest-per-layer summary to a standalone HTML file."""
    connection = connect(database_path)
    try:
        runs = list_eval_runs(connection=connection)
    finally:
        connection.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(runs), encoding="utf-8")
    return path


def _render_run(layer: str, run: Mapping[str, Any]) -> str:
    """Build an escaped HTML card for one evaluation run."""
    summary = _parse_summary(run.get("summary"))
    metrics = html.escape(json.dumps(summary, indent=2, sort_keys=True))
    threshold_status = summary.get("thresholds_passed")
    outcome = (
        "PASS" if threshold_status is True else "FAIL" if threshold_status is False else "UNGATED"
    )
    return f"""<article>
  <h2>{html.escape(layer)} · {outcome}</h2>
  <p class="muted">Run {html.escape(str(run.get('eval_run_id', '')))} · 
  dataset {html.escape(str(run.get('dataset_version', '')))} · 
  code {html.escape(str(run.get('code_version', '')))} · 
  {html.escape(str(run.get('started_at', '')))}</p>
  <pre>{metrics}</pre>
</article>"""


def _parse_summary(value: object) -> dict[str, Any]:
    """Load a JSON summary or return an empty mapping for damaged old rows."""
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
