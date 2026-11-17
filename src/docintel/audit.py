"""Audit trail: one JSON line per tool call.

Day 1 records tool, arguments, outcome and duration. Day 3 adds the caller's
identity and OAuth scopes once the server sits behind the gateway.

Never write to stdout here: on the stdio transport, stdout is the protocol channel.
"""

from __future__ import annotations

import functools
import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def audit_path() -> Path:
    return Path(os.environ.get("DOCINTEL_AUDIT_LOG", ".data/audit.jsonl"))


def audited[F: Callable[..., Any]](func: F) -> F:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        outcome, error = "ok", None
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            outcome, error = "error", f"{type(exc).__name__}: {exc}"
            raise
        finally:
            record = {
                "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "tool": func.__name__,
                "arguments": kwargs,
                "outcome": outcome,
                "error": error,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
            path = audit_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str) + "\n")

    return wrapper  # type: ignore[return-value]
