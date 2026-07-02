"""cooling_reminder — MCP tool for creating cooling-off reminders.

When the judge agent suggests "delay" or "reject", this tool creates
a watchlist entry with a scheduled reminder for follow-up review.
"""

from .logger import logger
from datetime import datetime, timedelta
import time
import uuid


def create_reminder(
    user_id: str,
    case_id: str,
    title: str,
    days: int = 3,
    reason: str = "",
) -> dict:
    """Create a cooling-off reminder for a decision case.

    Args:
        user_id: User identifier.
        case_id: Case identifier.
        title: Short reminder title (e.g. "降噪耳机冷静期复盘").
        days: Cooling-off period in days. Defaults to 3.
        reason: Why the reminder was set.

    Returns:
        dict with reminder_id, due_at, and status.
    """
    start = time.perf_counter()

    if not user_id or not case_id:
        return {"error": "user_id and case_id are required", "status": "error"}

    effective_days = max(days, 1)
    due_at = (datetime.now() + timedelta(days=effective_days)).strftime(
        "%Y-%m-%dT%H:%M:%S+08:00"
    )

    result = {
        "reminder_id": f"r_{uuid.uuid4().hex[:8]}",
        "due_at": due_at,
        "status": "scheduled",
    }

    duration = (time.perf_counter() - start) * 1000
    logger.log_call(
        "cooling_reminder",
        {"user_id": user_id, "case_id": case_id, "title": title, "days": days, "reason": reason},
        result,
        duration,
    )
    return result
