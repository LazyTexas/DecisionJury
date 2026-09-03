import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rag")))

from evaluate_rag_standard import (  # noqa: E402
    answer_relevancy_score,
    faithfulness_score,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_retrieval_metrics_perfect():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"a", "b", "c"}

    assert round(precision_at_k(retrieved, relevant, 5), 4) == 0.6
    assert round(recall_at_k(retrieved, relevant, 5), 4) == 1.0
    assert mrr(retrieved, relevant, 5) == 1.0
    assert round(ndcg_at_k(retrieved, relevant, 5), 4) == 1.0


def test_retrieval_metrics_no_hit():
    retrieved = ["x", "y"]
    relevant = {"a"}

    assert precision_at_k(retrieved, relevant, 5) == 0.0
    assert recall_at_k(retrieved, relevant, 5) == 0.0
    assert mrr(retrieved, relevant, 5) == 0.0
    assert ndcg_at_k(retrieved, relevant, 5) == 0.0


def test_faithfulness_and_answer_relevancy():
    report_text = "建议购买无线降噪耳机，预算压力中等。"
    evidence_text = "无线降噪耳机 消费复盘；预算 3000 元"

    assert faithfulness_score(report_text, evidence_text) > 0

    # 覆盖了 耳机 / 预算，但没提到 delay
    score = answer_relevancy_score(report_text, ["耳机", "预算", "delay"])
    assert abs(score - 2 / 3) < 1e-6
