# 角色 D（RAG 与数据检索）任务完成度与下一步计划

> 本文档由角色 D 维护，用于向全员同步 RAG 模块的当前完成度、剩余工作、验收方式与依赖。

## 1. 角色与范围

| 项 | 说明 |
|---|---|
| 成员 | D |
| 模块 | RAG 与数据检索 |
| 主要负责目录 | `rag/`、`data/` |
| 配合目录 | `backend/`、`tests/` |

交付清单（来自 `docs/03_Milestones.md` §6.2）：

- 历史记录数据结构。
- 模拟数据。
- 检索模块。
- 检索结果格式。
- RAG 评测样例。

## 2. 完成度一览

| # | 任务 | 状态 | 说明 | 完成度 |
|---|---|---|---|---|
| 1 | 历史记录数据结构 | ✅ 完成 | 500 条记录，字段稳定：`id/title/content/context/pros/cons/tags/...` | 100% |
| 2 | 模拟数据 | ✅ 完成 | 购物 250 + 时间 250，共 **500 条** | 100% |
| 3 | 检索模块 | ✅ 完成 | `rag/retriever.py`：FastAPI + jieba + BM25，`POST /api/rag/search`（端口 8001） | 100% |
| 4 | 检索结果格式 | ✅ 完成 | 返回 `success/data.results/message`，每条结果仅含 `RagEvidence` 字段（`id/title/content/score/source/case_type/tags/created_at`），已裁剪内部字段 | 100% |
| 5 | 前后端数据联动 | ✅ 完成 | `rag/data_loader.py` 合并静态种子 + B `/api/history` 实时历史，新决策复盘自动进入检索 | 100% |
| 6 | RAG 测试 | ⚠️ 主体完成 | 检索/防幻觉/类型隔离/500 条/时间场景/字段映射/合并/回退/adapter 契约 | 90% |
| 7 | 与 C 真实联调 | ✅ 完成 | 已端到端联调验证：创建购物案件 → debate → `rag_evidence` 命中 3 条、trace `rag_search completed`、无命中返回空 | 100% |
| 8 | RAG 评测样例 / 指标 | ✅ 完成 | 新增 `rag/evaluate_rag.py`，输出 top_k/类型/预期命中/分数；4 个标准查询中 3 个 expected_hit，`参加社团活动` 未命中预期关键词 | 80% |
| 9 | 答辩证据 | ⚠️ 部分 | 已能产出检索结果、评测 JSON、判决书引用证据；待补正式截图 | 50% |

**综合完成度估算：约 92%。**

## 3. 已完成内容（实现现状）

### 3.1 数据集：500 条
- `data/history_records.json`：**500 条**（购物 250 + 时间 250），与原有结构一致。
- 新增 `rag/build_history_data.py`：确定性生成脚本（固定随机种子、幂等），可复现数据集。

### 3.2 检索模块
- `rag/retriever.py` 使用 `jieba` 分词 + `rank_bm25.BM25Okapi` 实现 BM25 检索。
- 按 `case_type` 做购物/时间类型隔离。
- 返回结构：`{ "success": true, "data": { "results": [RagEvidence...] }, "message": "" }`。
- 每条结果仅返回 `RagEvidence` 契约字段（`id/title/content/score/source/case_type/tags/created_at`），已裁剪 `case_id/price/pros/cons` 等内部字段，`score` 保留 4 位小数。
- 检索质量优化：query 与语料统一用 `jieba.lcut_for_search`（解决“社团活动/学习用品”被切成整词导致无法命中）；语料加入 `tags`；返回前按 `title` 去重，避免重复记录挤占 top-k。
- 无命中返回空数组 `[]`，不编造历史。

### 3.3 后端联动（新输入的数据入库）
- `rag/data_loader.py`：
  - 读取静态 JSON（500 条）。
  - 拉取 B 后端 `GET /api/history?user_id=...&page=1&page_size=1000` 的实时历史。
  - 字段映射：`history_id → id`、`summary → content`、`source → decision_history`。
  - 按 `id` 合并去重，实时记录优先。
  - 后端不可用时**自动回退到静态数据**，不中断 RAG 服务。
- `rag/retriever.py` 每次检索按请求里的 `user_id` 实时取数，保证前端新数据**立即可检索**。
- 使用 Python 标准库 `urllib`，**未新增第三方依赖**。

### 3.4 环境变量（可选）
| 变量 | 默认值 | 说明 |
|---|---|---|
| `RAG_LIVE_RECORDS` | `1` | 设为 `0` 关闭后端联动（离线/单测） |
| `BACKEND_HISTORY_URL` | `http://127.0.0.1:8000/api/history` | 后端历史接口地址 |
| `HISTORY_TIMEOUT` | `1.0` | 请求后端历史接口超时（秒） |

