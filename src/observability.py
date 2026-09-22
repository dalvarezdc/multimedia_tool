"""Fail-open application observability for local development and optional OTLP export.

The SQLite ledger is the local source of truth for requests, logs, LLM calls, and
media jobs. OpenTelemetry export turns on only when the SDK is installed and
``OTEL_EXPORTER_OTLP_ENDPOINT`` is set. Telemetry failures are logged and ignored.

``make dev`` sets ``MULTIMEDIA_DEV_BANNER=1`` so startup prints the live view URL
and later LLM, media, workflow, and error events are echoed to the terminal.
"""

# ruff: noqa: BLE001
from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any

logger = logging.getLogger("multimedia_observability")

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("run_id", default="")

SENSITIVE_KEYS = {
    "api_key", "authorization", "ark_api_key", "xai_api_key", "mureka_api_key",
    "password", "token", "access_token", "secret", "image_url", "data_uri",
    "cookie", "session",
}

# Probes and the dashboard's own reads stay out of the ledger so they cannot
# crowd out real activity. They still receive a trace id response header.
QUIET_PREFIXES = ("/api/observability", "/static", "/renders", "/uploads")
QUIET_PATHS = {"/metrics", "/favicon.ico", "/api/health"}

_COST_RE = re.compile(r"\d+(?:\.\d+)?")
_BEARER_RE = re.compile(r"(?i)(bearer\s+)\S+")
_KEY_ASSIGN_RE = re.compile(r"(?i)((?:api[_-]?key|token|secret|password)\s*[=:]\s*)\S+")

