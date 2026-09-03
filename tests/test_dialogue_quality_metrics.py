import os
import sys

# 把 rag 目录加入系统路径，便于导入 evaluate_dialogue_quality
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rag")))

from evaluate_dialogue_quality import compute_metrics  # noqa: E402


def test_compute_metrics_with_evidence():
    """正常命中：检索命中、进入上下文、判决书引用证据、关键词有重合。"""
    evidence = [
        {
            "title": "无线降噪耳机 消费复盘",
            "content": "用户购买无线降噪耳机用于学习，使用率高，值得。",
            "tags": ["电子", "数码"],
        }
    ]
    report = {
        "final_decision": "delay",
        "summary": "建议暂缓购买降噪耳机，冷静三天后复盘。",
        "case_summary": "用户想购买降噪耳机用于学习。",
        "pro_points": ["降噪耳机对学习有帮助。"],
        "con_points": ["预算占比较高。"],
        "next_actions": ["加入观察清单，3 天后复盘。"],
        "rag_evidence": evidence,
    }

    m = compute_metrics(True, evidence, report)

    assert m["debate_success"] is True
    assert m["retrieval_hits"] == 1
    assert m["evidence_in_judge_context"] is True
    assert m["report_cites_evidence"] is True
    assert m["grounded_keyword_hit"] is True
    assert m["token_overlap"] > 0


def test_compute_metrics_no_evidence():
    """无证据/无判决书：所有指标应为未命中/0。"""
    m = compute_metrics(False, [], None)

    assert m["debate_success"] is False
    assert m["retrieval_hits"] == 0
    assert m["evidence_in_judge_context"] is False
    assert m["report_cites_evidence"] is False
    assert m["grounded_keyword_hit"] is False
    assert m["token_overlap"] == 0
