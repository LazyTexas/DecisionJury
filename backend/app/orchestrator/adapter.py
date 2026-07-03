# backend/app/orchestrator/adapter.py
from __future__ import annotations

from .decision_flow import run_decision_flow
from ..schemas.decision import to_dict


def run_case_decision_flow(
    case_id: str,
    user_id: str,
    case_type: str,
    description: str,
    collected_fields: dict | None = None,
) -> dict:
    """
    B 后端调用的统一入口。
    将 run_decision_flow 的 dataclass 结果转为 dict，
    并统一 case_status / message 等顶层字段命名。
    """
    # MVP 阶段只支持 shopping
    if case_type != "shopping":
        return {
            "success": False,
            "case_id": case_id,
            "case_status": "rejected",
            "message": "UNSUPPORTED_CASE_TYPE",
        }

    # 字段名映射：B 可能用不同名称 → C 模块标准字段名
    if collected_fields:
        field_mapping = {
            "usage_scenario": "purpose",
            "budget": "monthly_budget_left",
            "usage": "purpose",
            "alternatives": "owned_alternatives",
        }
        normalized_fields = {}
        for key, value in collected_fields.items():
            mapped_key = field_mapping.get(key, key)
            normalized_fields[mapped_key] = value
    else:
        normalized_fields = {}

    # 调用 C 模块核心函数（返回 DebateResult dataclass）
    result = run_decision_flow(
        raw_input=description,
        user_id=user_id,
        case_id=case_id,
        existing_collected_fields=normalized_fields,
    )

    # 转为 dict
    data = to_dict(result)

    # 统一返回格式
    return data