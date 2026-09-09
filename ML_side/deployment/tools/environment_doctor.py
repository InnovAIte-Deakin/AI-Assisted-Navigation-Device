"""Read-only environment inspection for candidate deployment preparation."""

from __future__ import annotations

import argparse
import json
import socket
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable

from common import DeploymentError, check, result_for, validate_nonartifact_output, write_json


TOOL_VERSION = "1.0.0"
REQUIRED_VISION_PACKAGES = ("torch", "torchvision", "ultralytics", "fastapi", "uvicorn")
OPTIONAL_FEATURE_PACKAGES = ("easyocr", "faster-whisper", "websockets", "opencv-python", "pydantic", "requests")


def _cuda_runtime(torch_module: Any | None = None) -> tuple[dict[str, object], list[dict[str, str]]]:
    try:
        import runtime_preflight
    except ImportError:
        tools_dir = Path(__file__).resolve().parents[2] / "tools"
        sys.path.insert(0, str(tools_dir))
        import runtime_preflight
    return runtime_preflight._torch_runtime(torch_module)


def _port_available(port: int, socket_factory: Callable[..., socket.socket] = socket.socket) -> bool:
    try:
        with socket_factory(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def inspect_environment(
    *,
    torch_module: Any | None = None,
    package_version: Callable[[str], str] = version,
    port: int | None = None,
    port_checker: Callable[[int], bool] = _port_available,
) -> dict[str, object]:
    packages: dict[str, dict[str, object]] = {}
    checks: list[dict[str, str]] = []
    package_specs = [(name, True) for name in REQUIRED_VISION_PACKAGES] + [
        (name, False) for name in OPTIONAL_FEATURE_PACKAGES
    ]
    for name, required in package_specs:
        try:
            installed_version = package_version(name)
        except PackageNotFoundError:
            installed_version = None
        except Exception:
            installed_version = "unknown"
        status = "pass" if installed_version else ("fail" if required else "warning")
        category = "REQUIRED FOR YOLO VISION" if required else "OPTIONAL / FEATURE-SPECIFIC"
        packages[name] = {"category": category, "version": installed_version, "installed": installed_version is not None}
        checks.append(check(f"package_{name}", status, f"{name} is installed." if installed_version else f"{name} is {'required for YOLO vision' if required else 'missing but non-blocking'}."))
    runtime, runtime_checks = _cuda_runtime(torch_module)
    checks.extend(runtime_checks)
    if port is not None:
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            checks.append(check("port", "fail", "Port must be an integer from 1 to 65535."))
        else:
            available = port_checker(port)
            checks.append(check("port", "pass" if available else "warning", "Local port is available." if available else "Local port is already in use."))
    return {
        "schema_version": "1.0.0",
        "tool": {"name": "walkbuddy_environment_doctor", "version": TOOL_VERSION},
        "python_version": sys.version.split()[0],
        "packages": packages,
        "runtime_environment": runtime,
        "checks": checks,
        "overall_result": result_for(checks),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only WalkBuddy deployment environment doctor.")
    parser.add_argument("--json-out", help="Optional JSON report path.")
    parser.add_argument("--port", type=int, help="Optionally check whether this local TCP port is available.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = inspect_environment(port=args.port)
        if args.json_out:
            write_json(validate_nonartifact_output(args.json_out), report)
    except DeploymentError as exc:
        print(f"Environment doctor failed: {exc}", file=sys.stderr)
        return 2
    print(f"Environment doctor result: {report['overall_result']}")
    return 1 if report["overall_result"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
