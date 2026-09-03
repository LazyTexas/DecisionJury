# -*- coding: utf-8 -*-
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import jieba
from rank_bm25 import BM25Okapi
from data_loader import load_history_data  # 静态种子 + B 后端实时历史合并

app = FastAPI()


# 1. 严格对照 API 文档的数据格式
class RagRequest(BaseModel):
    user_id: str
    case_id: str
    case_type: str
    query: str
    top_k: Optional[int] = 3


# RagEvidence 契约字段（docs/04_API.md §5.4 / §10.1）
_RAG_EVIDENCE_FIELDS = ("id", "title", "content", "score", "source", "case_type", "tags", "created_at")


def _to_rag_evidence_item(record: dict, score: float) -> dict:
    """
    把检索命中的原始记录裁剪成 RagEvidence 契约结构。

    原始记录（data/history_records.json 或 B 后端 /api/history 映射后）可能带
    case_id/report_id/price/pros/cons/result 等额外字段，RAG 只对外暴露契约字段，
    避免把内部字段泄漏给 C/前端造成联调歧义。
    """
    tags = record.get("tags")
    if not isinstance(tags, list):
        tags = []
    return {
        "id": str(record.get("id") or ""),
        "title": str(record.get("title") or ""),
        "content": str(record.get("content") or ""),
        "score": float(score),
        "source": str(record.get("source") or "decision_history"),
        "case_type": str(record.get("case_type") or ""),
        "tags": [t for t in tags if isinstance(t, str)],
        "created_at": record.get("created_at"),
    }


@app.post("/api/rag/search")
async def rag_search(request: RagRequest):
    # 每次检索实时取数：静态种子 + 当前用户在后端新写入的历史记录（联动）
    all_records = load_history_data(request.user_id)

    # 步骤 A：数据隔离 (根据 shopping 还是 time 进行初步过滤)
    filtered_records = [
        r for r in all_records
        if r.get("case_type") == request.case_type
        and (r.get("title") or "") and (r.get("content") or "")
    ]

    # 如果该场景下完全没有历史记录，直接按规范返回空数组
    if not filtered_records:
        return {"success": True, "data": {"results": []}, "message": ""}

    # 步骤 B：准备 BM25 算法的语料库 (用 jieba 对标题和内容进行分词)
    corpus = []
    for record in filtered_records:
        # 把标题和内容拼起来一起切分，增加召回率
        text_to_cut = record.get("title", "") + " " + record.get("content", "")
        # 改用搜索引擎专用的分词方法，把长词切得更细，提升召回率
        corpus.append(jieba.lcut_for_search(text_to_cut))

    # 初始化 BM25 引擎
    bm25 = BM25Okapi(corpus)

    # 步骤 C：对用户传来的 query 也进行切分，并彻底过滤掉空格等无效空白字符！
    tokenized_query = [word.strip() for word in jieba.lcut(request.query) if word.strip()]

    # 步骤 D：计算得分 (核心算法)
    scores = bm25.get_scores(tokenized_query)

    # 步骤 E：把算出来的得分赋值给记录，并剔除 0 分的无关数据
    matched_results = []
    for i, record in enumerate(filtered_records):
        score = round(float(scores[i]), 4)  # 保留4位小数
        if score > 0:  # 只有得分大于 0 才说明相关
            matched_results.append(_to_rag_evidence_item(record, score))

    # 步骤 F：根据 score 从大到小排序，并截取前 top_k 个
    matched_results.sort(key=lambda x: x["score"], reverse=True)
    final_results = matched_results[: request.top_k]

    # 3. 严格返回契约要求的结构
    return {
        "success": True,
        "data": {
            "results": final_results
        },
        "message": ""
    }
