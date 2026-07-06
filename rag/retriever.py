from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import jieba
from rank_bm25 import BM25Okapi
from data_loader import load_history_data  # 导入你刚刚写好的数据加载模块

app = FastAPI()


# 1. 严格对照 API 文档的数据格式
class RagRequest(BaseModel):
    user_id: str
    case_id: str
    case_type: str
    query: str
    top_k: Optional[int] = 3


# 2. 服务启动时，加载真实的 JSON 历史数据
ALL_RECORDS = load_history_data()


@app.post("/api/rag/search")
async def rag_search(request: RagRequest):
    # 步骤 A：数据隔离 (根据 shopping 还是 time 进行初步过滤)
    filtered_records = [r for r in ALL_RECORDS if r["case_type"] == request.case_type]

    # 如果该场景下完全没有历史记录，直接按规范返回空数组
    if not filtered_records:
        return {"success": True, "data": {"results": []}, "message": ""}

    # 步骤 B：准备 BM25 算法的语料库 (用 jieba 对标题和内容进行分词)
    corpus = []
    for record in filtered_records:
        # 把标题和内容拼起来一起切分，增加召回率
        text_to_cut = record["title"] + " " + record["content"]
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
        score = round(scores[i], 4)  # 保留4位小数
        if score > 0:  # 只有得分大于 0 才说明相关
            # Python 的字典是引用传递，为了不污染原始数据，我们做个浅拷贝
            result_item = record.copy()
            result_item["score"] = score
            matched_results.append(result_item)

    # 步骤 F：根据 score 从大到小排序，并截取前 top_k 个
    matched_results.sort(key=lambda x: x["score"], reverse=True)
    final_results = matched_results[:request.top_k]

    # 3. 严格返回契约要求的结构
    return {
        "success": True,
        "data": {
            "results": final_results
        },
        "message": ""
    }