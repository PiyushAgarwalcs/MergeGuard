# Report aggregation by category.
# Decimal arithmetic avoids introducing binary rounding into totals.

import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import StringIO


def totals_by_category(rows: list[dict[str, str]]) -> dict[str, Decimal]:
    """Aggregate valid amount strings by their category."""
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in rows:
        category = row["category"].strip()
        try:
            amount = Decimal(row["amount"])
        except InvalidOperation as error:
            raise ValueError(f"Invalid amount for category {category}.") from error
        if not amount.is_finite():
            raise ValueError(f"Non-finite amount for category {category}.")
        totals[category] += amount
    return dict(totals)


def format_report(totals: dict[str, Decimal]) -> str:
    """Format categories deterministically for stable reports."""
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["category", "total"])
    for category in sorted(totals):
        writer.writerow([_safe_category(category), f"{totals[category]:.2f}"])
    return output.getvalue()


def _safe_category(category: str) -> str:
    """Prevent spreadsheet software from evaluating category text as a formula."""
    if category.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{category}"
    return category
