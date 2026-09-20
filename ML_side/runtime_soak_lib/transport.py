"""Optional real WebSocket transport for Candidate runtime soak validation."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from .core import RuntimeSoakError, TransportDisconnected, VisionConnection, VisionTransport


def websocket_url(base_url: str) -> str:
    """Translate an HTTP backend base URL to its established vision endpoint."""
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment:
        raise RuntimeSoakError("--base-url must be a plain http(s) backend URL.")
    scheme = "wss" if parsed.scheme == "https" else "ws"
    path = parsed.path.rstrip("/") + "/ws/vision"
    return urlunsplit((scheme, parsed.netloc, path, "", ""))


class _WebsocketsConnection:
    def __init__(self, connection: object) -> None:
        self._connection = connection

    async def send_text(self, message: str) -> None:
        try:
            await self._connection.send(message)  # type: ignore[attr-defined]
        except Exception as exc:
            raise TransportDisconnected("WebSocket send failed.") from exc

    async def send_bytes(self, payload: bytes) -> None:
        try:
            await self._connection.send(payload)  # type: ignore[attr-defined]
        except Exception as exc:
            raise TransportDisconnected("WebSocket send failed.") from exc

    async def receive_text(self) -> str:
        try:
            response = await self._connection.recv()  # type: ignore[attr-defined]
        except Exception as exc:
            raise TransportDisconnected("WebSocket receive failed.") from exc
        if not isinstance(response, str):
            raise TransportDisconnected("WebSocket returned an unexpected binary response.")
        return response

    async def close(self) -> None:
        try:
            await self._connection.close()  # type: ignore[attr-defined]
        except Exception:
            # Closing a peer that has already closed is an expected lifecycle event.
            return


class WebsocketsVisionTransport:
    """Real transport, imported only for an explicitly requested live soak."""

    def __init__(self, base_url: str, *, timeout_seconds: float) -> None:
        self._url = websocket_url(base_url)
        self._timeout_seconds = timeout_seconds

    async def connect(self) -> VisionConnection:
        try:
            import websockets
        except ImportError as exc:
            raise RuntimeSoakError(
                "Real WebSocket soak requires the optional 'websockets' package; use --mock for CI-safe validation."
            ) from exc
        try:
            connection = await websockets.connect(
                self._url,
                open_timeout=self._timeout_seconds,
                close_timeout=self._timeout_seconds,
            )
        except Exception as exc:
            raise TransportDisconnected("WebSocket connection failed.") from exc
        return _WebsocketsConnection(connection)
