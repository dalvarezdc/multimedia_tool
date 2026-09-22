"""Local observability middleware, LLM tracking, and the dev dashboard."""

import asyncio
import json
import logging
import sqlite3
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from src.director.planner import DirectorPlanner
from src.observability import (
    ActivityObserver,
    ObservabilityMiddleware,
    configure_observability,
    format_dev_banner,
    get_observer,
    parse_cost_usd,
    print_dev_banner,
    track_llm,
)
from src.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MULTIMEDIA_DEV_BANNER", "0")
    monkeypatch.setenv("OBSERVABILITY_CONSOLE", "0")
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "1")
    (tmp_path / "uploads").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    return TestClient(create_app())


def test_parse_cost_reads_provider_estimates():
    assert parse_cost_usd("USD 0.0400") == 0.04
    assert parse_cost_usd("estimated cost 0.030 USD") == 0.03
    assert parse_cost_usd("0.045-0.090 USD") == 0.045
    assert parse_cost_usd("Price unavailable — check Mureka billing") is None
    assert parse_cost_usd(None) is None
    assert parse_cost_usd(1.5) == 1.5


def test_dev_banner_points_at_the_live_view():
    text = format_dev_banner(8000)
    assert "Observability middleware is on" in text
    assert "http://localhost:8000/observability" in text
    assert "http://localhost:8000/metrics" in text
    assert "http://localhost:8000/api/observability/llm" in text


def test_make_dev_announces_middleware():
    makefile = Path("Makefile").read_text()
    assert "http://localhost:8000/observability" in makefile
    assert "MULTIMEDIA_DEV_BANNER=1" in makefile
    nginx = Path("docker/nginx.conf").read_text()
    assert "location = /observability" in nginx
    assert "location = /metrics" in nginx


def test_record_redacts_secrets_and_truncates(tmp_path):
    observer = ActivityObserver(str(tmp_path))
    observer.record(
        "llm",
        "director.complete",
        metadata={
            "api_key": "secret-value",
            "note": "bearer abcdefghijklmnop",
            "prompt": "x" * 600,
        },
    )
    stored = json.dumps(observer.recent(kind="llm")[0]["metadata"])
    assert "secret-value" not in stored
    assert "abcdefghijklmnop" not in stored
    assert "[redacted]" in stored
    assert "truncated" in stored


def test_operation_records_tokens_cost_and_errors(tmp_path):
    observer = ActivityObserver(str(tmp_path))
    with observer.operation("llm", "director.complete", provider="byteplus", model="seed") as bag:
        bag["usage"] = {"prompt_tokens": 11, "completion_tokens": 7}
        bag["cost_usd"] = 0.02
    row = observer.recent(kind="llm")[0]
    assert row["status"] == "ok"
    assert row["model"] == "seed"
    assert row["input_tokens"] == 11
    assert row["output_tokens"] == 7
    assert row["cost_usd"] == pytest.approx(0.02)
    assert row["duration_ms"] >= 0

    class Usage:
        prompt_tokens = 5
        completion_tokens = 2

    with observer.operation("llm", "object-usage") as bag:
        bag["usage"] = Usage()
    assert observer.recent(kind="llm")[0]["input_tokens"] == 5

    with pytest.raises(RuntimeError), observer.operation("llm", "boom", provider="xai", model="grok") as bag:
        bag["usage"] = {"prompt_tokens": 3, "completion_tokens": 1}
        raise RuntimeError("nope")
    failed = next(item for item in observer.recent(kind="llm") if item["name"] == "boom")
    assert failed["status"] == "error"
    assert failed["input_tokens"] == 3
    assert failed["metadata"]["error_type"] == "RuntimeError"


