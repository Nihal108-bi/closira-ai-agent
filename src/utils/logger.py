"""
logger.py — Structured logging configuration for Closira.

All escalation events, SOP gaps, and session summaries are persisted
as newline-delimited JSON to logs/events.jsonl for auditability.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            payload.update(record.extra)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(debug: bool = False) -> None:
    """
    Call once at startup.  Sets up:
      - Console handler (human-readable, coloured if rich is available)
      - Rotating JSON file handler → logs/app.log
      - Dedicated JSONL event log → logs/events.jsonl
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # --- Console handler ---
    try:
        from rich.logging import RichHandler
        console = RichHandler(
            rich_tracebacks=True,
            show_path=False,
            markup=True,
        )
        console.setLevel(logging.DEBUG if debug else logging.INFO)
    except ImportError:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))

    root.addHandler(console)

    # --- Rotating JSON file handler ---
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(_JsonFormatter())
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)


# ---------------------------------------------------------------------------
# Event logger (audit log)
# ---------------------------------------------------------------------------

class EventLogger:
    """
    Writes structured audit events to logs/events.jsonl.
    Every escalation, SOP gap, and session summary is recorded here.
    This gives the ops / support team a queryable audit trail.
    """

    _path = LOG_DIR / "events.jsonl"

    @classmethod
    def _write(cls, event_type: str, payload: Dict[str, Any]) -> None:
        record = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            **payload,
        }
        with cls._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    @classmethod
    def log_escalation(
        cls,
        session_id: str,
        trigger_type: str,
        reason: str,
        confidence: float,
        flagged_message: str,
    ) -> None:
        cls._write(
            "ESCALATION",
            {
                "session_id": session_id,
                "trigger_type": trigger_type,
                "reason": reason,
                "confidence": confidence,
                "flagged_message": flagged_message[:300],  # cap length
            },
        )

    @classmethod
    def log_sop_gap(cls, session_id: str, description: str) -> None:
        cls._write(
            "SOP_GAP",
            {"session_id": session_id, "description": description},
        )

    @classmethod
    def log_session_end(cls, session_id: str, stage_reached: str, turns: int) -> None:
        cls._write(
            "SESSION_END",
            {
                "session_id": session_id,
                "stage_reached": stage_reached,
                "total_turns": turns,
            },
        )
