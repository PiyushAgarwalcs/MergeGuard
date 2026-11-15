# mergeguard.monitoring
# Read-only summaries for shadow reviews and human feedback outcomes.

from __future__ import annotations

from typing import Any

from mergeguard.storage import connect


def shadow_report() -> dict[str, Any]:
    """Summarize shadow-mode runs and dismissal feedback by finding category."""
    connection = connect()
    try:
        shadow_runs = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT run_id FROM events WHERE kind = 'published' "
                "AND json_extract(payload, '$.status') = 'shadow' ORDER BY run_id"
            ).fetchall()
        ]
        rows = connection.execute("""SELECT findings.category AS category,
                      COUNT(*) AS shown,
                      SUM(CASE WHEN feedback.action = 'dismiss' THEN 1 ELSE 0 END) AS dismissed
               FROM findings
               LEFT JOIN feedback ON feedback.run_id = findings.run_id
                    AND feedback.finding_id = findings.finding_id
               WHERE findings.run_id IN (
                 SELECT DISTINCT run_id FROM events WHERE kind = 'published'
                   AND json_extract(payload, '$.status') = 'shadow')
               GROUP BY findings.category ORDER BY findings.category""").fetchall()
        categories = [
            {
                "category": row["category"] or "unknown",
                "shown": row["shown"],
                "dismissed": row["dismissed"] or 0,
                "dismissal_rate": (row["dismissed"] or 0) / row["shown"] if row["shown"] else 0.0,
            }
            for row in rows
        ]
        approvals = [
            dict(row)
            for row in connection.execute(
                """SELECT feedback.run_id, runs.repo, runs.pr_number, feedback.by_user,
                      feedback.reason, feedback.ts, feedback.action
               FROM feedback JOIN runs ON runs.run_id = feedback.run_id
               WHERE runs.outcome = 'block' AND feedback.action IN ('approve', 'override')
               ORDER BY feedback.ts DESC"""
            ).fetchall()
        ]
        return {
            "shadow_run_count": len(shadow_runs),
            "categories": categories,
            "approve_after_block": approvals,
        }
    finally:
        connection.close()


__all__ = ["shadow_report"]
