"""Stable public error payloads for vision-runtime operational failures."""

from __future__ import annotations


def model_unavailable_error() -> dict[str, dict[str, str]]:
    """Return the public response when the vision model is not ready."""
    return {
        "error": {
            "code": "model_unavailable",
            "message": "Vision model is unavailable.",
        }
    }


def inference_failed_error() -> dict[str, dict[str, str]]:
    """Return the public response when vision inference fails."""
    return {
        "error": {
            "code": "inference_failed",
            "message": "Vision inference failed.",
        }
    }


def websocket_error_payload(code: str, frame_id: str | None) -> dict[str, str | None]:
    """Return a WebSocket-safe version of a known vision-runtime error."""
    errors = {
        "model_unavailable": "Vision model is unavailable.",
        "inference_failed": "Vision inference failed.",
    }
    return {
        "type": "error",
        "code": code,
        "frame_id": frame_id,
        "message": errors[code],
    }
