from __future__ import annotations

import json

from backend.app.orchestrator.decision_flow import run_decision_flow
from backend.app.schemas.decision import to_dict


def main() -> None:
    raw_input = (
        "我想买一副 1299 元的降噪耳机，最近学习需要安静。"
        "本月预算还剩 2000 元，已有普通耳机，预计每天使用，这次是刚需。"
    )
    result = run_decision_flow(raw_input=raw_input, user_id="u001", case_id="case_001")
    print(json.dumps(to_dict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
