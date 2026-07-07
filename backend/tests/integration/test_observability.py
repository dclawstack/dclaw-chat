"""Observability endpoints (#29): metrics, probes, tracing off-by-default."""
import pytest


@pytest.mark.asyncio
async def test_metrics_endpoint_serves_prometheus_format(client):
    # Generate at least one instrumented request first
    await client.get("/api/v1/messaging/channels")
    r = await client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "ws_connections" in body
    assert "llm_router_calls" in body


@pytest.mark.asyncio
async def test_liveness_always_green(client):
    r = await client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_readiness_reports_ready_with_db(client, monkeypatch):
    import app.core.database as database
    from tests.conftest import engine as test_engine

    monkeypatch.setattr(database, "engine", test_engine)
    r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_readiness_503_when_db_unreachable(client, monkeypatch):
    from sqlalchemy.ext.asyncio import create_async_engine

    import app.core.database as database

    dead_engine = create_async_engine("sqlite+aiosqlite:////nonexistent-dir/x.db")
    monkeypatch.setattr(database, "engine", dead_engine)
    r = await client.get("/health/ready")
    assert r.status_code == 503


def test_tracing_is_noop_without_endpoint(monkeypatch):
    """No collector configured → setup_tracing must not install a provider."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    from app.core.observability import setup_tracing
    from app.main import app

    # Must simply return without touching opentelemetry
    assert setup_tracing(app) is None
