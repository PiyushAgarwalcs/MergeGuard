# CSV input parsing and validation.
# The parser rejects malformed rows instead of silently shifting columns.

import csv
from pathlib import Path

REQUIRED_COLUMNS = {"category", "amount"}


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read CSV rows and validate required columns and amounts."""
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError("CSV requires category and amount columns.")
        rows = list(reader)
    if not rows:
        raise ValueError("CSV must contain at least one data row.")
    for row_number, row in enumerate(rows, start=2):
        if None in row or not row.get("category", "").strip():
            raise ValueError(f"Invalid columns or category on row {row_number}.")
        try:
            float(row["amount"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid amount on row {row_number}.") from error
    return rows


def total_amount(rows: list[dict[str, str]]) -> float:
    """Sum amounts from rows already validated by read_rows."""
    return sum(float(row["amount"]) for row in rows)
