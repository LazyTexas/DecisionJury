"""E 模块工具演示脚本（答辩取证用）。

运行方式：
    python -m mcp_tools.demo

会依次调用 cost_analyzer（购物 + 时间）和 cooling_reminder，
并打印工具调用日志（来自 mcp_tools.logger），方便在答辩时展示
“至少两个 MCP 工具被调用”的课程要求证据。
"""

from __future__ import annotations

import json

from mcp_tools.mcp import call_tool
from mcp_tools.logger import logger


def main() -> None:
    shopping_cost = call_tool(
        "cost_analyzer",
        {
            "case_type": "shopping",
            "price": 1299,
            "monthly_budget_left": 2000,
        },
    )

    time_cost = call_tool(
        "cost_analyzer",
        {
            "case_type": "time",
            "hours_required": 16,
            "free_hours_this_week": 20,
            "urgent_tasks": 2,
        },
    )

    reminder = call_tool(
        "cooling_reminder",
        {
            "user_id": "u001",
            "case_id": "case_001",
            "title": "降噪耳机冷静期复盘",
            "cooling_days": 3,
            "reason": "预算占比较高，建议冷静 3 天后复盘。",
            "watch_items": ["是否仍然需要", "是否已有低价替代品", "是否影响本月必要支出"],
        },
    )

    output = {
        "tool_results": [shopping_cost, time_cost, reminder],
        "call_log": logger.get_all(),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
