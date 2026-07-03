import time
from typing import Any


class ToolLogger:
    """Records MCP tool call history for traceability and demo purposes."""

    def __init__(self):
        self._logs: list[dict[str, Any]] = []

    def log_call(
        self,
        tool_name: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        duration_ms: float,
    ) -> dict[str, Any]:
        record = {
            "tool_name": tool_name,
            "input": input_data,
            "output": output_data,
            "duration_ms": round(duration_ms, 2),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime()),
        }
        self._logs.append(record)
        return record

    def get_all(self) -> list[dict[str, Any]]:
        return self._logs

    def clear(self) -> None:
        self._logs.clear()


# Singleton shared across the application
logger = ToolLogger()
