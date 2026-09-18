"""CLI entry point for read-only WalkBuddy ML release readiness checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
if str(ML_SIDE_DIR) not in sys.path:
    sys.path.insert(0, str(ML_SIDE_DIR))

from release_readiness_lib.core import ReleaseReadinessError, run_release_readiness  # noqa: E402
from release_readiness_lib.outputs import write_reports  # noqa: E402
from common import DeploymentError  # noqa: E402


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only WalkBuddy ML release readiness and handover verification.")
    parser.add_argument("--candidate", required=True, help="Model registry candidate ID, for example WB-OD-NAV-001.")
    parser.add_argument("--out-dir", help="Optional directory for release_readiness.json and release_readiness.md.")
    parser.add_argument("--live-base-url", help="Optional backend base URL for /ml/model-info, /ml/ready, and /ml/health checks.")
    parser.add_argument("--api-key", help="Optional X-API-Key for live requests; it is never written to reports.")
    parser.add_argument("--timeout-seconds", type=float, default=5.0, help="Live request timeout (default: 5).")
    parser.add_argument("--repository-root", help="Repository root override for controlled test or handover use.")
    parser.add_argument("--manifest", help="Optional candidate deployment-manifest override.")
    parser.add_argument("--benchmark-evidence", help="Optional formal benchmark JSON override.")
    parser.add_argument("--acceptance-evidence", help="Optional runtime/safety acceptance JSON override.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_release_readiness(
            args.candidate,
            repository_root=args.repository_root or ML_SIDE_DIR.parent,
            manifest_path=args.manifest,
            benchmark_path=args.benchmark_evidence,
            acceptance_path=args.acceptance_evidence,
            live_base_url=args.live_base_url,
            api_key=args.api_key,
            timeout_seconds=args.timeout_seconds,
        )
        if args.out_dir:
            write_reports(args.out_dir, report)
    except (ReleaseReadinessError, DeploymentError) as exc:
        print(f"Release readiness failed: {exc}", file=sys.stderr)
        return 2
    print(f"WalkBuddy ML Release Readiness: {report['technical_readiness']}")
    print(f"Candidate: {report['candidate']['candidate_id']}")
    print(f"Lifecycle state: {report['lifecycle_state']}")
    print(f"Production authorization: {report['production_authorization']}")
    return 0 if report["technical_readiness"] in {"PASS", "WARNING"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
