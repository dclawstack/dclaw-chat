"""Observability (#29): Prometheus metrics, optional OTLP tracing, probes.

Everything here is safe with nothing configured: metrics are always served at
/metrics (scraping is pull-based, no collector needed), tracing initialises
only when OTEL_EXPORTER_OTLP_ENDPOINT is set, and the probes need only the DB.
"""
from __future__ import annotations

import os
import time

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    REGISTRY,
    generate_latest,
)
from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import text

from app.core.logging import get_logger

log = get_logger(__name__)

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests by method, route template and status",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency by method and route template",
    ["method", "route"],
)
WS_CONNECTIONS = Gauge(
    "ws_connections", "Currently connected WebSocket clients on this replica"
)
LLM_LATENCY = Histogram(
    "llm_call_duration_seconds",
    "LLM provider call latency",
    ["provider"],
)
LLM_FAILURES = Counter(
    "llm_call_failures_total", "LLM provider call failures", ["provider"]
)


class _RouterStatsCollector:
    """Expose ModelRouter's in-process counters without touching its code."""

    def collect(self):
        from app.services.model_router import ModelRouter

        g = GaugeMetricFamily(
            "llm_router_calls", "Model-router usage counters", labels=["kind"]
        )
        for key, value in ModelRouter.stats().items():
            if isinstance(value, (int, float)):
                g.add_metric([key], float(value))
        yield g


_registered = False


def setup_observability(app: FastAPI) -> None:
    global _registered
    if not _registered:
        try:
            REGISTRY.register(_RouterStatsCollector())
        except ValueError:  # pragma: no cover - double import safety
            pass
        from app.services.messaging import manager

        WS_CONNECTIONS.set_function(lambda: float(manager.online_count))
        _registered = True

    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        # Route template keeps label cardinality bounded; unmatched paths
        # (404 scans) are bucketed together.
        route_path = getattr(route, "path", "unmatched")
        HTTP_REQUESTS.labels(request.method, route_path, str(response.status_code)).inc()
        HTTP_LATENCY.labels(request.method, route_path).observe(
            time.perf_counter() - start
        )
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/health/live", include_in_schema=False)
    async def liveness() -> dict:
        return {"status": "alive"}

    @app.get("/health/ready", include_in_schema=False)
    async def readiness() -> Response:
        from app.core.database import engine

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            log.warning("readiness_failed", error=repr(exc))
            return Response(
                content='{"status": "not ready"}',
                status_code=503,
                media_type="application/json",
            )
        return Response(
            content='{"status": "ready"}', media_type="application/json"
        )


def setup_tracing(app: FastAPI) -> None:
    """OTLP tracing across request → service → DB/provider spans. No-op
    unless OTEL_EXPORTER_OTLP_ENDPOINT is configured."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        from app.core.database import engine

        provider = TracerProvider(
            resource=Resource.create({"service.name": "dclaw-chat-backend"})
        )
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
        HTTPXClientInstrumentor().instrument()
        log.info("tracing_enabled", endpoint=endpoint)
    except Exception as exc:  # pragma: no cover - never break startup
        log.warning("tracing_setup_failed", error=repr(exc))
