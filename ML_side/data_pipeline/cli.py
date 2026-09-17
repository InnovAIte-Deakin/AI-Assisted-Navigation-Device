from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .config import load_config
from .cvat_sync import sync_cvat_reviews
from .database import PipelineDatabase
from .intake import run_id_for
from .models import PipelineError, StageStatus
from .pipeline import database_path, execute
from .release import verify_release
from .reviews import import_review_csv, unresolved_review_count


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the traceable WalkBuddy dataset pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run or resume a checkpointed pipeline.")
    run.add_argument("--config", type=Path, required=True)
    review = subparsers.add_parser("review-import", help="Import signed human review decisions.")
    review.add_argument("--config", type=Path, required=True)
    review.add_argument("--csv", type=Path, required=True)
    review.add_argument("--reviewer", required=True)
    cvat_sync = subparsers.add_parser("cvat-sync", help="Import completed CVAT corrections with reviewer attribution.")
    cvat_sync.add_argument("--config", type=Path, required=True)
    cvat_sync.add_argument("--reviewer", required=True)
    status = subparsers.add_parser("status", help="Show the current run checkpoint and pending reviews.")
    status.add_argument("--config", type=Path, required=True)
    verify = subparsers.add_parser("verify", help="Verify checksums and reject unexpected release files.")
    verify.add_argument("--release-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "run":
            result = execute(args.config)
            print(json.dumps({"stage": result.stage, "status": result.status.value, "message": result.message, "metrics": result.metrics}, indent=2))
            return 0 if result.status == StageStatus.PASS else 2 if result.status == StageStatus.REVIEW_REQUIRED else 1
        if args.command == "verify":
            valid, issues = verify_release(args.release_dir.resolve())
            print(json.dumps({"valid": valid, "issues": issues}, indent=2))
            return 0 if valid else 1
        config = load_config(args.config)
        run_id = run_id_for(config, args.config)
        with PipelineDatabase(database_path(config, run_id)) as db:
            if args.command == "review-import":
                result = import_review_csv(db, run_id, config, args.csv, args.reviewer)
                print(json.dumps({"status": result.status.value, "message": result.message}, indent=2))
                return 0
            if args.command == "cvat-sync":
                result = sync_cvat_reviews(db, run_id, config, args.reviewer)
                print(json.dumps({"status": result.status.value, "message": result.message}, indent=2))
                return 0
            stages = [dict(row) for row in db.rows(
                "SELECT source_id, stage, status, message, created_at FROM stage_results WHERE run_id=? ORDER BY result_id", (run_id,)
            )]
            print(json.dumps({"run_id": run_id, "pending_reviews": unresolved_review_count(db, run_id), "stages": stages}, indent=2))
            return 0
    except (PipelineError, OSError, ValueError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, indent=2))
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
