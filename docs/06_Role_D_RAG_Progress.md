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
tests/test_rag.py                 检索命中/防幻觉/类型隔离/500 条数据/时间场景/RagEvidence 字段/仅契约字段
tests/test_rag_data_loader.py     字段映射/静态+实时合并/回退/联动开关/响应解包
tests/test_rag_adapter.py         C-D adapter 契约（成功/空结果/失败/缺字段/URL/body）
```

验证命令：
```bash
uv run pytest tests/test_rag.py tests/test_rag_data_loader.py tests/test_rag_adapter.py
uv run python -m compileall -q rag tests
```

当前结果：`23 passed`。

### 3.6 联调与评测脚本
```text
rag/evaluate_rag.py     RAG 评测：跑 docs/05_TestPlan.md §5.1 标准查询，输出 top_k/类型/预期命中/分数
rag/e2e_verify.py       端到端联调验证：创建购物案件 → debate → rag_evidence/trace/report/无命中检查
```

## 4. 下一步该做什么（按优先级）

### P0（已完成）
- ✅ **端到端联调**：`uv run python rag/e2e_verify.py`（需 8000/8001）。结果：购物案件 `rag_evidence` 命中 3 条、trace `rag_search completed`、无命中返回空、report.final_decision=delay。
- ✅ **RAG 评测脚本/指标**：`uv run python rag/evaluate_rag.py --out data/rag_eval_result.json`。结果：4 个标准查询中 `想买降噪耳机`/`想买学习用品`/`参加技术分享` 为 expected_hit=True，`参加社团活动` 为 False（召回质量待提升）。

### P1（建议完成）
- ✅ 已完成：契约裁剪。`rag/retriever.py` 返回结果只保留 `RagEvidence` 所需字段（`id/title/content/score/source/case_type/tags/created_at`），已裁剪 `case_id/price/pros/cons` 等内部字段，并补充“仅契约字段”单测。
1. **优化两处检索质量并补 4 组标准查询命中断言**：
   - 评测显示 `想买学习用品` 的 top 命中偏题（围巾等），`参加社团活动` 未命中预期关键词（`社团/活动`）。
   - 建议：调整 query 分词/对 `title+tags` 加权、给关键记录补充更强关键词，然后补断言：
     - 降噪耳机 → 电子/闲置/预算记录。
     - 学习用品 → 学习台灯/值得购买记录。
     - 社团活动 → 作业延期/社团记录。
     - 技术分享 → 低时间成本记录。
2. **time 场景检索验证**：C 完成 time 流程后会以 `case_type=time` 调用，D 先确认时间记录检索正常。

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
- 提交记录：
  - `6b95b43 feat: 扩充 RAG 历史数据至 500 条并联动后端历史入库`
  - `8ab0b21 refactor: RAG 检索结果裁剪为 RagEvidence 契约字段并补充测试`
- 状态：已推送远程，待通过 PR 合并到 `dev`。
