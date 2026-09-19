"""Read-only sustained WebSocket runtime validation for a Candidate model."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


ML_SIDE_DIR = Path(__file__).resolve().parents[1]
if str(ML_SIDE_DIR) not in sys.path:
    sys.path.insert(0, str(ML_SIDE_DIR))

from runtime_soak_lib.core import (  # noqa: E402
    RuntimeSoakError,
    SoakConfig,
    collect_nonheldout_fixtures,
    query_runtime_endpoints,
    resolve_candidate,
    run_mock_soak,
    run_protocol_soak,
)
from runtime_soak_lib.outputs import write_reports  # noqa: E402
from runtime_soak_lib.transport import WebsocketsVisionTransport  # noqa: E402
import runtime_preflight as preflight  # noqa: E402


async def run_real_soak(
    config: SoakConfig,
    *,
    base_url: str,
    fixture_dir: str | Path,
    api_key: str | None = None,
) -> dict[str, object]:
    """Validate one live Candidate runtime through the current HTTP/WS APIs."""
    candidate = resolve_candidate(config.candidate_id)
    runtime_environment, _ = preflight._torch_runtime()  # noqa: SLF001 - shared preflight device facts
    endpoints, checks = query_runtime_endpoints(
        candidate,
        base_url,
        timeout_seconds=config.timeout_seconds,
        api_key=api_key,
    )
    metrics_endpoint = endpoints.get("/ml/metrics")
    before_metrics = metrics_endpoint.get("payload") if isinstance(metrics_endpoint, Mapping) else None
    if not isinstance(before_metrics, Mapping):
        before_metrics = {}
    fixtures = collect_nonheldout_fixtures(fixture_dir)
    transport = WebsocketsVisionTransport(base_url, timeout_seconds=config.timeout_seconds)

    async def after_metrics() -> Mapping[str, object]:
        after_endpoints, _ = query_runtime_endpoints(
            candidate,
            base_url,
            timeout_seconds=config.timeout_seconds,
            api_key=api_key,
        )
        after_endpoint = after_endpoints.get("/ml/metrics")
        payload = after_endpoint.get("payload") if isinstance(after_endpoint, Mapping) else None
        return payload if isinstance(payload, Mapping) else {}

    return await run_protocol_soak(
        candidate,
        config,
        transport,
        fixtures,
        before_metrics=before_metrics,
        after_metrics=after_metrics,
        evidence_mode="real_candidate_runtime",
        real_candidate_runtime_validated=True,
        base_url=base_url,
        endpoint_checks=checks,
        fixture_provenance="controlled Candidate 1 validation split, local non-heldout fixture subset",
        runtime_environment=runtime_environment,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only Candidate runtime soak validation; not a model-performance benchmark."
    )
    parser.add_argument("--candidate", default="WB-OD-NAV-001")
    parser.add_argument("--base-url", help="Live backend HTTP base URL; required without --mock.")
    parser.add_argument("--fixture-dir", help="Local non-held-out image directory; required without --mock.")
    parser.add_argument("--frames", type=int, default=500)
    parser.add_argument("--interval-ms", type=int, default=250)
    parser.add_argument("--reconnect-every", type=int, help="Reconnect cadence; defaults to 50 for a real run and 10 for --mock.")
    parser.add_argument("--malformed-every", type=int, help="Malformed-image cadence; defaults to disabled for a real run and 10 for --mock.")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--settle-ms", type=int, default=250)
    parser.add_argument("--api-key", help="Optional X-API-Key sent only to the live backend; never written to reports.")
    parser.add_argument("--mock", action="store_true", help="Run CI-safe synthetic protocol coverage with no backend or model.")
    parser.add_argument("--out-dir", help="Optional report directory. Generated reports are never committed automatically.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = SoakConfig(
        candidate_id=args.candidate,
        frames=args.frames,
        interval_ms=args.interval_ms,
        reconnect_every=args.reconnect_every if args.reconnect_every is not None else (10 if args.mock else 50),
        malformed_every=args.malformed_every if args.malformed_every is not None else (10 if args.mock else 0),
        timeout_seconds=args.timeout_seconds,
        settle_ms=args.settle_ms,
    )
    try:
        config.validate()
        if args.mock:
            report = asyncio.run(run_mock_soak(config))
        else:
            if not args.base_url or not args.fixture_dir:
                raise RuntimeSoakError("--base-url and --fixture-dir are required unless --mock is selected.")
            report = asyncio.run(
                run_real_soak(
                    config,
                    base_url=args.base_url,
                    fixture_dir=args.fixture_dir,
                    api_key=args.api_key,
                )
            )
    except RuntimeSoakError as exc:
        print(f"Runtime soak failed: {exc}", file=sys.stderr)
        return 2
    if args.out_dir:
        try:
            json_path, markdown_path = write_reports(args.out_dir, report)
        except Exception as exc:
            print(f"Runtime soak report failed: {exc}", file=sys.stderr)
            return 2
        print(f"Wrote {json_path.name} and {markdown_path.name}")
    print(f"Runtime soak result: {report['technical_verdict']}")
    print(f"Evidence mode: {report['evidence_mode']}")
    print(f"Real Candidate runtime validated: {'YES' if report['real_candidate_runtime_validated'] else 'NO'}")
    return 0 if report["technical_verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
