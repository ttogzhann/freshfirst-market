"""Private header-file checks; exporter/provider constructors are stubs, no scheduler."""

import os
from types import SimpleNamespace

import pytest

from app import telemetry


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("OTEL_", "FRESHFIRST_TELEMETRY_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://dev-otlp.example/otlp")
    monkeypatch.setenv("FRESHFIRST_TELEMETRY_ENVIRONMENT", "dev")


def private_file(tmp_path, monkeypatch, content):
    path = tmp_path / "headers"
    path.write_bytes(content)
    path.chmod(0o600)
    monkeypatch.setenv("FRESHFIRST_TELEMETRY_HEADERS_FILE", str(path))
    return path


def stub_providers(monkeypatch):
    captured = []

    def exporter(**kwargs):
        captured.append(kwargs)
        return object()

    def provider(*args, **kwargs):
        return SimpleNamespace(
            add_span_processor=lambda item: None, add_log_record_processor=lambda x: None
        )

    for name in ("OTLPSpanExporter", "OTLPMetricExporter", "OTLPLogExporter"):
        monkeypatch.setattr(telemetry, name, exporter)
    for name in ("TracerProvider", "MeterProvider", "LoggerProvider"):
        monkeypatch.setattr(telemetry, name, provider)
    for name in ("BatchSpanProcessor", "BatchLogRecordProcessor", "PeriodicExportingMetricReader"):
        monkeypatch.setattr(telemetry, name, lambda *args, **kwargs: object())
    result = object()
    monkeypatch.setattr(telemetry, "Telemetry", lambda *args: result)
    return captured, result


def test_same_explicit_decoded_headers_for_all_signals_without_environment_copy(
    tmp_path, monkeypatch
):
    private_file(
        tmp_path, monkeypatch, b"Authorization=Basic%20dummy%2Bcredential%3D,X-Scope=dev\n"
    )
    captured, expected = stub_providers(monkeypatch)
    before = dict(os.environ)
    assert telemetry.configure(object()) is expected
    assert [item["endpoint"] for item in captured] == [
        "https://dev-otlp.example/otlp/v1/traces",
        "https://dev-otlp.example/otlp/v1/metrics",
        "https://dev-otlp.example/otlp/v1/logs",
    ]
    assert all(item["headers"] is captured[0]["headers"] for item in captured)
    assert captured[0]["headers"] == {
        "authorization": "Basic dummy+credential=",
        "x-scope": "dev",
    }
    assert os.environ == before


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"Authorization=dummy\nsecond-line",
        b"Authorization=dummy%0D%0AInjected%3Ayes",
        b"Authorization=dummy%00",
        b"Authorization=dummy%FF",
        b"Authorization=dummy%2",
        b"Authorization=dummy%GG",
        b"Authorization=dummy,authorization=duplicate",
        b"Bad Header=dummy",
        b"Authorization=",
        b"missing-separator",
        b"Authorization=Basic dummy",
        b"Authorization=" + b"x" * 8192,
    ],
)
def test_malformed_file_fails_redacted_before_provider_start(
    tmp_path, monkeypatch, content, capsys, caplog
):
    path = private_file(tmp_path, monkeypatch, content)
    monkeypatch.setattr(telemetry, "TracerProvider", lambda **kw: pytest.fail("provider started"))
    with pytest.raises(
        ValueError, match="Cannot read valid private telemetry headers file"
    ) as error:
        telemetry.configure(object())
    assert error.value.__suppress_context__
    assert str(path) not in str(error.value)
    assert "dummy" not in str(error.value)
    captured = capsys.readouterr()
    assert not captured.out and not captured.err and not caplog.text


@pytest.mark.parametrize("path_kind", ["missing", "directory", "relative"])
def test_unreadable_or_invalid_path_fails_before_provider_start(tmp_path, monkeypatch, path_kind):
    path = tmp_path if path_kind == "directory" else tmp_path / "missing"
    monkeypatch.setenv(
        "FRESHFIRST_TELEMETRY_HEADERS_FILE",
        "relative-file" if path_kind == "relative" else str(path),
    )
    monkeypatch.setattr(telemetry, "TracerProvider", lambda **kw: pytest.fail("provider started"))
    with pytest.raises(ValueError, match="Cannot read valid private telemetry headers file"):
        telemetry.configure(object())


@pytest.mark.parametrize(
    "name",
    [
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
        "OTEL_EXPORTER_OTLP_METRICS_HEADERS",
        "OTEL_EXPORTER_OTLP_LOGS_HEADERS",
    ],
)
@pytest.mark.parametrize("value", ["Authorization=dummy-env-secret", ""])
def test_ambient_sdk_header_fallback_rejected_even_with_valid_file(
    tmp_path, monkeypatch, name, value
):
    private_file(tmp_path, monkeypatch, b"Authorization=Basic%20dummy-file")
    monkeypatch.setenv(name, value)
    monkeypatch.setattr(telemetry, "TracerProvider", lambda **kw: pytest.fail("provider started"))
    with pytest.raises(ValueError, match="header environment variables are unsupported") as error:
        telemetry.configure(object())
    assert "dummy-env-secret" not in str(error.value)


def test_remote_dev_without_file_fails_before_provider_start(monkeypatch):
    monkeypatch.setattr(telemetry, "TracerProvider", lambda **kw: pytest.fail("provider started"))
    with pytest.raises(ValueError, match="Remote dev telemetry requires a private headers file"):
        telemetry.configure(object())


def test_loopback_collector_still_allows_no_headers(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    captured, expected = stub_providers(monkeypatch)
    assert telemetry.configure(object()) is expected
    assert len(captured) == 3 and all(item["headers"] == {} for item in captured)


@pytest.mark.parametrize("environment", ["production", "test", "local"])
def test_private_file_cannot_be_used_for_other_environments(tmp_path, monkeypatch, environment):
    private_file(tmp_path, monkeypatch, b"Authorization=Basic%20dummy-file")
    monkeypatch.setenv("FRESHFIRST_TELEMETRY_ENVIRONMENT", environment)
    monkeypatch.setattr(telemetry, "TracerProvider", lambda **kw: pytest.fail("provider started"))
    with pytest.raises(ValueError, match="supported only for dev"):
        telemetry.configure(object())
