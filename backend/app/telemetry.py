"""Opt-in, allowlisted OpenTelemetry signals; never capture user input or SQL text."""

import json
import logging
import os
from time import perf_counter
from urllib.parse import urlsplit

from opentelemetry import context, trace
from opentelemetry._logs import LogRecord, SeverityNumber
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from sqlalchemy import event


def configure(engine):
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").rstrip("/")
    url = urlsplit(endpoint)
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or (url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"})
    ):
        raise ValueError("Telemetry requires HTTPS (or loopback HTTP) without credentials/query")
    if os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf") != "http/protobuf":
        raise ValueError("Telemetry supports only OTLP http/protobuf")
    environment = os.getenv("FRESHFIRST_TELEMETRY_ENVIRONMENT", "dev")
    if environment not in {"dev", "test", "production", "local"}:
        raise ValueError("Invalid telemetry environment")
    ratio = float(os.getenv("FRESHFIRST_TELEMETRY_SAMPLE_RATIO", "0.1"))
    if not 0 <= ratio <= 1:
        raise ValueError("Telemetry sample ratio must be between 0 and 1")
    # Explicit Resource avoids environment/host detectors leaking arbitrary attributes.
    resource = Resource(
        {"service.name": "freshfirst-api", "deployment.environment.name": environment}
    )
    traces = TracerProvider(
        resource=resource, sampler=ParentBased(TraceIdRatioBased(ratio)), shutdown_on_exit=False
    )
    traces.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint + "/v1/traces", timeout=3),
            max_queue_size=256,
            max_export_batch_size=64,
            schedule_delay_millis=5000,
        )
    )
    meters = MeterProvider(
        resource=resource,
        shutdown_on_exit=False,
        views=[
            View(
                instrument_name="http.server.request.duration",
                aggregation=ExplicitBucketHistogramAggregation(
                    boundaries=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
                ),
            )
        ],
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=endpoint + "/v1/metrics", timeout=3),
                export_interval_millis=60000,
                export_timeout_millis=5000,
            )
        ],
    )
    logs = LoggerProvider(resource=resource, shutdown_on_exit=False)
    logs.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(endpoint=endpoint + "/v1/logs", timeout=3),
            max_queue_size=256,
            max_export_batch_size=64,
            schedule_delay_millis=5000,
        )
    )
    return Telemetry(engine, traces, meters, logs)


class Telemetry:
    def __init__(self, engine, traces, meters, logs):
        self.engine, self.traces, self.meters, self.logs = engine, traces, meters, logs
        self.tracer = traces.get_tracer("freshfirst")
        self.environment = traces.resource.attributes.get("deployment.environment.name", "dev")
        meter = meters.get_meter("freshfirst")
        self.requests = meter.create_counter("freshfirst.http.requests", unit="1")
        self.duration = meter.create_histogram("http.server.request.duration", unit="s")
        self.counters = {
            name: meter.create_counter("freshfirst." + name, unit="1")
            for name in (
                "listings.created",
                "reservations.completed",
                "recipes.requests",
                "reservations.failures",
            )
        }
        self.log = logs.get_logger("freshfirst.requests")
        # Only our safe completion events enter OTLP/JSON logs, never arbitrary app logs.
        self.console = logging.Logger("freshfirst.telemetry", logging.INFO)
        self.console.addHandler(logging.StreamHandler())
        self.listeners = [
            ("before_cursor_execute", self.before_query),
            ("after_cursor_execute", self.after_query),
            ("handle_error", self.query_error),
        ]
        for name, callback in self.listeners:
            event.listen(engine, name, callback)

    def before_query(self, conn, cursor, statement, parameters, execution, executemany):
        operation = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else "OTHER"
        if operation not in {"SELECT", "INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT", "ROLLBACK"}:
            operation = "OTHER"
        execution._freshfirst_span = self.tracer.start_span(
            "db " + operation,
            kind=trace.SpanKind.CLIENT,
            attributes={"db.system.name": self.engine.dialect.name, "db.operation.name": operation},
        )

    def after_query(self, conn, cursor, statement, parameters, execution, executemany):
        span = getattr(execution, "_freshfirst_span", None)
        if span:
            span.end()
            execution._freshfirst_span = None

    def query_error(self, error):
        execution = error.execution_context
        span = getattr(execution, "_freshfirst_span", None)
        if span:
            span.set_status(trace.StatusCode.ERROR)
            span.end()
            execution._freshfirst_span = None

    def completed(self, scope, method, status, elapsed, span):
        route = scope.get("route")
        # Only static templates from the router; unknown URLs never become labels.
        path = getattr(route, "path", "unmatched")
        operation = getattr(route, "operation_id", None)
        attributes = {
            "freshfirst.environment": self.environment,
            "http.request.method": method,
            "http.route": path,
            "http.response.status_code": status,
        }
        span.update_name(method + " " + path)
        span.set_attributes(attributes)
        if status >= 500:
            span.set_status(trace.StatusCode.ERROR)
        self.requests.add(1, attributes)
        self.duration.record(elapsed, attributes)
        counter = None
        if operation == "createPantryItem" and 200 <= status < 300:
            counter = "listings.created"
        elif operation == "confirmCook":
            counter = "reservations.completed" if 200 <= status < 300 else "reservations.failures"
        elif operation in {"listRecipes", "getRecipe"}:
            counter = "recipes.requests"
        if counter:
            self.counters[counter].add(1, attributes)
        ids = span.get_span_context()
        record = {
            "event": "http.request.completed",
            **attributes,
            "duration_seconds": round(elapsed, 6),
            "trace_id": format(ids.trace_id, "032x"),
            "span_id": format(ids.span_id, "016x"),
        }
        self.console.info(json.dumps(record))
        self.log.emit(
            LogRecord(
                context=context.get_current(),
                severity_number=SeverityNumber.INFO,
                severity_text="INFO",
                body=record,
                attributes=attributes,
            )
        )

    def shutdown(self):
        for name, callback in self.listeners:
            event.remove(self.engine, name, callback)
        # Export failures must never prevent storage shutdown.
        for provider in (self.meters, self.logs, self.traces):
            try:
                provider.shutdown()
            except Exception:
                pass
        for handler in self.console.handlers:
            handler.close()


class RequestTelemetry:
    def __init__(self, app, telemetry):
        self.app, self.telemetry = app, telemetry

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        method = scope.get("method", "OTHER")
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
            method = "OTHER"
        # Read only W3C trace context, not baggage, cookies or arbitrary headers.
        carrier = {
            k.decode("ascii"): v.decode("ascii", errors="replace")
            for k, v in scope.get("headers", [])
            if k == b"traceparent"
        }
        parent = TraceContextTextMapPropagator().extract(carrier)
        started, status = perf_counter(), 500

        async def capture(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        with self.telemetry.tracer.start_as_current_span(
            method,
            context=parent,
            kind=trace.SpanKind.SERVER,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            try:
                await self.app(scope, receive, capture)
            finally:
                try:
                    self.telemetry.completed(scope, method, status, perf_counter() - started, span)
                except Exception:
                    pass  # Telemetry is best effort and cannot alter an API result.
