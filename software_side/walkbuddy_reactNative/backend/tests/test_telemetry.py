"""Focused tests for optional OpenTelemetry configuration and initialisation."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import telemetry


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("YES", True),
        ("On", True),
        ("0", False),
        ("false", False),
        ("NO", False),
        ("Off", False),
    ],
)
def test_parse_enabled_value_accepts_common_boolean_forms(value, expected):
    assert telemetry._parse_enabled_value(value) is expected


def test_resolve_config_defaults_to_disabled_without_telemetry_environment():
    config = telemetry.resolve_telemetry_config({})

    assert config.enabled is False
    assert config.endpoint is None
    assert config.disabled_reason is not None


def test_explicit_false_disables_telemetry_even_when_endpoint_is_configured():
    config = telemetry.resolve_telemetry_config(
        {
            "WALKBUDDY_TELEMETRY_ENABLED": "false",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4317",
        }
    )

    assert config.enabled is False
    assert config.endpoint is None


def test_explicit_true_uses_configured_endpoint():
    config = telemetry.resolve_telemetry_config(
        {
            "WALKBUDDY_TELEMETRY_ENABLED": "true",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4317",
        }
    )

    assert config.enabled is True
    assert config.endpoint == "http://collector:4317"


def test_explicit_true_uses_localhost_fallback_without_endpoint():
    config = telemetry.resolve_telemetry_config(
        {"WALKBUDDY_TELEMETRY_ENABLED": "1"}
    )

    assert config.enabled is True
    assert config.endpoint == "http://localhost:4317"


def test_configured_endpoint_enables_auto_mode():
    config = telemetry.resolve_telemetry_config(
        {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://jaeger:4317"}
    )

    assert config.enabled is True
    assert config.endpoint == "http://jaeger:4317"


def test_invalid_explicit_enable_value_fails_clearly():
    with pytest.raises(ValueError, match="Invalid WALKBUDDY_TELEMETRY_ENABLED"):
        telemetry.resolve_telemetry_config(
            {"WALKBUDDY_TELEMETRY_ENABLED": "sometimes"}
        )


def test_disabled_init_skips_exporter_and_instrumentation(monkeypatch, caplog):
    exporter = Mock()
    httpx_instrumentor = Mock()
    fastapi_instrumentor = Mock()
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", exporter)
    monkeypatch.setattr(telemetry, "HTTPXClientInstrumentor", httpx_instrumentor)
    monkeypatch.setattr(telemetry, "FastAPIInstrumentor", fastapi_instrumentor)
    monkeypatch.delenv("WALKBUDDY_TELEMETRY_ENABLED", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    with caplog.at_level(logging.INFO, logger="telemetry"):
        config = telemetry.init_telemetry(app=object())

    assert config.enabled is False
    exporter.assert_not_called()
    httpx_instrumentor.assert_not_called()
    fastapi_instrumentor.instrument_app.assert_not_called()
    assert "[Telemetry] Disabled" in caplog.text


def test_enabled_init_configures_exporter_and_instrumentation(monkeypatch):
    resource = object()
    provider = Mock()
    processor = object()
    exporter = Mock()
    resource_factory = SimpleNamespace(create=Mock(return_value=resource))
    provider_factory = Mock(return_value=provider)
    processor_factory = Mock(return_value=processor)
    httpx_instance = Mock()
    httpx_instrumentor = Mock(return_value=httpx_instance)
    fastapi_instrumentor = SimpleNamespace(instrument_app=Mock())
    trace_api = SimpleNamespace(set_tracer_provider=Mock())

    monkeypatch.setattr(telemetry, "Resource", resource_factory)
    monkeypatch.setattr(telemetry, "TracerProvider", provider_factory)
    monkeypatch.setattr(telemetry, "BatchSpanProcessor", processor_factory)
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", exporter)
    monkeypatch.setattr(telemetry, "HTTPXClientInstrumentor", httpx_instrumentor)
    monkeypatch.setattr(telemetry, "FastAPIInstrumentor", fastapi_instrumentor)
    monkeypatch.setattr(telemetry, "trace", trace_api)
    monkeypatch.setenv("WALKBUDDY_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")

    app = object()
    config = telemetry.init_telemetry(app=app)

    assert config.enabled is True
    assert config.endpoint == "http://collector:4317"
    exporter.assert_called_once_with(endpoint="http://collector:4317", insecure=True)
    processor_factory.assert_called_once_with(exporter.return_value)
    provider.add_span_processor.assert_called_once_with(processor)
    trace_api.set_tracer_provider.assert_called_once_with(provider)
    httpx_instance.instrument.assert_called_once_with()
    fastapi_instrumentor.instrument_app.assert_called_once_with(
        app, tracer_provider=provider
    )
