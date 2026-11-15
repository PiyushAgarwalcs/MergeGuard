# Command-line entry point for report generation.
# Errors are reported to stderr with a non-zero process status.

import argparse
import logging
from pathlib import Path

from report_tool.config import load_settings
from report_tool.service import build_and_render

LOGGER = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the report command argument parser."""
    parser = argparse.ArgumentParser(description="Build a category total report.")
    parser.add_argument("name", help="Input CSV name without its .csv suffix")
    return parser


def main() -> int:
    """Run the report command with environment-based configuration."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = load_settings()
    arguments = create_parser().parse_args()
    try:
        report_path = build_and_render(
            settings.input_directory,
            settings.output_directory,
            arguments.name,
            settings.renderer,
        )
    except (OSError, ValueError, RuntimeError) as error:
        LOGGER.error("Report generation failed: %s", error)
        return 1
    print(Path(report_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
