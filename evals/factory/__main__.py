# Command-line interface for building and inspecting offline dataset versions.
# All output is deterministic JSON so it can be captured in CI logs.

import argparse
import json
import sys

from evals.factory.build import build_dataset, dataset_stats, validate_dataset


def main() -> int:
    """Run one dataset factory command and return its process status."""
    parser = argparse.ArgumentParser(prog="python -m evals.factory")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "validate", "stats"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = build_dataset(args.version)
    elif args.command == "validate":
        errors = validate_dataset(args.version)
        result = {"valid": not errors, "errors": errors}
        if errors:
            print(json.dumps(result, indent=2))
            return 1
    else:
        result = dataset_stats(args.version)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
