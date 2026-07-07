# DecisionJury 里程碑计划

## 1. 项目周期

项目周期为三周。目标是在三周内完成一个可运行、可演示、可答辩的 MVP。

## 2. 团队分工

本项目 5 人分工只按具体实现模块划分。文档、答辩、PPT、演示讲解不作为单独岗位，后期由全员基于自己负责模块共同补充。

| 成员 | 实现方向 | 主要职责 |
|---|---|---|
| A | 前端交互开发 | 页面结构、案件创建页、多轮对话页、判决书展示、RAG/MCP 结果展示 |
| B | 后端 API 与状态管理 | FastAPI 接口、案件 CRUD、SQLite 数据存储、多轮会话状态、接口联调 |
| C | Agent 编排与 LLM 调用 | LLM API 接入、输入解析 Agent、正方 Agent、反方 Agent、法官 Agent、Prompt 模板 |
| D | RAG 与数据检索 | 历史记录样例、规则知识库、BM25/向量/混合检索、证据引用、RAG 评测 |
| E | MCP 工具与工程化 | cost_analyzer、cooling_reminder、工具调用日志、自动化测试、Docker 或一键启动 |

## 3. 三周总计划

### 第 1 周：基础链路跑通

目标：

- 完成必要文档初稿。
- 搭建项目仓库和基础目录。
- 跑通 LLM 调用。
- 跑通多 Agent 基础流程。
- 完成案件创建和简单对话。

验收标准：

- 能创建购物案件。
- 能创建时间案件。
- 正方 Agent、反方 Agent、法官 Agent 能按顺序输出。
- 有一份可运行的命令行或后端 Demo。

### 第 2 周：RAG 与 MCP 工具接入

目标：

- 完成历史记录数据结构。
- 完成 RAG 检索模块。
- 完成成本计算 MCP 工具。
- 完成冷静期提醒 MCP 工具。
- 将 RAG 和 MCP 接入 Agent 主流程。

验收标准：

- 法官 Agent 能引用历史记录。
- 成本计算工具能返回预算或时间成本结果。
- 冷静期工具能创建观察清单或提醒任务。
- 一条购物决策链路能完整跑通。
- 一条时间决策链路能完整跑通。

### 第 3 周：前端、测试、部署和演示环境

目标：

- 完成 Web 前端。
- 完成测试用例。
- 完成部署或本地一键启动脚本。
- 完成前后端、RAG、MCP、Agent 全链路联调。
- 冻结一套稳定可演示版本。

验收标准：

- 前端能完整演示购物决策。
- 前端能完整演示时间决策。
- 能展示 RAG 检索结果。
- 能展示 MCP 工具调用结果。
- 能生成最终判决书。
- `main` 分支保留稳定可演示版本。

## 4. 每日详细计划

### 第 1 周

| 天数 | 目标 | 主要负责人 | 输出物 |
|---|---|---|---|
| Day 1 | 明确实现范围和技术选型 | 全员 | 技术栈、目录、接口草案 |
| Day 2 | 搭建基础工程和本地运行方式 | B / E | 后端启动、工具模块骨架、README 运行说明 |
| Day 3 | 跑通 LLM API 和基础后端 | B / C | `/api/chat` Demo、LLM 调用 Demo |
| Day 4 | 完成多 Agent Prompt 初版 | C | 正方、反方、法官输出 |
| Day 5 | 准备历史记录样例和 RAG 初版 | D | 样例数据、检索 Demo |
| Day 6 | 前端基础页面 | A | 创建案件页面 |
| Day 7 | 第一次阶段演示 | 全员 | 命令行或页面 Demo |

### 第 2 周

| 天数 | 目标 | 主要负责人 | 输出物 |
|---|---|---|---|
| Day 8 | 完成 RAG 接入 Agent | C / D | 法官可引用历史记录 |
| Day 9 | 实现成本计算工具 | E | cost_analyzer |
| Day 10 | 实现冷静期提醒工具 | E | cooling_reminder |
| Day 11 | Agent 接入两个 MCP 工具 | C / E | 工具调用链路 |
| Day 12 | 完成购物决策完整流程 | A / B / C / D / E | 购物 Demo |
| Day 13 | 完成时间决策完整流程 | A / B / C / D / E | 时间 Demo |
| Day 14 | 第二次阶段演示和问题修复 | 全员 | 可运行集成版本 |

### 第 3 周