### 3.5 测试覆盖
```text
tests/test_rag.py                 检索命中/防幻觉/类型隔离/500 条数据/时间场景/RagEvidence 字段/仅契约字段/4 组标准查询命中
tests/test_rag_data_loader.py     字段映射/静态+实时合并/回退/联动开关/响应解包
tests/test_rag_adapter.py         C-D adapter 契约（成功/空结果/失败/缺字段/URL/body）
tests/test_dialogue_quality_metrics.py  对话质量指标计算（检索命中/进上下文/判决书引用/关键词接地）
tests/test_rag_standard_metrics.py      标准版指标纯函数（Precision/Recall/MRR/NDCG/忠实度/答案相关性）
```

验证命令：
```bash
uv run pytest tests/test_rag.py tests/test_rag_data_loader.py tests/test_rag_adapter.py tests/test_dialogue_quality_metrics.py tests/test_rag_standard_metrics.py
uv run python -m compileall -q rag tests
```

当前结果：`29 passed`。

### 3.6 联调与评测脚本
```text
rag/evaluate_rag.py                RAG 检索评测：跑 docs/05_TestPlan.md §5.1 标准查询，输出 top_k/类型/预期命中/分数
rag/e2e_verify.py                  端到端联调验证：创建购物案件 → debate → rag_evidence/trace/report/无命中检查
rag/evaluate_dialogue_quality.py   对话质量量化：检索命中数/进入法官上下文/判决书引用证据/关键词接地(token_overlap)
rag/evaluate_rag_standard.py       标准版 RAG 评估：检索侧 Precision/Recall/MRR/NDCG + 生成侧忠实度/答案相关性/延迟
```

## 4. 下一步该做什么（按优先级）

### P0（已完成）
- ✅ **端到端联调**：`uv run python rag/e2e_verify.py`（需 8000/8001）。结果：购物案件 `rag_evidence` 命中 3 条、trace `rag_search completed`、无命中返回空、report.final_decision=delay。
- ✅ **RAG 评测脚本/指标**：`uv run python rag/evaluate_rag.py --out data/rag_eval_result.json`。优化前 `参加社团活动` 为 False；优化后 4 个标准查询 **全部 expected_hit=True**。
- ✅ **对话质量量化指标**：`uv run python rag/evaluate_dialogue_quality.py --out data/rag_dialogue_quality_result.json`（需 8000/8001）。实测：`retrieval_hits=3`、`evidence_in_judge_context=True`、`report_cites_evidence=True`、`grounded_keyword_hit=True`、`token_overlap=16`。`tests/test_dialogue_quality_metrics.py` 覆盖该指标计算。
- ✅ **标准版 RAG 评估指标**：`uv run python rag/evaluate_rag_standard.py --out data/rag_std_full.json`（离线算检索侧；`--live` 追加生成侧）。
  - 检索侧（top_k=5）：降噪耳机 P=0.4/R=0.33/MRR=1.0/NDCG=0.55；学习用品 P=0.8/R=0.14/MRR=1.0/NDCG=0.85；社团活动 P=0.6/R=0.25/MRR=0.5/NDCG=0.53；技术分享 P=0.4/R=0.25/MRR=1.0/NDCG=0.55。
  - 生成侧（购物）：降噪耳机 faithfulness=0.18/answer_relevancy=1.0/延迟≈1.06s；学习用品 faithfulness=0.11/answer_relevancy=0.5/延迟≈0.13s；time 场景生成侧暂不可算（C 未实现 time 流程）。
  - 结论：检索 recall 偏低（top_k=5 相对相关池偏小，可调 top_k/混合检索）；生成 faithfulness 偏低（判决书措辞对证据接地不足，需优化 Prompt）。

### P1（建议完成）
- ✅ 已完成：契约裁剪。`rag/retriever.py` 返回结果只保留 `RagEvidence` 所需字段（`id/title/content/score/source/case_type/tags/created_at`），已裁剪 `case_id/price/pros/cons` 等内部字段，并补充“仅契约字段”单测。
- ✅ **已完成：检索质量优化 + 4 组标准查询命中**。`rag/retriever.py` 统一 query/语料分词、语料加入 tags、按 title 去重；`tests/test_rag.py` 新增 `test_rag_standard_query_expected_hits`，4 组查询（降噪耳机/学习用品/社团活动/技术分享）在 top_k=5 内均命中预期关键词。
- 剩余：**time 场景检索验证**：C 完成 time 流程后会以 `case_type=time` 调用，D 先确认时间记录检索正常；补答辩检索/引用截图。

