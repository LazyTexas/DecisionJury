import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_tools.logger import ToolLogger


def setup_function():
    global logger
    logger = ToolLogger()


logger = ToolLogger()


def test_logger_initial_empty():
    """Logger starts with no records"""
    assert logger.get_all() == []


def test_logger_log_call():
    """Log a single call and verify fields"""
    logger.log_call("test_tool", {"a": 1}, {"b": 2}, 12.34)
    logs = logger.get_all()
    assert len(logs) == 1

    record = logs[0]
    assert record["tool_name"] == "test_tool"
    assert record["input"] == {"a": 1}
    assert record["output"] == {"b": 2}
    assert record["duration_ms"] == 12.34
    assert record["timestamp"].endswith("+08:00")


def test_logger_multiple_calls():
    """Multiple calls accumulate"""
    l = ToolLogger()
    l.log_call("tool_a", {}, {}, 1.0)
    l.log_call("tool_b", {}, {}, 2.0)
    assert len(l.get_all()) == 2


def test_logger_clear():
    """Clear removes all records"""
    l = ToolLogger()
    l.log_call("t", {}, {}, 0.1)
    l.clear()
    assert l.get_all() == []


def test_logger_duration_rounding():
    """duration_ms should be rounded to 2 decimal places"""
    l = ToolLogger()
    l.log_call("t", {}, {}, 1.234567)
    assert l.get_all()[0]["duration_ms"] == 1.23