| 天数 | 目标 | 主要负责人 | 输出物 |
|---|---|---|---|
| Day 15 | 前端完善和结果页展示 | A | 判决书页面 |
| Day 16 | 测试用例和评测指标 | D / E | RAG 评测、工具测试、端到端测试 |
| Day 17 | Docker 或一键启动脚本 | E | 可复现运行环境 |
| Day 18 | 联调修复和体验优化 | 全员 | 稳定集成版本 |
| Day 19 | 全流程压测和边界 case 修复 | 全员 | 缺陷修复清单 |
| Day 20 | 演示环境冻结和全流程彩排 | 全员 | 可演示版本 |
| Day 21 | 最终修复、合并 main、提交 | 全员 | v1.0-demo |

## 5. 具体里程碑

| 里程碑 | 内容 | 负责人 | 截止时间 |
|---|---|---|---|
| M1 | 完成基础工程和本地启动 | B / E | 第 1 周第 2 天 |
| M2 | 完成前端案件创建页 | A | 第 1 周第 6 天 |
| M3 | 跑通 LLM API | C | 第 1 周第 3 天 |
| M4 | 完成多 Agent 基础流程 | C | 第 1 周第 5 天 |
| M5 | 完成历史记录样例数据 | D | 第 1 周第 5 天 |
| M6 | 完成 RAG 检索 | D | 第 2 周第 2 天 |
| M7 | 完成成本计算 MCP 工具 | E | 第 2 周第 3 天 |
| M8 | 完成冷静期提醒 MCP 工具 | E | 第 2 周第 4 天 |
| M9 | Agent 接入 RAG 和 MCP | C / D / E | 第 2 周第 6 天 |
| M10 | 完成前端主流程 | A / B | 第 3 周第 2 天 |
| M11 | 完成测试和缺陷修复 | 全员 | 第 3 周第 4 天 |
| M12 | 完成部署和演示环境冻结 | E / 全员 | 第 3 周第 6 天 |

## 6. 各角色交付清单

### 6.1 目录责任分工

| 成员 | 主要负责目录 | 配合目录 | 说明 |
|---|---|---|---|
| A 前端交互开发 | `frontend/` | `backend/` | 负责页面、交互、结果展示、接口联调 |
| B 后端 API 与状态管理 | `backend/` | `tests/`、`data/` | 负责 API、数据库、案件状态、多轮会话状态 |
| C Agent 编排与 LLM 调用 | `backend/` | `mcp_tools/`、`rag/` | 负责 LLM 接入、多 Agent 工作流、Prompt 模板、判决书生成 |
| D RAG 与数据检索 | `rag/`、`data/` | `backend/`、`tests/` | 负责样例数据、知识库、检索逻辑、证据引用 |
| E MCP 工具与工程化 | `mcp_tools/`、`tests/` | `backend/`、部署文件 | 负责 MCP 工具、工具测试、调用日志、Docker 或一键启动 |

开发要求：

- 每个成员优先在自己的负责目录内开发。
- 跨目录修改必须在 PR 说明中写清楚原因。
- 修改接口时，必须同步更新 `docs/04_API.md`。
- 修改功能范围时，必须同步更新 `docs/01_MVP.md` 或 `docs/02_SPEC.md`。
- 修改验收方式时，必须同步更新 `docs/05_TestPlan.md`。

### 6.2 角色交付清单

### A 前端交互开发

- 案件创建页。
- 多轮对话页。
- 判决书结果页。
- RAG 证据展示区。
- MCP 工具调用结果展示区。
- 前端与后端 API 联调。

### B 后端 API 与状态管理

- FastAPI 项目结构。
- 案件创建、查询、更新接口。
- 多轮消息接口。
- SQLite 数据表和基础 CRUD。
- 案件状态流转。
- 后端接口错误处理。

### C Agent 编排与 LLM 调用

- LLM API 接入。
- Prompt 模板。
- 输入解析 Agent。
- 正方 Agent。
- 反方 Agent。
- 法官 Agent。
- 多 Agent 编排。
- 判决书生成逻辑。

### D RAG 与数据检索

- 历史记录数据结构。
- 模拟数据。
- 检索模块。
- 检索结果格式。
- RAG 评测样例。

### E MCP 工具与工程化

- cost_analyzer。
- cooling_reminder。
- 可选 decision_score。
- 工具调用日志。
- 工具单元测试。
- 部署脚本。
- 一键启动脚本。

## 7. 风险与预案

| 风险 | 影响 | 预案 |
|---|---|---|
| LLM API 不稳定 | Agent 无法输出 | 准备备用模型或 mock 输出 |
| RAG 效果差 | 法官依据不足 | 使用高质量模拟历史记录 |
| MCP 工具接入慢 | 课程要求受影响 | 先做 HTTP 接口形式，再封装 MCP |
| 前端来不及 | 演示困难 | 先用 Streamlit 或简洁 Web 页面 |
| 范围失控 | 三周做不完 | 只保留购物和时间两类案件 |
| 结果太主观 | 答辩说服力下降 | 强制输出证据和工具结果 |