def test_summary_prometheus_and_retention(tmp_path, monkeypatch):
    observer = ActivityObserver(str(tmp_path))
    ticks = iter([float(step) for step in range(1, 8)])
    monkeypatch.setattr("src.observability.time.time", lambda: next(ticks))
    observer.max_events = 2
    for index in range(5):
        observer.record("http", f"GET /{index}", cost_usd=0.1)
    rows = observer.recent(limit=10)
    assert len(rows) == 2
    assert {row["name"] for row in rows} == {"GET /3", "GET /4"}

    summary = observer.summary()
    assert summary["events"] == 2
    assert summary["by_kind"][0]["kind"] == "http"
    assert summary["cost_usd"] == pytest.approx(0.2)
    metrics = observer.prometheus()
    assert 'multimedia_activity_total{kind="http",status="ok"} 2' in metrics
    assert "multimedia_estimated_cost_usd_total" in metrics


def test_disabled_and_broken_storage_do_not_raise(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "0")
    disabled = ActivityObserver(str(tmp_path / "off"))
    disabled.record("llm", "hidden")
    assert disabled.recent() == []
    assert disabled.summary()["enabled"] is False
    assert disabled.prometheus().startswith("# observability disabled")

    monkeypatch.setenv("OBSERVABILITY_ENABLED", "1")
    observer = ActivityObserver(str(tmp_path / "on"))
    observer.record("llm", "kept", input_tokens=1)

    def broken():
        raise sqlite3.OperationalError("locked")

    monkeypatch.setattr(observer, "_connect", broken)
    observer.record("llm", "dropped")
    assert observer.summary()["events"] == 0
    assert observer.prometheus().startswith("# observability metrics unavailable")