_log_handler: ActivityLogHandler | None = None


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def console_enabled() -> bool:
    raw = os.getenv("OBSERVABILITY_CONSOLE")
    if raw is None:
        return _flag("MULTIMEDIA_DEV_BANNER", "0")
    return _flag("OBSERVABILITY_CONSOLE", "0")


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_cost_usd(value: Any) -> float | None:
    """Pull the first number out of a cost string such as ``USD 0.0400``."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _COST_RE.search(str(value))
    if not match:
        return None
    return float(match.group(0))


def _scrub_text(text: str) -> str:
    cleaned = _BEARER_RE.sub(r"\1[redacted]", text or "")
    cleaned = _KEY_ASSIGN_RE.sub(r"\1[redacted]", cleaned)
    if len(cleaned) > 500:
        return f"{cleaned[:120]}… [truncated, {len(cleaned)} chars]"
    return cleaned


def _safe_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, item in (value or {}).items():
        normalized = str(key).lower()
        if normalized in SENSITIVE_KEYS or normalized.endswith(("_key", "_token")):
            safe[key] = "[redacted]"
            continue
        if isinstance(item, str):
            lowered = item.lower()
            if lowered.startswith(("data:", "bearer ")):
                safe[key] = "[redacted]"
            else:
                safe[key] = _scrub_text(item)
        elif isinstance(item, (int, float, bool)) or item is None:
            safe[key] = item
        else:
            safe[key] = _scrub_text(str(item))
    return safe


def _label(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", " ").replace('"', '\\"')


def _should_print(kind: str, status: str) -> bool:
    if not console_enabled():
        return False
    if kind == "http" and status == "ok":
        return _flag("OBSERVABILITY_CONSOLE_HTTP", "0")
    return True


def _console_line(
    kind: str,
    name: str,
    status: str,
    duration_ms: float | None,
    provider: str | None,
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: float | None,
    trace: str,
) -> None:
    if not _should_print(kind, status):
        return
    bits = [f"observability  {status:<12} {kind:<16} {name}"]
    if provider:
        bits.append(provider)
    if model:
        bits.append(model)
    if duration_ms is not None:
        bits.append(f"{duration_ms:.0f}ms")
    if input_tokens is not None or output_tokens is not None:
        bits.append(f"in={input_tokens or 0} out={output_tokens or 0}")
    if cost_usd:
        bits.append(f"${cost_usd:.4f}")
    if trace:
        bits.append(f"trace={trace[:8]}")
    print("  ".join(bits), flush=True)


def format_dev_banner(port: int | None = None) -> str:
    resolved = port or int(os.getenv("PORT", "8000"))
    base = f"http://localhost:{resolved}"
    return "\n".join([
        "=====================================================================",
        "  Observability middleware is on",
        f"  Live view     {base}/observability",
        f"  Metrics       {base}/metrics",
        f"  LLM calls     {base}/api/observability/llm",
        f"  Activity log  {base}/api/observability/activity",
        "  LLM, media, workflow, and error events also print in this terminal.",
        "=====================================================================",
    ])


def print_dev_banner() -> None:
    if not _flag("MULTIMEDIA_DEV_BANNER", "0"):
        return
    if not _flag("OBSERVABILITY_ENABLED", "1"):
        print("Observability middleware is off (OBSERVABILITY_ENABLED=0).", flush=True)
        return
    print(format_dev_banner(), flush=True)


def _zero_summary(enabled: bool) -> dict[str, Any]:
    return {
        "events": 0,
        "errors": 0,
        "avg_duration_ms": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "by_kind": [],
        "enabled": enabled,
    }


def _skip_path(path: str) -> bool:
    if path in QUIET_PATHS:
        return True
    return path.startswith(QUIET_PREFIXES)


def _header_text(headers: dict[bytes, bytes], name: bytes) -> str:
    raw = headers.get(name, b"")
    if isinstance(raw, str):
        return raw.strip()
    return bytes(raw).decode("utf-8", "ignore").strip()


class ActivityLogHandler(logging.Handler):
    """Copy warnings and errors into the ledger without recording our own logger."""

    def __init__(self, observer: ActivityObserver):
        super().__init__(level=logging.WARNING)
        self.observer = observer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if not self.observer.enabled:
                return
            if record.name.startswith(("multimedia_observability", "uvicorn.access")):
                return
            if record.levelno < logging.WARNING:
                return
            status = "error" if record.levelno >= logging.ERROR else "warning"
            self.observer.record(
                "log",
                record.name,
                status,
                metadata={"level": record.levelname, "message": _scrub_text(record.getMessage())},
            )
        except Exception:
            return


def install_log_handler(observer: ActivityObserver) -> None:
    global _log_handler
    if _log_handler is None:
        _log_handler = ActivityLogHandler(observer)
        logging.getLogger().addHandler(_log_handler)
        return
    _log_handler.observer = observer


class ActivityObserver:
    """Durable event ledger, Prometheus text, and optional OTel spans."""

    def __init__(self, data_dir: str):
        self.enabled = _flag("OBSERVABILITY_ENABLED", "1")
        self.db_path = Path(data_dir) / "observability.db"
        self.max_events = max(100, _as_int(os.getenv("OBSERVABILITY_MAX_EVENTS")) or 5000)
        self._lock = threading.RLock()
        self._tracer = self._configure_otel()
        if self.enabled:
            self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_events (
                    id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    trace_id TEXT NOT NULL,
                    run_id TEXT,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL,
                    provider TEXT,
                    model TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cost_usd REAL,
                    metadata_json TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_events(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_trace ON activity_events(trace_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_kind ON activity_events(kind, created_at DESC)")

    def _configure_otel(self):
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
        if not endpoint:
            return None
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider(resource=Resource.create({
                "service.name": os.getenv("OTEL_SERVICE_NAME", "multimedia-tool"),
                "deployment.environment.name": os.getenv("APP_ENV", "development"),
            }))
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            trace.set_tracer_provider(provider)
            return trace.get_tracer("multimedia-tool")
        except Exception as exc:
            logger.warning("OTLP exporter disabled: %s", exc)
            return None

    def new_trace_id(self) -> str:
        return uuid.uuid4().hex

    def bind(self, trace_id: str, run_id: str = ""):
        return (_trace_id.set(trace_id), _run_id.set(run_id))

    def reset(self, tokens) -> None:
        _trace_id.reset(tokens[0])
        _run_id.reset(tokens[1])

    def record(
        self,
        kind: str,
        name: str,
        status: str = "ok",
        duration_ms: float | None = None,
        provider: str | None = None,
        model: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: float | None = None,
        metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        trace = trace_id or _trace_id.get() or self.new_trace_id()
        run = run_id or _run_id.get() or None
        safe = _safe_metadata(metadata)
        in_tokens = _as_int(input_tokens)
        out_tokens = _as_int(output_tokens)
        cost = _as_float(cost_usd)
        if cost is None:
            cost = parse_cost_usd(safe.get("estimated_cost"))
        try:
            with self._lock, self._connection() as conn:
                conn.execute(
                    """INSERT INTO activity_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        uuid.uuid4().hex, time.time(), trace, run, kind, name, status,
                        duration_ms, provider, model, in_tokens, out_tokens, cost,
                        json.dumps(safe, separators=(",", ":"), default=str),
                    ),
                )
                conn.execute(
                    """
                    DELETE FROM activity_events
                    WHERE created_at < (
                        SELECT created_at FROM activity_events
                        ORDER BY created_at DESC LIMIT 1 OFFSET ?
                    )
                    """,
                    (max(0, self.max_events - 1),)
                )
            _console_line(kind, name, status, duration_ms, provider, model, in_tokens, out_tokens, cost, trace)
        except Exception as exc:
            logger.warning("Activity recording failed: %s", exc)

    @contextmanager
    def operation(self, kind: str, name: str, **fields: Any) -> Iterator[dict[str, Any]]:
        """Time a unit of work. The yielded dict accepts ``usage`` and ``cost_usd``."""
        started = time.perf_counter()
        result: dict[str, Any] = {}
        error: BaseException | None = None
        metadata = fields.pop("metadata", None) or {}
        provider = fields.pop("provider", None)
        model = fields.pop("model", None)
        trace_id = fields.pop("trace_id", None)
        run_id = fields.pop("run_id", None)
        span_cm = self._tracer.start_as_current_span(name) if self._tracer else nullcontext()
        try:
            with span_cm as current:
                if current is not None and hasattr(current, "set_attribute"):
                    current.set_attribute("gen_ai.operation.name", name)
                    if provider:
                        current.set_attribute("gen_ai.system", provider)
                    if model:
                        current.set_attribute("gen_ai.request.model", model)
                yield result
        except Exception as exc:
            error = exc
            raise
        finally:
            try:
                usage = result.get("usage") or {}
                if not isinstance(usage, dict):
                    usage = {
                        "input_tokens": getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None),
                        "output_tokens": getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None),
                    }
                meta = dict(metadata)
                extra = result.get("metadata")
                if isinstance(extra, dict):
                    meta.update(extra)
                if error is not None:
                    meta["error_type"] = type(error).__name__
                cost = result.get("cost_usd")
                if cost is None:
                    cost = parse_cost_usd(meta.get("estimated_cost"))
                self.record(
                    kind,
                    name,
                    "error" if error else str(result.get("status") or "ok"),
                    (time.perf_counter() - started) * 1000,
                    provider=provider,
                    model=model,
                    input_tokens=usage.get("input_tokens") or usage.get("prompt_tokens"),
                    output_tokens=usage.get("output_tokens") or usage.get("completion_tokens"),
                    cost_usd=cost,
                    metadata=meta,
                    trace_id=trace_id,
                    run_id=run_id,
                    **fields,
                )
            except Exception as exc:
                logger.warning("Observability operation failed: %s", exc)

    def recent(
        self,
        limit: int = 100,
        trace_id: str | None = None,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        limit = max(1, min(int(limit or 100), 500))
        query = "SELECT * FROM activity_events"
        clauses: list[str] = []
        params: list[Any] = []
        if trace_id:
            clauses.append("trace_id = ?")
            params.append(trace_id)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        try:
            with self._connection() as conn:
                rows = conn.execute(query, params).fetchall()
        except Exception as exc:
            logger.warning("Activity query failed: %s", exc)
            return []
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            except json.JSONDecodeError:
                item["metadata"] = {}
            result.append(item)
        return result

    def summary(self) -> dict[str, Any]:
        if not self.enabled:
            return _zero_summary(False)
        try:
            with self._connection() as conn:
                row = conn.execute("""
                    SELECT COUNT(*) AS events,
                           SUM(CASE WHEN status IN ('error', 'client_error', 'warning') THEN 1 ELSE 0 END) AS errors,
                           AVG(duration_ms) AS avg_duration_ms,
                           SUM(COALESCE(input_tokens, 0)) AS input_tokens,
                           SUM(COALESCE(output_tokens, 0)) AS output_tokens,
                           SUM(COALESCE(cost_usd, 0)) AS cost_usd
                    FROM activity_events
                """).fetchone()
                kinds = conn.execute("""
                    SELECT kind,
                           COUNT(*) AS events,
                           SUM(CASE WHEN status IN ('error', 'client_error', 'warning') THEN 1 ELSE 0 END) AS errors,
                           SUM(COALESCE(input_tokens, 0)) AS input_tokens,
                           SUM(COALESCE(output_tokens, 0)) AS output_tokens,
                           SUM(COALESCE(cost_usd, 0)) AS cost_usd
                    FROM activity_events
                    GROUP BY kind
                    ORDER BY kind
                """).fetchall()
        except Exception as exc:
            logger.warning("Activity summary failed: %s", exc)
            return _zero_summary(True)
        payload = _zero_summary(True)
        if row is not None:
            payload.update({
                "events": int(row["events"] or 0),
                "errors": int(row["errors"] or 0),
                "avg_duration_ms": row["avg_duration_ms"],
                "input_tokens": int(row["input_tokens"] or 0),
                "output_tokens": int(row["output_tokens"] or 0),
                "cost_usd": float(row["cost_usd"] or 0),
            })
        payload["by_kind"] = [
            {
                "kind": item["kind"],
                "events": int(item["events"] or 0),
                "errors": int(item["errors"] or 0),
                "input_tokens": int(item["input_tokens"] or 0),
                "output_tokens": int(item["output_tokens"] or 0),
                "cost_usd": float(item["cost_usd"] or 0),
            }
            for item in kinds
        ]
        return payload

    def prometheus(self) -> str:
        if not self.enabled:
            return "# observability disabled\n"
        lines = [
            "# HELP multimedia_activity_total Recorded application activities",
            "# TYPE multimedia_activity_total counter",
        ]
        try:
            with self._connection() as conn:
                rows = conn.execute(
                    "SELECT kind, status, COUNT(*) AS n FROM activity_events GROUP BY kind, status ORDER BY kind, status"
                ).fetchall()
            summary = self.summary()
        except Exception as exc:
            logger.warning("Metrics render failed: %s", exc)
            return "# observability metrics unavailable\n"
        for row in rows:
            lines.append(
                f'multimedia_activity_total{{kind="{_label(row["kind"])}",status="{_label(row["status"])}"}} {int(row["n"])}'
            )
        lines.extend([
            "# HELP multimedia_llm_input_tokens_total Recorded LLM input tokens",
            "# TYPE multimedia_llm_input_tokens_total counter",
            f"multimedia_llm_input_tokens_total {summary['input_tokens'] or 0}",
            "# HELP multimedia_llm_output_tokens_total Recorded LLM output tokens",
            "# TYPE multimedia_llm_output_tokens_total counter",
            f"multimedia_llm_output_tokens_total {summary['output_tokens'] or 0}",
            "# HELP multimedia_estimated_cost_usd_total Estimated provider cost in USD",
            "# TYPE multimedia_estimated_cost_usd_total counter",
            f"multimedia_estimated_cost_usd_total {summary['cost_usd'] or 0}",
        ])
        return "\n".join(lines) + "\n"


@contextmanager
def track_llm(
    name: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Record one LLM call. No-ops when the app has not configured an observer.

    Set ``usage`` on the yielded dict (``prompt_tokens`` / ``completion_tokens``
    or ``input_tokens`` / ``output_tokens``) and optional ``cost_usd`` before
    the block exits.
    """
    observer = get_observer()
    if observer is None:
        yield {}
        return
    with observer.operation(
        "llm",
        name,
        provider=provider,
        model=model,
        metadata=metadata or {},
    ) as result:
        yield result


class ObservabilityMiddleware:
    def __init__(self, app, observer: ActivityObserver):
        self.app = app
        self.observer = observer

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in (scope.get("headers") or [])}
        trace_id = _header_text(headers, b"x-trace-id") or self.observer.new_trace_id()
        run_id = _header_text(headers, b"x-run-id") or uuid.uuid4().hex
        scope.setdefault("state", {})
        if not isinstance(scope["state"], dict):
            scope["state"] = {}
        scope["state"]["trace_id"] = trace_id
        scope["state"]["run_id"] = run_id
        tokens = self.observer.bind(trace_id, run_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_trace(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                outbound = list(message.get("headers") or [])
                outbound.append((b"x-trace-id", trace_id.encode()))
                outbound.append((b"x-run-id", run_id.encode()))
                message["headers"] = outbound
            await send(message)

        try:
            await self.app(scope, receive, send_with_trace)
        finally:
            path = scope.get("path", "")
            method = scope.get("method", "GET")
            try:
                if method != "OPTIONS" and not _skip_path(path):
                    if status_code >= 500:
                        status = "error"
                    elif status_code >= 400:
                        status = "client_error"
                    else:
                        status = "ok"
                    self.observer.record(
                        "http",
                        f"{method} {path}",
                        status,
                        (time.perf_counter() - started) * 1000,
                        metadata={"status_code": status_code},
                        trace_id=trace_id,
                        run_id=run_id,
                    )
            except Exception as exc:
                logger.warning("HTTP activity recording failed: %s", exc)
            try:
                self.observer.reset(tokens)
            except Exception as exc:
                logger.warning("Failed to reset observability context: %s", exc)


_observer: ActivityObserver | None = None


def configure_observability(data_dir: str) -> ActivityObserver:
    global _observer
    _observer = ActivityObserver(data_dir)
    install_log_handler(_observer)
    return _observer


def get_observer() -> ActivityObserver | None:
    return _observer
