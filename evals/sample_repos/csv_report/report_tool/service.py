# Report generation orchestration.
# Input names are validated and report output is written atomically.

import logging
import os
from pathlib import Path

from report_tool.aggregate import format_report, totals_by_category
from report_tool.csv_data import read_rows
from report_tool.paths import contained_path, ensure_directory
from report_tool.renderer import render

LOGGER = logging.getLogger(__name__)


def build_report(input_directory: Path, output_directory: Path, name: str) -> Path:
    """Generate and return a category report for one CSV input."""
    source = contained_path(input_directory, name, ".csv")
    destination_root = ensure_directory(output_directory)
    destination = contained_path(destination_root, name, ".report.csv")
    rows = read_rows(source)
    report = format_report(totals_by_category(rows))
    temporary = destination.with_suffix(".tmp")
    try:
        temporary.write_text(report, encoding="utf-8", newline="")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    LOGGER.info("Generated report %s from %d rows.", destination.name, len(rows))
    return destination


def build_and_render(
    input_directory: Path, output_directory: Path, name: str, renderer: str
) -> Path:
    """Generate a report and optionally invoke its configured renderer."""
    report_path = build_report(input_directory, output_directory, name)
    render(renderer, report_path)
    return report_path
