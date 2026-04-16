from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


# Fields that are always present on a LogRecord — we exclude them from the
# "extra" block to keep output clean and predictable.
_STDLIB_ATTRS = frozenset({
    "args", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "message", "module", "msecs", "msg",
    "name", "pathname", "process", "processName", "relativeCreated",
    "stack_info", "thread", "threadName",
})


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log line.

    Standard fields: timestamp, level, logger, message.
    Any keys passed via extra={} appear as top-level fields alongside the
    standard ones — NOT nested under an "extra" key — so they are directly
    searchable in log aggregators without path traversal.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Ensure record.message is populated (calls record.getMessage())
        record.message = record.getMessage()

        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }

        # Append exception info if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # Collect extra fields: anything on the record that is not a stdlib attr
        for key, value in record.__dict__.items():
            if key not in _STDLIB_ATTRS and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Call once at application startup to install the JSON formatter globally."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    # Replace any handlers installed by uvicorn or previous calls
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy third-party loggers that are not useful at INFO
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
