"""CLI for deterministic, read-only deployment-manifest diagnostics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import DeploymentError, result_for, validate_nonartifact_output, write_json
from manifest import load_manifest, validate_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a portable WalkBuddy deployment manifest.")
    parser.add_argument("manifest")
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)
    try:
        payload, path = load_manifest(args.manifest)
        checks = validate_manifest(payload)
        report = {"schema_version": "1.0.0", "manifest": str(path), "checks": checks, "overall_result": result_for(checks)}
        if args.json_out:
            write_json(validate_nonartifact_output(args.json_out), report)
    except DeploymentError as exc:
        print(f"Manifest validation failed: {exc}", file=sys.stderr)
        return 2
    for item in checks:
        print(f"{item['status'].upper():11} {item['name']}: {item['detail']}")
    return 1 if report["overall_result"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