### P2（可选 / 依赖其他角色）
6. **BM25 → 混合检索**（BM25 + 向量，可选加分）。
7. **RAG 纳入一键启动/Docker**（依赖 E/部署）。
8. **前端证据展示**（依赖 A/B 前端联调后，确认后端能返回 `rag_evidence`）。

## 5. 依赖与阻塞

| 依赖 | 状态 | 影响 |
|---|---|---|
| C 模块 time 决策流程 | ❌ 尚未实现 | time 端到端联调需等 C |
| B 前后端真实接口链路 | 🔶 联调中 | 判决书/前端证据展示需等 A/B |
| B 历史接口 `/api/history` | ✅ 已提供 | RAG 实时联动依赖它，后端关闭时回退静态数据 |

## 6. RAG 完成定义（验收标准）

- 购物 / 时间两条链路都能引用至少 1 条 RAG 历史证据。
- 无相关历史时返回空数组，不编造。
- RAG 失败不中断 Agent 主流程（trace 记录 `rag_search failed`）。
- 评测指标可复现，能在答辩中展示检索结果截图与判决书引用证据。

## 7. 运行与测试命令

```bash
# 一键启动前后端 + RAG（推荐）
start_all.bat

# 单独启动 RAG
cd rag && venv\Scripts\activate && uvicorn retriever:app --host 127.0.0.1 --port 8001

# 运行 RAG 相关测试
uv run pytest tests/test_rag.py tests/test_rag_data_loader.py tests/test_rag_adapter.py

# RAG 评测（离线，可复现）
uv run python rag/evaluate_rag.py --out data/rag_eval_result.json

# 端到端联调（需先启动 8000/8001）
uv run python rag/e2e_verify.py

# 重新生成 500 条数据集（幂等）
python rag/build_history_data.py
```

## 8. 当前提交分支

- 分支：`feature/rag-500-linkage`
- 提交记录（append 到 origin/dev 之上）：
  - `6b95b43 feat: 扩充 RAG 历史数据至 500 条并联动后端历史入库`
  - `8ab0b21 refactor: RAG 检索结果裁剪为 RagEvidence 契约字段并补充测试`
  - `344a29a test: 补充 RAG 评测脚本与端到端联调验证脚本，更新 D 进度文档`
  - `3277999 docs: 更新 D RAG 进度小结与提交记录`
  - `4c35073 feat: 优化 RAG 检索质量（查询分词/标签索引/标题去重）并补标准查询断言`
  - `1c9b032 docs: 更新 RAG 检索质量优化与完成度`
  - `beb33cc feat: 新增对话质量量化评估指标（检索命中/进上下文/判决书引用/关键词接地）`
  - `157f199 docs: 补充对话质量量化指标与提交记录`
  - `cbde8e8 feat: 新增标准版 RAG 评估指标（Precision/Recall/MRR/NDCG + 忠实度/答案相关性）`
- 状态：**已推送远程**，待通过 PR 合并到 `dev`。

## 9. 一次性进度小结（2020-07 更新）

- RAG 主链路（500 条数据、BM25 检索、契约字段、后端历史联动）已完成。
- P0 已完成：端到端联调验证通过（购物案例命中 3 条证据、trace completed、无命中返回空）；RAG 评测脚本产出 `data/rag_eval_result.json`。
- P1 检索质量优化已完成：query/语料统一用 `lcut_for_search`、语料加 tags、按 title 去重；4 组标准查询在 top_k=5 内均命中预期关键词。
- 对话质量量化指标已完成：`rag/evaluate_dialogue_quality.py` 输出检索命中/进上下文/判决书引用/关键词接地（token_overlap），实测 `grounded_keyword_hit=True`。
- 标准版 RAG 评估指标已完成：`rag/evaluate_rag_standard.py`（检索侧 Precision/Recall/MRR/NDCG + 生成侧忠实度/答案相关性/延迟）。真实发现：检索 recall 偏低（top_k=5 相对相关池偏小）、生成 faithfulness 偏低（判决书对证据接地不足）、time 生成侧暂不可算。
- 当前估算完成度 **约 95%**。
- 剩余重点：调优 top_k/混合检索以提升 recall；优化法官 Prompt 提升 faithfulness；等 C 完成 time 流程后补 time 生成侧；补答辩检索/判决书引用截图；可选接 LLM 做更细的“回答相关性/一致性”打分。
- 未提交：`data/rag_eval_result.json`、`data/rag_dialogue_quality_result.json`、`data/rag_std_retrieval.json`、`data/rag_std_full.json`（评测结果，本地留作答辩证据）。
