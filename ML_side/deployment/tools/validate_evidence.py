"""CLI wrapper for deployment-readiness evidence validation."""

from __future__ import annotations

import argparse
import sys

from common import DeploymentError
from evidence import load_and_validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate deployment-readiness evidence JSON.")
    parser.add_argument("evidence")
    args = parser.parse_args(argv)
    try:
        errors = load_and_validate(args.evidence)
    except DeploymentError as exc:
        print(f"Evidence validation failed: {exc}", file=sys.stderr)
        return 2
    if errors:
        print("Evidence validation failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print("Evidence validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
