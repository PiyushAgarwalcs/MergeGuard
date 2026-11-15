# HTML report rendering for the sample CSV utility.
# All data-derived labels are escaped before joining the markup.

from decimal import Decimal
from html import escape


def render_html_report(totals: dict[str, Decimal]) -> str:
    """Render category totals as a small escaped HTML table."""
    rows = ["<table><thead><tr><th>Category</th><th>Total</th></tr></thead><tbody>"]
    for category in sorted(totals):
        safe_category = escape(category, quote=True)
        rows.append(f"<tr><td>{safe_category}</td><td>{totals[category]:.2f}</td></tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)