def test_console_prints_llm_and_hides_successful_http(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OBSERVABILITY_CONSOLE", "1")
    observer = ActivityObserver(str(tmp_path))
    observer.record("llm", "director.complete", model="grok-test", input_tokens=4, output_tokens=2, cost_usd=0.01)
    printed = capsys.readouterr().out
    assert "director.complete" in printed
    assert "grok-test" in printed
    assert "in=4 out=2" in printed

    observer.record("http", "GET /api/usage", status="ok")
    assert "GET /api/usage" not in capsys.readouterr().out


def test_otel_span_attributes_and_missing_sdk(tmp_path, monkeypatch):
    class Span:
        def __init__(self):
            self.attrs = {}

        def set_attribute(self, key, value):
            self.attrs[key] = value

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Tracer:
        def __init__(self):
            self.span = Span()

        def start_as_current_span(self, name):
            self.span.name = name
            return self.span

    observer = ActivityObserver(str(tmp_path))
    observer._tracer = Tracer()
    with observer.operation("llm", "director.complete", provider="xai", model="grok-4"):
        pass
    assert observer._tracer.span.attrs["gen_ai.request.model"] == "grok-4"
    assert observer._tracer.span.attrs["gen_ai.system"] == "xai"

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:9/v1/traces")
    try:
        import opentelemetry  # noqa: F401
        installed = True
    except ImportError:
        installed = False
    again = ActivityObserver(str(tmp_path / "otel"))
    if not installed:
        assert again._tracer is None


def test_track_llm_without_observer_is_a_noop():
    from src import observability

    previous = observability._observer
    observability._observer = None
    try:
        with track_llm("orphan", provider="xai", model="grok") as bag:
            bag["usage"] = {"prompt_tokens": 1}
    finally:
        observability._observer = previous


def test_warning_logs_are_stored_and_secrets_scrubbed(tmp_path):
    configure_observability(str(tmp_path))
    logging.getLogger("multimedia_server").error("api_key=supersecret boom")
    logging.getLogger("multimedia_observability").error("ignore this internal warning")
    rows = get_observer().recent(kind="log")
    assert rows
    assert rows[0]["name"] == "multimedia_server"
    assert rows[0]["status"] == "error"
    assert "supersecret" not in json.dumps(rows[0]["metadata"])
    assert all(row["name"] != "multimedia_observability" for row in rows)


def test_director_llm_call_is_tracked(tmp_path, monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "mock")
    configure_observability(str(tmp_path))

    class Message:
        content = '{"theme": "tracked", "chapters": []}'

    class Choice:
        message = Message()

    class Usage:
        prompt_tokens = 11
        completion_tokens = 7

    class Response:
        def __init__(self):
            self.choices = [Choice()]
            self.usage = Usage()

    class Completions:
        def create(self, model, messages):
            return Response()

    class FakeArk:
        def __init__(self, **kwargs):
            self.chat = self
            self.completions = Completions()
            self.responses = None

    monkeypatch.setattr("src.director.planner.Ark", FakeArk)
    planner = DirectorPlanner(api_key="mock", model_id="seed-2-0-lite-260228")
    result = planner.plan_storyboard("Tracking check")
    assert result["theme"] == "tracked"
    event = get_observer().recent(kind="llm")[0]
    assert event["name"] == "director.complete"
    assert event["model"] == "seed-2-0-lite-260228"
    assert event["input_tokens"] == 11
    assert event["output_tokens"] == 7
    assert event["status"] == "ok"
    assert "Tracking check" not in json.dumps(event["metadata"])


def test_middleware_traces_requests_and_serves_the_live_view(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.headers["x-trace-id"]

    usage = client.get("/api/usage", headers={"x-trace-id": "plain-trace"})
    assert usage.headers["x-trace-id"] == "plain-trace"
    missing = client.get("/api/not-a-route")
    assert missing.status_code == 404

    events = client.get("/api/observability/activity").json()["events"]
    names = [event["name"] for event in events]
    assert "GET /api/health" not in names
    assert "GET /api/observability/activity" not in names
    assert "GET /metrics" not in names
    usage_event = next(event for event in events if event["name"] == "GET /api/usage")
    assert usage_event["trace_id"] == "plain-trace"
    assert usage_event["metadata"]["status_code"] == 200
    assert any(event["name"] == "GET /api/not-a-route" and event["status"] == "client_error" for event in events)

    summary = client.get("/api/observability/summary")
    assert summary.status_code == 200
    assert summary.json()["events"] >= 1
    assert client.get("/api/observability/llm").status_code == 200
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "multimedia_activity_total" in metrics.text

    page = client.get("/observability")
    assert page.status_code == 200
    assert "Observability middleware" in page.text
    assert "/api/observability/summary" in page.text
    studio = client.get("/app")
    assert 'href="/observability"' in studio.text
    assert "Open live view" in studio.text


def test_telemetry_failure_does_not_break_planning(client, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)

    def broken():
        raise sqlite3.OperationalError("locked")

    monkeypatch.setattr(get_observer(), "_connect", broken)
    response = client.post("/api/plan", json={"topic": "Quiet forest", "chapter_count": 2, "purpose": "rpg"})
    assert response.status_code == 200
    assert response.json()["director_mode"] == "local_deterministic"
    assert response.headers["x-trace-id"]


def test_edge_cases_for_ledger_console_and_middleware(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OBSERVABILITY_CONSOLE", "1")
    monkeypatch.setenv("OBSERVABILITY_CONSOLE_HTTP", "1")
    observer = ActivityObserver(str(tmp_path))
    observer.record(
        "llm",
        "rough",
        provider="grok",
        model="grok-test",
        duration_ms=12,
        input_tokens="nope",
        output_tokens=False,
        cost_usd="nope",
        metadata={
            "blob": "data:image/png;base64,AAAA",
            "refs": ["one"],
            "count": 2,
            "flag": True,
            "empty": None,
            "estimated_cost": "USD 0.0400",
        },
        trace_id="trace-edge",
    )
    printed = capsys.readouterr().out
    assert "grok" in printed
    assert "12ms" in printed
    row = observer.recent(trace_id="trace-edge")[0]
    assert row["input_tokens"] is None
    assert row["cost_usd"] == pytest.approx(0.04)
    assert row["metadata"]["blob"] == "[redacted]"
    assert row["metadata"]["refs"] == "['one']"
    assert observer.recent(trace_id="missing") == []

    observer.record("http", "GET /api/models", status="ok", duration_ms=3)
    assert "GET /api/models" in capsys.readouterr().out

    with observer._connection() as conn:
        conn.execute(
            "UPDATE activity_events SET metadata_json = ? WHERE trace_id = ?",
            ("{", "trace-edge"),
        )
    assert observer.recent(trace_id="trace-edge")[0]["metadata"] == {}

    with observer.operation(
        "media_generation",
        "image.generate",
        metadata={"estimated_cost": "USD 1.2500"},
    ) as bag:
        bag["metadata"] = {"task_id": "img-1"}
    generated = next(item for item in observer.recent() if item["name"] == "image.generate")
    assert generated["cost_usd"] == pytest.approx(1.25)
    assert generated["metadata"]["task_id"] == "img-1"

    def explode(*args, **kwargs):
        raise RuntimeError("ledger down")

    monkeypatch.setattr(observer, "record", explode)
    with observer.operation("llm", "still-returns"):
        pass

    monkeypatch.setenv("MULTIMEDIA_DEV_BANNER", "1")
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "0")
    print_dev_banner()
    assert "off" in capsys.readouterr().out

    monkeypatch.setattr(observer, "_connect", explode)
    assert observer.recent() == []


def test_log_handler_ignores_disabled_and_access_logs(tmp_path):
    observer = configure_observability(str(tmp_path))
    observer.enabled = False
    logging.getLogger("multimedia_server").error("should not land")
    observer.enabled = True
    logging.getLogger("uvicorn.access").warning("polled")
    logging.getLogger("multimedia_server").warning("heads up")
    names = [row["name"] for row in observer.recent(kind="log")]
    assert "uvicorn.access" not in names
    warning = next(row for row in observer.recent(kind="log") if row["metadata"].get("message") == "heads up")
    assert warning["status"] == "warning"

    def explode(*args, **kwargs):
        raise RuntimeError("emit failed")

    observer.record = explode
    logging.getLogger("multimedia_server").error("still safe")


def test_middleware_ignores_non_http_and_telemetry_exceptions(tmp_path):
    observer = ActivityObserver(str(tmp_path))

    async def scenario():
        seen = {}

        async def websocket_app(scope, receive, send):
            seen["kind"] = scope["type"]

        await ObservabilityMiddleware(websocket_app, observer)(
            {"type": "websocket", "path": "/ws"}, None, None
        )
        assert seen["kind"] == "websocket"

        async def ok_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 500, "headers": []})
            await send({"type": "http.response.body", "body": b"no"})

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            return None

        scope = {
            "type": "http",
            "method": "OPTIONS",
            "path": "/api/plan",
            "headers": [(b"x-trace-id", "plain-trace")],
            "state": object(),
        }
        await ObservabilityMiddleware(ok_app, observer)(scope, receive, send)
        assert isinstance(scope["state"], dict)
        assert scope["state"]["trace_id"] == "plain-trace"
        assert observer.recent() == []

        def explode(*args, **kwargs):
            raise RuntimeError("record down")

        observer.record = explode
        scope["method"] = "POST"
        scope["state"] = {}
        await ObservabilityMiddleware(ok_app, observer)(scope, receive, send)

        def bad_reset(tokens):
            raise RuntimeError("reset down")

        observer.record = lambda *args, **kwargs: None
        observer.reset = bad_reset
        await ObservabilityMiddleware(ok_app, observer)(scope, receive, send)

    asyncio.run(scenario())


def test_dev_banner_prints_when_make_dev_enables_it(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MULTIMEDIA_DEV_BANNER", "1")
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "1")
    monkeypatch.setenv("MULTIMEDIA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MULTIMEDIA_UPLOADS_DIR", str(tmp_path / "uploads"))
    create_app()
    printed = capsys.readouterr().out
    assert "Observability middleware is on" in printed
    assert "http://localhost:8000/observability" in printed
