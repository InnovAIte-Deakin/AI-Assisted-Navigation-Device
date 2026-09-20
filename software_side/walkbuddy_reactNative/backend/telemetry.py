from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor


logger = logging.getLogger(__name__)

TELEMETRY_ENABLED_ENV = "WALKBUDDY_TELEMETRY_ENABLED"
OTLP_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"
DEFAULT_OTLP_ENDPOINT = "http://localhost:4317"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class TelemetryConfig:
    """Resolved telemetry settings for one backend process."""

    enabled: bool
    endpoint: str | None
    disabled_reason: str | None = None


def _parse_enabled_value(value: str) -> bool:
    """Parse an explicit telemetry setting without silently accepting typos."""

    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    accepted = ", ".join(sorted(_TRUE_VALUES | _FALSE_VALUES))
    raise ValueError(
        f"Invalid {TELEMETRY_ENABLED_ENV} value {value!r}. "
        f"Use one of: {accepted}."
    )


def _configured_endpoint(environment: Mapping[str, str]) -> str | None:
    """Return an explicitly configured OTLP endpoint, ignoring blank values."""

    endpoint = environment.get(OTLP_ENDPOINT_ENV)
    return endpoint.strip() if endpoint and endpoint.strip() else None


def resolve_telemetry_config(
    environment: Mapping[str, str] | None = None,
) -> TelemetryConfig:
    """Resolve explicit true/false and automatic local-development telemetry modes."""

    environment = os.environ if environment is None else environment
    endpoint = _configured_endpoint(environment)
    enabled_value = environment.get(TELEMETRY_ENABLED_ENV)

    if enabled_value is None:
        if endpoint:
            return TelemetryConfig(enabled=True, endpoint=endpoint)
        return TelemetryConfig(
            enabled=False,
            endpoint=None,
            disabled_reason=(
                f"auto mode: set {OTLP_ENDPOINT_ENV} or "
                f"{TELEMETRY_ENABLED_ENV}=1 to enable"
            ),
        )

    if _parse_enabled_value(enabled_value):
        return TelemetryConfig(
            enabled=True,
            endpoint=endpoint or DEFAULT_OTLP_ENDPOINT,
        )

    return TelemetryConfig(
        enabled=False,
        endpoint=None,
        disabled_reason=f"{TELEMETRY_ENABLED_ENV} is explicitly disabled",
    )


def init_telemetry(app, service_name="walkbuddy-backend") -> TelemetryConfig:
    """
    Initialise OpenTelemetry only when explicitly enabled or configured.

    Docker Compose supplies an OTLP endpoint, while direct local development
    defaults to telemetry disabled unless explicitly requested.
    """

    config = resolve_telemetry_config()
    if not config.enabled:
        logger.info("[Telemetry] Disabled (%s).", config.disabled_reason)
        return config

    # 1. Define the Resource (Service Name)
    resource = Resource.create(attributes={
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": "development"
    })

    # 2. Configure the Tracer Provider
    tracer_provider = TracerProvider(resource=resource)
    
    # 3. Configure the Exporter (Sends data to Jaeger via OTLP gRPC)
    otlp_exporter = OTLPSpanExporter(
        endpoint=config.endpoint,
        insecure=True
    )
    
    # Use BatchProcessor for better performance (sends traces in chunks)
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    
    # 4. Set the Global Tracer Provider
    # This allows 'trace.get_tracer()' to work in other files
    trace.set_tracer_provider(tracer_provider)

    # 5. Auto-Instrument HTTPX (Captures LibriVox & OSRM calls automatically)
    HTTPXClientInstrumentor().instrument()

    # 6. Instrument FastAPI
    # This captures all incoming HTTP requests to your API
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    
    logger.info("[Telemetry] OTel initialized for %s -> %s", service_name, config.endpoint)
    return config
