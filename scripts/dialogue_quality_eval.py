"""对话质量评测：用真实 API 跑一批剧本，输出准确率/降级率/幻觉率等指标。

用法：
    python scripts/dialogue_quality_eval.py            # 需要 DEEPSEEK_API_KEY 或 deepseek.local.ps1
    python scripts/dialogue_quality_eval.py --json out.json

指标定义：
    field_accuracy   期望字段被正确抽取的比例（字符串按包含判断，数字按容差）
    degrade_rate     本轮走了本地规则（parser_used != deepseek）的比例
    hallucination    用户从未提及、却在最终字段里被填上的项数（按剧本声明的“不应出现”字段）
    repeat_question  连续两轮追问同一问题（复读）的比例
    system_tone      追问/回复里出现系统口吻关键词的比例
    clarify_rounds   达到可分析状态所需轮数（越少越好）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SYSTEM_TONE = ("为了进入", "购物法庭", "字段", "请补充", "已记录", "槽位")

# 剧本：create 是建案描述，turns 是后续补充；expect 是最终应满足的字段；
# must_stay_empty 是用户全程未提及、不应被填上的字段（幻觉检查）。
SCENARIOS: list[dict] = [
    {
        "name": "一句话给全核心字段",
        "create": "想买个键盘，300左右，预算还剩5000",
        "turns": [],
        "expect": {"product_name": "键盘", "price": 300, "monthly_budget_left": 5000},
    },
    {
        "name": "预算与价格同句（芒果）",
        "create": "预算 3000 元，芒果 4 元",
        "turns": [],
        "expect": {"product_name": "芒果", "price": 4, "monthly_budget_left": 3000},
    },
    {
        "name": "带单位单价 + 数量",
        "create": "水果5元一斤，我想买10斤，预算还剩2000元",
        "turns": [],
        "expect": {"product_name": "水果", "price": 5, "monthly_budget_left": 2000,
                   "quantity": 10, "price_is_unit": True},
    },
    {
        "name": "多轮补充到可就绪",
        "create": "我想买芒果",
        "turns": ["花4元买", "预算3000元", "想补充营养，没有其他水果", "差不多每天吃"],
        "expect": {"product_name": "芒果", "price": 4, "monthly_budget_left": 3000,
                   "expected_usage_frequency": "每天"},
    },
    {
        "name": "纠正价格",
        "create": "想买键盘，价格300，预算5000",
        "turns": ["价格不是300，是500"],
        "expect": {"price": 500},
    },
    {
        "name": "否定频率不被误判",
        "create": "想买个相机，5000元，预算还剩20000元",
        "turns": ["我不是每天用，只是偶尔"],
        "expect": {"expected_usage_frequency": "偶尔"},
        "forbid_frequency_canonical": "daily",
    },
    {
        "name": "已有替代品等效判断",
        "create": "想买降噪耳机，800元，预算还剩3000元，已经有普通耳机了，每天通勤用",
        "turns": [],
        "expect": {"product_name": "耳机", "owned_alternatives": "普通耳机",
                   "alternative_covers_need": False},
    },
    {
        "name": "只给价格预算（不应编造用途/替代品/频率）",
        "create": "想买个鼠标，价格199元，预算还剩2000元",
        "turns": [],
        "expect": {"product_name": "鼠标", "price": 199, "monthly_budget_left": 2000},
        "must_stay_empty": ["purpose", "owned_alternatives", "expected_usage_frequency", "trigger_reason"],
    },
]


def load_key() -> str:
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    local = ROOT / "deepseek.local.ps1"
    if local.exists():
        match = re.search(r"sk-[A-Za-z0-9]+", local.read_text(encoding="utf-8"))
        if match:
            return match.group(0)
    raise SystemExit("未找到 DEEPSEEK_API_KEY（环境变量或 deepseek.local.ps1）")


def match_field(name: str, expected, actual) -> bool:
    if actual is None or actual == "":
        return False
    if isinstance(expected, bool):
        return bool(actual) is expected
    if isinstance(expected, (int, float)):
        try:
            return abs(float(actual) - float(expected)) < 1e-6
        except (TypeError, ValueError):
            return False
    return str(expected) in str(actual)


def run_scenario(parse_input, normalize_frequency, scenario: dict) -> dict:
    fields: dict = {}
    degraded = 0
    tones = 0
    repeats = 0
    questions: list[str] = []
    rounds = 0
    started = time.perf_counter()

    messages = [scenario["create"], *scenario.get("turns", [])]
    result = None
    for index, text in enumerate(messages):
        result = parse_input(text, fields)
        fields = dict(result.merged_fields)
        rounds = index + 1
        if result.parser_used != "deepseek":
            degraded += 1
        question = (result.reply_plan or {}).get("question") or ""
        reply = (result.reply_plan or {}).get("reply") or ""
        if any(tone in question or tone in reply for tone in SYSTEM_TONE):
            tones += 1
        if question and questions and question == questions[-1]:
            repeats += 1
        if question:
            questions.append(question)

    hits = sum(1 for key, value in scenario["expect"].items() if match_field(key, value, fields.get(key)))
    misses = [key for key, value in scenario["expect"].items() if not match_field(key, value, fields.get(key))]
    hallucinated = [key for key in scenario.get("must_stay_empty", []) if fields.get(key) not in (None, "")]
    forbidden = scenario.get("forbid_frequency_canonical")
    if forbidden and normalize_frequency(fields.get("expected_usage_frequency")) == forbidden:
        misses.append(f"frequency=={forbidden}")

    return {
        "name": scenario["name"],
        "expected": len(scenario["expect"]),
        "hits": hits,
        "misses": misses,
        "degraded_turns": degraded,
        "turns": rounds,
        "system_tone_hits": tones,
        "repeat_question_hits": repeats,
        "hallucinated_fields": hallucinated,
        "final_fields": {k: v for k, v in fields.items() if not k.startswith("_")},
        "seconds": round(time.perf_counter() - started, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    os.environ["DEEPSEEK_API_KEY"] = load_key()
    os.environ.setdefault("PYTHON_DOTENV_DISABLED", "1")
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("ENV", "development")

    from backend.app.agents.field_normalizer import normalize_frequency
    from backend.app.agents.input_parser import parse_input

    rows = [run_scenario(parse_input, normalize_frequency, item) for item in SCENARIOS]

    total_expected = sum(r["expected"] for r in rows)
    total_hits = sum(r["hits"] for r in rows)
    total_turns = sum(r["turns"] for r in rows)
    total_degraded = sum(r["degraded_turns"] for r in rows)
    total_hallucinated = sum(len(r["hallucinated_fields"]) for r in rows)
    total_tones = sum(r["system_tone_hits"] for r in rows)
    total_repeats = sum(r["repeat_question_hits"] for r in rows)

    print(f"{'剧本':34s} {'字段':>6s} {'降级':>4s} {'轮数':>4s} {'复读':>4s} {'腔调':>4s}  耗时")
    print("-" * 82)
    for row in rows:
        print(f"{row['name']:34s} {row['hits']}/{row['expected']:<4d} {row['degraded_turns']:>4d} "
              f"{row['turns']:>4d} {row['repeat_question_hits']:>4d} {row['system_tone_hits']:>4d}  {row['seconds']}s")
        if row["misses"]:
            print(f"{'':34s} 未命中: {row['misses']}")
        if row["hallucinated_fields"]:
            print(f"{'':34s} 编造字段: {row['hallucinated_fields']}")
    print("-" * 82)
    print(f"字段准确率      {total_hits}/{total_expected} = {total_hits / total_expected:.1%}")
    print(f"降级率          {total_degraded}/{total_turns} = {total_degraded / total_turns:.1%}")
    print(f"幻觉字段数      {total_hallucinated}")
    print(f"复读次数        {total_repeats}")
    print(f"系统口吻命中    {total_tones}")

    if args.json:
        Path(args.json).write_text(
            json.dumps({"summary": {
                "field_accuracy": total_hits / total_expected,
                "degrade_rate": total_degraded / total_turns,
                "hallucinated_fields": total_hallucinated,
                "repeat_questions": total_repeats,
                "system_tone_hits": total_tones,
            }, "rows": rows}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("WROTE", args.json)


if __name__ == "__main__":
    main()
