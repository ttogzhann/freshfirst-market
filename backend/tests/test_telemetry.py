"""Isolated signals/privacy/lifecycle checks; no managed service or production data."""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import pantry, register_test_account
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app import telemetry
from app.main import create_app


@pytest.fixture(autouse=True)
def isolated_telemetry_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("OTEL_", "FRESHFIRST_TELEMETRY_")):
            monkeypatch.delenv(name)


def test_disabled_by_default_does_not_configure_exporters(service, monkeypatch):
    monkeypatch.delenv("FRESHFIRST_TELEMETRY_ENABLED", raising=False)
    monkeypatch.setattr(telemetry, "configure", lambda engine: pytest.fail("must remain disabled"))
    with TestClient(create_app(service, startup_import=False)) as client:
        assert client.get("/api/ingredients").status_code == 200
        assert not hasattr(client.app.state, "telemetry")


def test_real_routes_counters_trace_log_privacy_and_cleanup(service, monkeypatch, capsys):
    spans, logs, reader = (
        InMemorySpanExporter(),
        InMemoryLogRecordExporter(),
        InMemoryMetricReader(),
    )
    traces, meters, logger = (
        TracerProvider(),
        MeterProvider(metric_readers=[reader]),
        LoggerProvider(),
    )
    traces.add_span_processor(SimpleSpanProcessor(spans))
    logger.add_log_record_processor(SimpleLogRecordProcessor(logs))
    signals = telemetry.Telemetry(service.store.engine, traces, meters, logger)
    monkeypatch.setattr(telemetry, "configure", lambda engine: signals)
    monkeypatch.setenv("FRESHFIRST_TELEMETRY_ENABLED", "true")
    with TestClient(
        create_app(service, startup_import=False), raise_server_exceptions=False
    ) as client:
        # No successful business counters for rejected unauthenticated requests.
        assert client.post("/api/pantry", json={}).status_code == 401
        register_test_account(client, email="private@example.com", password="private-password-123")
        for ingredient, amount, unit in [
            ("pasta", 100, "g"),
            ("milk", 100, "ml"),
            ("butter", 10, "g"),
        ]:
            pantry(client, ingredient, amount, unit)
        assert client.get("/api/recipes?query=private-search").status_code == 200
        assert client.get("/api/recipes/private-recipe-id").status_code == 404
        request = {"recipe_id": "rec_test1", "servings": 1, "substitutions": []}
        assert client.post("/api/cooking/preview", json=request).status_code == 200
        assert client.post("/api/cooking/confirm", json=request).status_code == 201
        assert client.post("/api/cooking/confirm", json=request).status_code == 409
        assert client.post("/api/cooking/confirm", json={}).status_code == 422
        assert client.get("/private-unmatched-path?token=private-token").status_code == 404

        @client.app.get("/test-failure")
        def failure():
            raise RuntimeError("private-exception")

        assert client.get("/test-failure").status_code == 500
        with service.store.engine.connect() as connection, pytest.raises(DBAPIError):
            connection.execute(text("SELECT private_sql_literal FROM private_missing_table"))

        data = reader.get_metrics_data()
        metrics = {
            m.name: m for r in data.resource_metrics for s in r.scope_metrics for m in s.metrics
        }
        for name, expected in [
            ("listings.created", 3),
            ("reservations.completed", 1),
            ("reservations.failures", 2),
            ("recipes.requests", 2),
        ]:
            assert sum(p.value for p in metrics["freshfirst." + name].data.data_points) == expected
        assert "http.server.request.duration" in metrics
        finished = spans.get_finished_spans()
        db = next(s for s in finished if s.kind == trace.SpanKind.CLIENT and s.parent)
        assert any(s.context.span_id == db.parent.span_id for s in finished)
        assert any(
            s.kind == trace.SpanKind.CLIENT and s.status.status_code == trace.StatusCode.ERROR
            for s in finished
        )
        records = [r.log_record for r in logs.get_finished_logs()]
        assert records and all(r.trace_id and r.span_id for r in records)
        assert all(r.body["trace_id"] == format(r.trace_id, "032x") for r in records)
        assert any(s.context.span_id == records[0].span_id for s in finished)
        exported = repr(
            [(s.name, dict(s.attributes), s.events, s.status.description) for s in finished]
        )
        exported += repr(data) + repr([r.body for r in records])
        for secret in [
            "private@example.com",
            "private-password-123",
            "private-search",
            "private-recipe-id",
            "private-token",
            "private-unmatched-path",
            "private-exception",
            "private_sql_literal",
            "private_missing_table",
        ]:
            assert secret not in exported
        json_lines = [
            json.loads(line)
            for line in capsys.readouterr().err.splitlines()
            if line.startswith('{"event":')
        ]
        assert json_lines and all(line["trace_id"] for line in json_lines)
    count = len(spans.get_finished_spans())
    with service.store.engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    assert len(spans.get_finished_spans()) == count


def test_otlp_http_exports_all_signals_to_configured_collector(service, monkeypatch):
    received = {}

    class Collector(BaseHTTPRequestHandler):
        def do_POST(self):
            received[self.path] = self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Collector)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    monkeypatch.setenv("FRESHFIRST_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("FRESHFIRST_TELEMETRY_SAMPLE_RATIO", "1")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", f"http://127.0.0.1:{server.server_port}")
    try:
        with TestClient(create_app(service, startup_import=False)) as client:
            assert client.get("/api/ingredients").status_code == 200
        for path, message in [
            ("traces", ExportTraceServiceRequest),
            ("metrics", ExportMetricsServiceRequest),
            ("logs", ExportLogsServiceRequest),
        ]:
            decoded = message.FromString(received["/v1/" + path])
            assert decoded.ListFields()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


@pytest.mark.parametrize(
    "endpoint",
    [
        "",
        "https://user:secret@example.com",
        "https://example.com?token=x",
        "http://remote-collector.example.com",
    ],
)
def test_enabled_requires_safe_explicit_endpoint(service, monkeypatch, endpoint):
    monkeypatch.setenv("FRESHFIRST_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)
    with pytest.raises(ValueError, match="without credentials/query"):
        create_app(service, startup_import=False)


def test_exporter_outages_do_not_change_responses(service, monkeypatch):
    from opentelemetry.sdk._logs.export import LogRecordExportResult
    from opentelemetry.sdk.metrics.export import MetricExportResult
    from opentelemetry.sdk.trace.export import SpanExportResult

    calls = []
    for exporter, failure in [
        (telemetry.OTLPSpanExporter, SpanExportResult.FAILURE),
        (telemetry.OTLPMetricExporter, MetricExportResult.FAILURE),
        (telemetry.OTLPLogExporter, LogRecordExportResult.FAILURE),
    ]:

        def fail_export(self, *args, failure=failure, **kwargs):
            calls.append(type(self))
            return failure

        monkeypatch.setattr(exporter, "export", fail_export)
    monkeypatch.setenv("FRESHFIRST_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("FRESHFIRST_TELEMETRY_SAMPLE_RATIO", "1")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://collector.invalid")
    with TestClient(create_app(service, startup_import=False)) as client:
        assert (
            client.get("/api/ingredients", headers=[(b"traceparent", b"\xff")]).status_code == 200
        )
        signals = client.app.state.telemetry
        for provider in (signals.traces, signals.meters, signals.logs):
            provider.force_flush()
        assert client.get("/api/ingredients").status_code == 200
    assert set(calls) == {
        telemetry.OTLPSpanExporter,
        telemetry.OTLPMetricExporter,
        telemetry.OTLPLogExporter,
    }