## 8. 每日同步格式

```text
昨天完成：
今天计划：
当前卡点：
需要谁配合：
```

## 9. 当前进度同步

### 9.1 C 模块购物法庭进度

截至当前 `dev` 分支，C 模块已完成购物法庭 Agent 编排主流程，并已完成与 B 后端 adapter、E MCP 工具 adapter、DeepSeek 真实 LLM 的阶段性集成。

已完成内容：

- 完成 `input_parser`、`pro_agent`、`con_agent`、`judge_agent` 四个 Agent 的基础实现。
- 完成购物法庭多 Agent 编排流程。
- 完成 DeepSeek 真实 LLM API 接入，模型固定为 `deepseek-v4-pro`，未配置 Key 或 API 失败时自动 fallback 到 mock。
- 完成 mock RAG 接入位置。
- 完成 C-E MCP adapter，当前主流程已通过 `backend/app/services/mcp_adapter.py` 调用 E 模块 `cost_analyzer` 和 `cooling_reminder`。
- 完成 C-B 后端 adapter，当前通过 `backend/app/orchestrator/adapter.py` 向 B 后端提供 `run_case_decision_flow` 调用入口。
- 完成结构化 `DecisionReport` 输出。
- 完成 `AgentStep`、`ToolResult`、`RagEvidence`、`TraceItem` 输出。
- 完成高风险输入拦截，高风险输入不会进入正反方辩论。
- 完成 RAG 为空时不编造历史证据的处理。
- 完成 RAG / MCP 异常兜底，异常不会直接中断 Agent 主流程。
- 完成命令行 demo。
- 完成 C 模块 Agent 编排测试、MCP adapter 测试和 DeepSeek LLM client 测试。

当前验证命令：

```bash
uv run python -m backend.app.orchestrator.demo
uv run pytest tests/test_agent_flow.py tests/test_mcp_adapter.py tests/test_llm_client.py
uv run python -m compileall backend tests mcp_tools
```

下一步计划：

- 与 D 模块对齐真实 RAG 检索返回结构和调用方式，后续用 C-D RAG adapter 替换当前 `mock_rag`。
- 等 A/B 完成前端真实接口链路后，配合验收 `steps`、`rag_evidence`、`tool_results`、`report`、`trace` 展示。

### 9.2 C 模块当前完成度判断

购物法庭 C 模块本体已基本跑通，并完成 B/E 两侧关键 adapter 集成和 DeepSeek 真实 LLM 接入，当前购物流程完成度约为 90%。

整体 C 模块仍需完成：

- 真实 RAG 模块替换 mock RAG。
- time 时间决策流程。
- 前后端完整链路联调。

### 9.3 D 模块 RAG 当前进度

截至当前 `dev` 分支，D 模块已合并 RAG 初版代码，目录为 `rag/`。

已完成内容：

- 新增 `rag/retriever.py`，提供基于 FastAPI 的 `/api/rag/search` 检索接口雏形。
- 使用 `jieba` 分词和 `rank_bm25` 实现 BM25 检索。
- 请求结构与 `docs/04_API.md` 中的 RAG 检索接口基本对齐，包括 `user_id`、`case_id`、`case_type`、`query`、`top_k`。
- 返回结构采用 `success / data.results / message` 形式，目标是返回 `RagEvidence[]`。

当前限制：

- C 模块主流程仍调用 `backend/app/services/mock_rag.py`，尚未接入 D 的真实 RAG。
- `rag/data_loader.py` 读取 `data/history_records.json`，但当前仓库尚未看到该数据文件，需要 D 确认数据文件路径、是否提交演示数据或由启动脚本生成。
- `rag/retriever.py` 当前更像独立 FastAPI 服务，C 需要和 D 确认最终是通过 HTTP 调用，还是提供 Python 函数/adapter 供 C 直接调用。
- RAG 依赖记录在 `rag/requirements.txt`，但是否纳入项目统一 `pyproject.toml` / `uv` 环境仍需确认。

下一步计划：

- C 与 D 对齐 RAG 调用入口、返回字段、异常行为和启动方式。
- C 新增 RAG adapter，将 D 返回结果转换为 C 侧稳定的 `RagEvidence[]`。
- 保留 RAG 失败时 fallback 为 `[]` 的行为，确保 Agent 主流程不中断且不编造历史证据。
