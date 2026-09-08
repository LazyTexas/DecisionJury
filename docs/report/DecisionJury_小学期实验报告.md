<!-- 本文件由 docs/report/merge_report.py 自动生成，请勿直接编辑；修改请编辑 sections/ 下的对应文件。 -->

# DecisionJury 小学期实验报告

> 项目名称：DecisionJury——基于多 Agent 协作的日常冷静决策助手
> 课程名称：综合能力实训
> 本文档为章节合并版，最终排版请使用学校 Word 模板 `小学期实验报告模板(1).docx`。

---

# 00 封面、摘要与引言

> 负责人：组长（全员确认）
> 状态：待填写
> 目标页数：封面 1 页 + 摘要 1 页 + 引言约 1 页
> 素材：`README.md`、`docs/01_MVP.md`、`docs/02_SPEC.md`、`docs/03_Milestones.md`、`docs/07_Architecture_Description.md`

---

## 0.1 封面信息（Word 模板第一页）

> 以下字段按学校模板填写；项目名称、班级、专业、任课教师以实际为准。

| 字段 | 内容 |
|---|---|
| 课程名称 | 综合能力实训 |
| 项目名称 | DecisionJury——基于多 Agent 协作的日常冷静决策助手 |
| 班级 | 【待填写：班级】 |
| 专业 | 【待填写：专业】 |
| 任课教师 | 魏振文、赵双华（以模板为准） |
| 学号 | 【待填写：本人学号，多人写全组】 |
| 姓名 | 【待填写：成员姓名，按小组顺序】 |
| 实践报告成绩 | （由指导教师填写） |

---

## 0.2 摘要

> 要求：中文摘要 200～300 字；用第三人称；不出现“本文、论文、作者、本人、我们”；不出现公式、插图、表格、参考文献序号；英文缩写首次出现注明全称。

【待填写：摘要正文】

写作建议（可直接改写为正式摘要）：

- 第一句：说明研究对象与范围，例如“对基于多 Agent 协作的日常低风险决策助手 DecisionJury 的设计与实现进行了研究”。
- 第二句：说明系统解决的核心问题，例如“针对大学生购物决策中存在冲动消费、历史经验难以复用、时间安排缺乏证据支持等问题”。
- 第三句：说明采用的技术方案，例如“采用 FastAPI 后端、React 前端、多个大语言模型 Agent、历史记录 RAG 检索和 MCP 工具调用”。
- 第四句：说明系统主要流程，例如“通过多轮信息补全、正反方法庭式辩论、法官 Agent 裁决，生成可解释的决策判决书，并提供冷静期提醒”。
- 第五句：说明验证方式与结论，例如“在购物与时间两类案例上完成了全流程演示，并通过自动化测试验证了核心接口与 Agent 编排”。

## 0.3 关键词

> 要求：4～8 个，用分号隔开；不要用一句话；不要用太泛指的词。

【待填写：关键词草稿】

建议（可调整排序与用词）：

```text
多 Agent 协作；大语言模型；检索增强生成（RAG）；MCP 工具；决策支持系统；冷静期提醒；正反方辩论；低风险决策
```

---

## 0.4 引言

> 要求：简洁明了，不宜出现图表；五号字，首行缩进 2 字符；说明背景、目的、范围、意义、已有工作、研究设想、预期结果等。

### 0.4.1 选题背景

【待填写：从以下要点选择 2～3 点展开】

- 大学生日常生活中存在大量低风险决策，如“要不要买某个商品”“要不要参加某个活动/接某个任务”。
- 信息过载与促销/种草容易诱发冲动消费；时间安排上容易低估任务占用、带来延期压力。
- 普通 AI 问答通常只给单一结论，缺少正反理由、个人历史经验与结构化成本分析。

### 0.4.2 研究目的与意义

【待填写：1～2 段】

建议从以下角度写：

- 目的：完成一个可运行、可演示、可解释的多 Agent 冷静决策助手。
- 意义 1：把“决策”从单点建议变成“看清动机 → 补全信息 → 检索历史 → 计算成本 → 正反分析 → 输出建议 → 设置冷静期”的完整流程。
- 意义 2：验证 RAG、MCP 工具与多 Agent 编排在低风险日常决策场景中的落地可行性。

### 0.4.3 项目边界

【待填写：1 段】

必须写清：

- 本项目只支持购物决策和时间决策两类低风险决策。
- 不支持医疗、法律、投资理财、借贷、就业离职、亲密关系等高风险决策；系统会拒绝并提示范围。
- 系统输出为辅助建议，不是强制结论，避免“必须/一定”等绝对化表述。

### 0.4.4 已有工作基础

【待填写：1 段】

可参考仓库中已有内容，但必须与真实完成情况一致：

- 项目采用 FastAPI + SQLite 后端、React + Vite 前端。
- Agent 编排包含输入解析、正方、反方、法官四个 Agent，接入大语言模型并保留 mock fallback。
- RAG 采用 jieba 分词 + BM25 检索，提供 500 条历史样本，并与后端历史记录联动。
- MCP 工具已包含成本计算、冷静期提醒和可选决策评分，并记录调用日志。

### 0.4.5 论文组织结构

【待填写：1 段】

示例：

```text
本文共分为六章：第一章项目概述；第二章需求分析；第三章设计方案；第四章项目实现；第五章项目测试；第六章项目总结。
```

<!-- TODO: 若学校模板要求“结论”章节，请按模板顺序调整章节号。 -->

---

# 01 项目概述

> 负责人：C（组长），B 配合
> 状态：待填写
> 目标页数：约 2 页
> 素材：`README.md`、`docs/01_MVP.md`、`docs/02_SPEC.md`、`docs/03_Milestones.md`

---

## 1.1 项目背景

【待填写：从以下要点组织成 2～3 段】

- 大学生是购物决策和时间决策的高频人群：容易因促销、种草、情绪驱动购买；也容易低估活动/任务的时间成本。
- 普通问答助手大多只输出“推荐/不推荐”，缺少正反理由、个人历史经验和结构化工具结果。
- 本项目面向低风险日常决策，通过多 Agent 协作、RAG 历史检索和 MCP 工具调用，生成一份可解释的“决策判决书”。
- 项目选择购物决策和时间决策两类场景，既满足课程对 LLM、RAG、MCP、多轮对话和 Web 演示的要求，又控制了三周开发范围。

## 1.2 项目简介

【待填写：用 1 段文字总体介绍】

写作要点：

- 系统名称：DecisionJury（多 Agent 冷静决策助手）。
- 面向对象：预算有限、容易被种草的大学生；任务较多、难以拒绝的学生群体。
- 核心流程：用户提交决策 → 多轮补全信息 → RAG 检索历史 → MCP 工具计算成本/设提醒 → 正方 Agent、反方 Agent 辩论 → 法官 Agent 裁决 → 生成判决书 → 复盘进入历史库形成闭环。
- 技术形态：Web 应用（React 前端 + FastAPI 后端），Agent 编排与 LLM 调用在后端，RAG 独立服务，工具以 MCP 契约提供。
- 输出形式：结构化判决书，包含案件摘要、正反方观点、RAG 证据、工具结果、最终裁决、后续动作。

## 1.3 项目计划

【表格：按实际进度填写；下面为仓库里程碑计划，可作为初稿】

| 阶段 | 时间 | 目标 | 主要输出 | 状态（按实际更新） |
|---|---|---|---|---|
| 第 1 周 | 第 1～7 天 | 基础链路跑通 | 文档、仓库、后端启动、LLM 调用、多 Agent 基础流程、案件创建与简单对话 | 【待填写：已完成/进行中】 |
| 第 2 周 | 第 8～14 天 | RAG 与 MCP 工具接入 | 历史数据、BM25 检索、cost_analyzer、cooling_reminder、完整购物/时间链路 | 【待填写】 |
| 第 3 周 | 第 15～21 天 | 前端、测试、部署与演示 | 前端全流程、测试用例、一键启动、演示环境冻结、答辩材料 | 【待填写】 |

> 详细每日计划见 `docs/03_Milestones.md`，团队分工见 `docs/03_Milestones.md` 第 2 节，报告章节分工见 `docs/report/README.md`。

## 1.4 开发团队与分工

【表格：5 人分工，与仓库 `docs/03_Milestones.md` 保持一致】

| 成员 | 实现方向 | 主要职责 | 对应报告章节 |
|---|---|---|---|
| A | 前端交互开发 | 页面结构、案件创建、多轮对话、判决书展示、RAG/MCP 结果展示 | 2、3.4、4.2、5.3 |
| B | 后端 API 与状态管理 | FastAPI 接口、案件 CRUD、SQLite、多轮状态、接口联调 | 3.1、4.1、4.2 |
| C | Agent 编排与 LLM 调用 | LLM 接入、输入解析/正方/反方/法官 Agent、Prompt、判决书 | 1、3.3、4.2 |
| D | RAG 与数据检索 | 历史记录、规则库、BM25/混合检索、证据引用、RAG 评测 | 3.1、3.3、4.2、5 |
| E | MCP 工具与工程化 | cost_analyzer、cooling_reminder、decision_score、工具日志、测试、部署 | 3.3、4.2、5 |

---

# 02 需求分析

> 负责人：A，B 配合
> 状态：待填写
> 目标页数：约 3 页
> 素材：`docs/01_MVP.md`、`docs/02_SPEC.md`、`docs/04_API.md`

---

## 2.1 功能需求

### 2.1.1 用户与账号（已实现范围以实际为准）

| 编号 | 功能 | 说明 | 对接接口 |
|---|---|---|---|
| FR-01 | 用户注册/登录 | 支持用户创建账号和登录，用于区分历史记录与案件 | `POST /auth/register`、`POST /auth/login` |
| FR-02 | 创建决策案件 | 支持购物决策与时间决策两类案件 | `POST /api/cases` |
| FR-03 | 多轮信息补全 | 系统根据缺失字段向用户追问，用户逐项补充 | `POST /api/cases/{case_id}/messages` |
| FR-04 | 启动多 Agent 分析 | 触发输入解析、正方、反方、法官 Agent 编排 | `POST /api/cases/{case_id}/debate` |
| FR-05 | RAG 历史检索 | 检索用户历史决策/闲置/后悔/任务延期记录，返回可引用证据 | `POST /api/rag/search` |
| FR-06 | MCP 工具调用 | 调用成本计算、冷静期提醒、可选决策评分 | `POST /api/tools/*` |
| FR-07 | 判决书生成 | 输出结构化报告，包含正反观点、证据、工具结果和最终裁决 | `GET /api/cases/{case_id}/report` |
| FR-08 | 执行轨迹展示 | 展示 Agent/RAG/工具调用顺序、耗时与状态 | `GET /api/cases/{case_id}/trace` |
| FR-09 | 历史记录管理 | 查看/新增历史记录，支持复盘后自动写入 | `GET /api/history`、`POST /api/history` |
| FR-10 | 观察清单 | 展示冷静期提醒与待复盘项 | `GET /api/watchlist`、`DELETE /api/watchlist/{id}` |
| FR-11 | 决策复盘 | 用户提交实际行为、满意度和复盘文本，形成闭环 | `POST /api/cases/{case_id}/feedback` |

### 2.1.2 业务流程：购物决策

```text
用户输入“想买 1299 元降噪耳机”
  -> 识别为购物案件，追问预算、已有替代品
  -> 信息补全后进入 ready_for_debate
  -> RAG 检索历史电子产品/闲置/预算记录
  -> cost_analyzer 计算预算占比与风险等级
  -> 正方 Agent 分析购买价值、使用频率
  -> 反方 Agent 分析冲动/闲置/平替风险
  -> judge_agent 输出 buy / delay / reject / alternative
  -> 如建议暂缓，调用 cooling_reminder 创建观察清单
```

### 2.1.3 业务流程：时间决策

```text
用户输入“要不要参加占用周末两天的社团活动”
  -> 识别为时间案件，追问当前任务、活动收益、可否部分参加
  -> 信息补全后进入 ready_for_debate
  -> RAG 检索历史任务延期/活动复盘记录
  -> cost_analyzer 计算时间占用与冲突等级
  -> 正方 Agent 分析成长/人际收益
  -> 反方 Agent 分析延期/精力/机会成本
  -> judge_agent 输出 accept / partial_accept / delay / reject
  -> 根据结果生成后续待办或观察项
```

### 2.1.4 输入边界与拒绝策略

| 输入类型 | 系统行为 |
|---|---|
| 购物决策 | 进入购物流程，最终给出购买/暂缓/不购买/替代方案建议 |
| 时间决策 | 进入时间流程，最终给出接受/部分接受/推迟/拒绝建议 |
| 医疗、法律、投资、借贷、就业离职、亲密关系等 | 拒绝裁决，提示仅支持低风险日常决策 |
| 信息不完整 | 保持收集状态，继续追问，不进入辩论 |

### 2.1.5 可选/拓展功能

【表格：按实际完成情况勾选】

| 功能 | 是否完成 | 说明 |
|---|---|---|
| 决策评分工具 decision_score | 【待填写】 | 0~100 综合分，供法官参考 |
| Agent 调用链路可视化 | 【待填写】 | 前端 trace 展示 |
| Docker / 一键部署 | 【待填写】 | Windows `start_all.bat`、Linux `deploy/*.sh` |
| RAG 量化评测指标 | 【待填写】 | `rag/evaluate_rag*.py` |

## 2.2 非功能需求

### 2.2.1 性能需求

【待填写：结合真实运行情况填写】

- 单次普通对话响应时间：目标 10 秒内（LLM 超时可按 `DEEPSEEK_TIMEOUT_SECONDS` 配置）。
- 主流程异常兜底：LLM、RAG、MCP 工具失败时不应中断整条流程。

### 2.2.2 可解释性需求

- 判决书必须列出正反方理由、RAG 证据、工具结果与最终裁决。
- RAG 无结果时明确说明未找到历史记录，不允许编造。
- 工具失败时保留 Agent 分析，并标记工具结果缺失。

### 2.2.3 可靠性与安全性需求

- 接口统一返回 `{success, data, message}`，错误使用统一错误码。
- SQLite 数据本地存储，不保存真实敏感消费记录，不接入真实支付/电商登录。
- 用户密码使用哈希存储（当前仓库使用 passlib，以实际代码为准）。
- 高风险输入必须被拦截，避免项目范围溢出。

### 2.2.4 可维护性需求

- Prompt、工具、数据结构分文件管理。
- 公共数据结构（`Case`、`AgentStep`、`RagEvidence`、`ToolResult`、`DecisionReport`、`TraceItem`）统一在 `docs/04_API.md` 中维护。
- 接口字段统一 `snake_case`，枚举统一小写 `snake_case`。

### 2.2.5 可演示性需求

- 支持一条购物决策完整演示：创建案件 → 补全 → RAG → 工具 → 辩论 → 判决书 → 复盘。
- 支持一条时间决策完整演示（按实际完成程度填写）。
- 关键过程可通过 trace 展示，关键工具调用有日志可查。

---

# 03 设计方案

> 负责人：B，A/C/D/E 配合
> 状态：待填写
> 目标页数：约 5～7 页（含图、表、流程图）
> 素材：`docs/02_SPEC.md`、`docs/04_API.md`、`docs/05_TestPlan.md`、`docs/07_Architecture_Description.md`、`backend/`、`rag/`、`mcp_tools/`

---

## 3.1 数据描述

### 3.1.1 数据存储总体设计

项目使用 SQLite 保存业务数据（实际表名以代码为准，以下为设计/预计），RAG 知识库使用 JSON 文件。

| 表/文件 | 用途 | 主要字段 |
|---|---|---|
| `users` | 用户账号 | user_id、name、密码哈希、created_at |
| `cases` | 决策案件 | case_id、user_id、case_type、title、description、status、collected_fields、final_decision、created_at、updated_at |
| `messages` | 多轮对话消息 | message_id、case_id、role、content、created_at |
| `histories` / `data/history_records.json` | 历史决策记录 | history_id、user_id、case_type、title、summary、result、tags、created_at |
| `traces` | Agent 执行轨迹 | trace_id、case_id、step、type、name、input_summary、output_summary、duration_ms、status、error |
| `reminders` / 观察清单 | 冷静期提醒 | reminder_id、case_id、title、due_at、status、watch_items |
| `data/rag_*.json` | RAG 评测结果 | 检索命中、指标结果（P/R/MRR/NDCG 等，按实际文件填写） |

### 3.1.2 核心数据结构

【表格：与 `docs/04_API.md` 保持一致，建议用统一格式]

- `Case`
- `Message`
- `AgentStep`
- `RagEvidence`
- `ToolResult`
- `DecisionReport`
- `TraceItem`

### 3.1.3 历史记录样例数据

【表格：列出实际使用的样例，至少体现“闲置/后悔/值得/延期”等类型】

| 类型 | 样例 | 标签 |
|---|---|---|
| 购物-闲置 | 购买机械键盘 399 元后使用频率较低 | electronics、idle、regret |
| 购物-值得 | 购买学习台灯 129 元后每天使用 | study、useful、worth |
| 时间-延期 | 参加社团活动占用 8 小时，导致课程作业延期 | club、delay、regret |
| 时间-值得 | 参加 2 小时技术分享，收获较高 | tech、low_cost、worth |

> 完整样例见 `data/history_records.json`（500 条，购物 250 + 时间 250）与 `docs/05_TestPlan.md` 第 3 节。

## 3.2 功能设计

### 3.2.1 功能列表

【表格：功能 → 模块 → 说明 → 主要接口】

| 功能 | 模块 | 说明 | 主要接口 |
|---|---|---|---|
| 用户注册/登录 | A/B | 认证 | `POST /auth/register`、`POST /auth/login` |
| 创建案件 | A/B | 创建购物/时间案件 | `POST /api/cases` |
| 多轮补全 | A/B/C | 提取字段、追问缺失字段 | `POST /api/cases/{id}/messages` |
| Agent 辩论 | B/C | 正方、反方、法官编排 | `POST /api/cases/{id}/debate` |
| RAG 检索 | D | BM25 检索历史记录 | `POST /api/rag/search` |
| MCP 工具 | E | 成本/提醒/评分 | `POST /api/tools/*` |
| 判决书 | B/C | 结构化报告 | `GET /api/cases/{id}/report` |
| 执行轨迹 | B/C | trace 展示 | `GET /api/cases/{id}/trace` |
| 历史记录 | B/D | 查询/新增 | `GET|POST /api/history` |
| 观察清单 | B/E | 冷静期提醒 | `GET /api/watchlist` |
| 决策复盘 | B | 反馈入历史库 | `POST /api/cases/{id}/feedback` |

### 3.2.2 模块分层设计

```text
前端 (React + Vite, :5173)
  |
后端主服务 (FastAPI, :8000)  -- SQLite
  |
Agent 编排 (C)
  |-- LLM 客户端 (DeepSeek + Mock fallback)
  |-- RAG 适配器 (HTTP -> :8001)
  |-- MCP 适配器 (cost_analyzer / cooling_reminder / decision_score)
  |
RAG 服务 (FastAPI, :8001) -- jieba + BM25 -- data/history_records.json + /api/history 联动
```

## 3.3 关键算法说明

### 3.3.1 多 Agent 编排流程（C 模块）

```text
input_parser(识别类型、提取字段、风险标记)
  -> 信息不完整：追问，等待用户补充
  -> RAG 检索：mock/HTTP 适配，返回 RagEvidence[]
  -> cost_analyzer：计算预算/时间成本
  -> decision_score（可选）：0~100 综合评分
  -> pro_agent：正方分析收益
  -> con_agent：反方分析风险与替代方案
  -> cooling_reminder：根据裁决结果创建冷静期提醒
  -> judge_agent：综合输出 DecisionReport + DebateEvent
  -> 保存 trace / report / reminders
```

【流程图：插入“多 Agent 编排流程图”，可用 Visio/ProcessOn 绘制，Word 中图下居中写图题】

### 3.3.2 输入解析与字段补全

- 优先调用大语言模型解析用户输入，输出 `case_type`、`extracted_fields`、`missing_fields`、`next_question`。
- 解析失败或未配置 API Key 时回退本地规则解析（以实际代码为准）。
- 高风险输入（医疗/法律/投资/借贷/就业离职/亲密关系等）标记 `is_high_risk`，不进入正反方辩论。

【代码片段：`backend/app/orchestrator/` 中 input_parser 或本地规则解析入口，选择 10～20 行关键代码】

### 3.3.3 RAG 检索算法（D 模块）

- 分词：jieba 中文分词。
- 检索模型：BM25Okapi（rank_bm25），当前 MVP 未使用向量库。
- 数据来源：`data/history_records.json` 静态 500 条 + 实时拉取后端 `/api/history`，按 `user_id` 过滤合并。
- 返回格式：`RagEvidence[]`，按相关性分数排序，case_type 隔离。
- 无结果时返回空数组，不允许编造历史记录。

【代码片段：`rag/retriever.py` 检索主函数与 `rag/data_loader.py` 数据合并/去重逻辑】

### 3.3.4 成本计算算法（E 模块）

- 购物场景：`budget_ratio = price / monthly_budget_left`，按阈值给出 low / medium / high 风险等级。
- 时间场景：`time_ratio = hours_required / free_hours_this_week`，结合 urgent_tasks 给出风险等级。
- 输出统一 `ToolResult`，失败时 `status=failed`，不中断主流程。

【代码片段：`mcp_tools/cost_analyzer.py` 核心判断逻辑】

### 3.3.5 冷静期提醒算法（E 模块）

- 输入：user_id、case_id、title、cooling_days、reason、watch_items。
- 输出：`reminder_id`、`due_at`、`status=scheduled`，并写入 `reminders` 表。
- 用于将“暂缓/部分参加”等建议转化为可执行的后续动作。

【代码片段：`mcp_tools/cooling_reminder.py` 关键函数】

### 3.3.6 决策评分算法（可选，E 模块）

- 输出 0~100 综合分，维度包括成本、历史风险、使用价值、冲动因素。
- 分数仅供法官参考，不直接决定最终裁决。

【代码片段：`mcp_tools/decision_score.py`，若实际已实现则填写】

## 3.4 原型图设计

### 3.4.1 首页 / 案件创建页

【截图：首页与创建案件页原型图/最终界面截图】

说明要点：

- 用户可输入决策描述，选择案件类型或由系统识别。
- 展示高风险边界提示与输入示例。

### 3.4.2 多轮对话页

【截图：多轮对话页原型图/最终界面截图】

说明要点：

- 展示当前收集到的字段、缺失字段与系统追问。
- 用户补充信息后实时更新状态。

### 3.4.3 判决书页面

【截图：判决书页原型图/最终界面截图】

说明要点：

- 展示案件摘要、正方观点、反方观点、RAG 证据、工具结果、最终裁决、后续动作。
- 支持查看 trace（执行轨迹），方便答辩演示。

### 3.4.4 历史与观察清单页面

【截图：历史记录页、观察清单页】

说明要点：

- 历史记录用于证明 RAG 素材来自真实复盘。
- 观察清单展示冷静期提醒的到期时间与状态。

> 原型图可用 ProcessOn/墨刀/Figma 绘制；Word 中建议“图题在图下方居中，表题在表上方居中”，并在正文写明“如图 X 所示”。

---

# 04 项目实现

> 负责人：C，A/B/D/E 配合
> 状态：待填写
> 目标页数：约 6～9 页（含架构图、关键代码、接口表）
> 素材：`backend/`、`frontend/`、`rag/`、`mcp_tools/`、`docs/04_API.md`、`docs/07_Architecture_Description.md`

---

## 4.1 总体实现

### 4.1.1 系统整体架构

```text
浏览器（React + Vite，:5173）
  │  登录/注册、创建案件、多轮对话、判决书、历史、观察清单
  ▼
后端主服务（FastAPI，:8000）
  │  /api/cases、/api/history、/api/watchlist、/api/tools/*、/api/health
  │
  ├── SQLite（users / cases / messages / histories / traces / reminders）
  ├── Agent 编排（adapter → decision_flow）
  │     ├── input_parser：类型识别 + 字段提取 + 高风险标记
  │     ├── RAG 适配器：HTTP 调用 :8001
  │     ├── MCP 适配器：cost_analyzer / cooling_reminder / decision_score
  │     ├── pro_agent / con_agent / judge_agent：调用 LLM
  │     └── 输出 DecisionReport / DebateEvent / TraceItem
  │
  ├── RAG 服务（FastAPI，:8001）
  │     └── jieba + BM25 → data/history_records.json + /api/history 实时联动
  └── 外部 LLM（DeepSeek，未配置时 Mock fallback）
```

【架构图：插入“系统分层架构图”，图下居中写图题】

### 4.1.2 项目目录结构

【表格或代码块：说明各目录职责】

| 目录 | 职责 |
|---|---|
| `frontend/` | React + Vite 前端，页面与交互 |
| `backend/` | FastAPI 接口、SQLite 数据、Agent 编排、LLM/RAG/MCP 适配 |
| `rag/` | 历史数据、BM25 检索、评测脚本 |
| `mcp_tools/` | cost_analyzer、cooling_reminder、decision_score、日志、MCP 契约 |
| `data/` | 演示数据、历史记录、评测结果 |
| `tests/` | 后端、RAG、MCP 工具和 Agent 测试 |
| `docs/` | 项目文档、API 契约、测试计划、协作规则 |

### 4.1.3 核心接口实现

【表格：与 `docs/04_API.md` 保持一致，只列已实现接口】

| 方法 | 路径 | 功能 | 实现位置 |
|---|---|---|---|
| GET | `/api/health` | 健康检查 | `backend/routers/health.py` |
| POST | `/api/cases` | 创建案件 | `backend/routers/cases.py` |
| GET/PATCH | `/api/cases/{case_id}` | 查询/更新案件 | `backend/routers/cases.py` |
| POST | `/api/cases/{case_id}/messages` | 多轮补充信息 | `backend/routers/chat.py` |
| POST | `/api/cases/{case_id}/debate` | 启动 Agent 分析 | `backend/routers/debate.py` |
| GET | `/api/cases/{case_id}/trace` | 查询执行轨迹 | `backend/routers/trace.py` |
| GET | `/api/cases/{case_id}/report` | 查询判决书 | `backend/routers/cases.py` |
| POST | `/api/cases/{case_id}/feedback` | 提交复盘 | `backend/routers/feedback.py` |
| GET/POST | `/api/history` | 历史记录 | `backend/routers/history.py` |
| GET/DELETE | `/api/watchlist` | 观察清单 | `backend/routers/watchlist.py` |
| POST | `/api/tools/cost-analyzer` | 成本计算 | `backend/routers/tools.py` |
| POST | `/api/tools/cooling-reminder` | 冷静期提醒 | `backend/routers/tools.py` |
| POST | `/api/tools/decision-score` | 决策评分 | `backend/routers/tools.py` |
| POST | `/api/rag/search` | RAG 检索 | `rag/retriever.py` |

【代码片段：选择一个路由的关键处理逻辑，例如创建案件或启动辩论，10～20 行】

### 4.1.4 数据库实现

| 表 | 关键字段 | 说明 |
|---|---|---|
| users | user_id、name、password 哈希 | 用户账号 |
| cases | case_id、case_type、status、collected_fields、final_decision | 决策案件与状态流转 |
| messages | case_id、role、content | 多轮对话 |
| histories | case_id、user_id、summary、result、tags、is_deleted | 历史记录（软删除） |
| traces | case_id、step、type、name、status、duration_ms | Agent 执行轨迹 |
| reminders | case_id、title、due_at、status | 冷静期提醒/观察清单 |

【说明：表名与字段以当前代码为准，若与上面不同请按实际更正。】

### 4.1.5 前端页面与交互

| 页面 | 功能 | 状态（按实际） |
|---|---|---|
| 登录/注册页 | 用户认证 | 【待填写】 |
| 首页/案件创建页 | 选择购物/时间决策，输入描述 | 【待填写】 |
| 多轮对话页 | 展示追问、补充字段、查看状态 | 【待填写】 |
| 辩论结果页 | 展示正方/反方/法官输出、RAG 证据、工具结果 | 【待填写】 |
| 判决书页 | 展示最终报告与后续动作 | 【待填写】 |
| 执行轨迹页 | 展示 trace 调用链 | 【待填写】 |
| 历史记录页 | 查看历史复盘 | 【待填写】 |
| 观察清单页 | 查看冷静期提醒 | 【待填写】 |

## 4.2 关键技术实现

### 4.2.1 多 Agent 编排与 LLM 调用（C）

实现要点：

- 输入解析 Agent、正方 Agent、反方 Agent、法官 Agent 使用 Markdown Prompt 文件管理（`backend/app/prompts/` 等，以实际路径为准）。
- LLM 客户端统一封装，支持 DeepSeek 调用与 mock fallback；未配置 Key、超时、非 JSON 输出时自动降级。
- 主流程输出 `AgentStep[]`、`RagEvidence[]`、`ToolResult[]`、`DecisionReport`、`TraceItem[]`。
- 高风险输入在入口拦截，不进入正反方辩论。

【代码片段：`decision_flow.py` 主流程编排，展示 Agent 调用顺序与异常兜底】

### 4.2.2 RAG 检索（D）

实现要点：

- 使用 jieba 分词 + rank_bm25 的 BM25Okapi 检索。
- 数据合并：静态 500 条 + 后端实时历史，按 user_id 拉取，按 id 去重。
- 检索结果按 `RagEvidence` 返回，case_type 隔离，无结果返回空数组。

【代码片段：`rag/retriever.py` 检索主流程，`rag/data_loader.py` 合并逻辑】

### 4.2.3 MCP 工具（E）

实现要点：

- `cost_analyzer`：购物预算占比、时间占用比与风险等级。
- `cooling_reminder`：生成冷静期提醒并写入 `reminders`。
- `decision_score`：0~100 综合评分（可选）。
- `logger.py`：记录工具调用输入、输出、耗时，便于答辩取证。
- `mcp.py`：定义工具 schema，统一 `call_tool(name, arguments)` 分发。

【代码片段：`mcp_tools/cost_analyzer.py` 核心计算；`mcp_tools/mcp.py` 契约分发】

### 4.2.4 后端 API 与状态管理（B）

实现要点：

- FastAPI 分层：路由 → 服务 → 数据访问。
- 案件状态流转：collecting → ready_for_debate → debating → completed（或 rejected）。
- 接口统一返回 `{success, data, message}`，统一异常处理。
- RAG 与工具失败不影响主流程，trace 记录失败原因。

【代码片段：案件状态流转或全局异常处理相关代码】

### 4.2.5 前端交互实现（A）

实现要点：

- 页面组件：创建案件、多轮对话、辩论结果、判决书、历史、观察清单、登录注册。
- 通过统一 REST 客户端调用后端 API。
- 展示 `steps`、`debate_events`、`rag_evidence`、`tool_results`、`trace`、`report`。

【截图或代码片段：前端关键组件/接口封装，建议配页面截图】

<!-- TODO: 若某一模块实际未完成（例如时间决策链路），请在报告中如实标注“待实现/进行中”，不要写成已完成。 -->

---

# 05 项目测试

> 负责人：E，A/B/C/D 配合
> 状态：待填写
> 目标页数：约 4～6 页（含截图、测试结果表）
> 素材：`docs/05_TestPlan.md`、`tests/`、`rag/evaluate_*.py`、`data/rag_*.json`

---

## 5.1 测试环境与项目部署

### 5.1.1 测试环境

【表格：按实际环境填写】

| 项 | 内容 |
|---|---|
| 操作系统 | 【待填写：Windows / Linux】 |
| Python 版本 | 【待填写：3.11+】 |
| Node.js 版本 | 【待填写】 |
| 数据库 | SQLite |
| LLM | 【待填写：DeepSeek / Mock】 |
| 端口 | 前端 5173、后端 8000、RAG 8001 |

### 5.1.2 部署/启动方式

```bash
# Windows 一键启动
start_all.bat

# 手动启动
uvicorn backend.main:app --reload        # 后端
npm run dev                               # 前端
uvicorn rag.retriever:app --port 8001     # RAG（按实际入口）
```

【截图：启动成功的终端/页面截图】

## 5.2 功能测试用例与结果

> 以下为仓库已有测试计划与测试文件；实际结果请以“运行 `pytest` 后”的真实输出为准，不得编造。

### 5.2.1 测试用例清单

【表格：覆盖功能 → 测试文件 → 期望结果 → 实际结果】

| 覆盖功能 | 测试文件 | 期望结果 | 实际结果 |
|---|---|---|---|
| 创建购物/时间案件 | `tests/test_cases_router.py` | 成功创建案件 | 【待填写】 |
| 多轮对话与状态流转 | `tests/test_chat_router.py` | 逐步补全、进入 ready | 【待填写】 |
| 多 Agent 辩论 | `tests/test_debate_router.py` | 正/反/法官按序输出 | 【待填写】 |
| 高风险输入拦截 | `tests/test_debate_router.py` | 拒绝并返回 HIGH_RISK_DECISION | 【待填写】 |
| RAG 检索 | `tests/test_rag.py`、`tests/test_rag_data_loader.py` | BM25 命中、隔离、防幻觉 | 【待填写】 |
| MCP 工具 | `tests/test_mcp_tools.py`、`tests/test_tools_router.py` | 成本/提醒/评分正常 | 【待填写】 |
| 执行轨迹 | `tests/test_trace_router.py` | 记录顺序与字段完整 | 【待填写】 |
| 决策复盘 | `tests/test_feedback_router.py` | 写入历史、更新观察清单 | 【待填写】 |

### 5.2.2 自动化测试执行结果

【截图：`pytest` 运行结果，填写实际通过数量】

```text
【待填写：运行命令】
pytest
【待填写：实际输出，例如】
N passed in X.XXs
```

> 仓库 `docs/05_TestPlan.md` 记录了不同模块的测试文件与测试数量，提交前请更新为最新真实结果。

### 5.2.3 手工演示用例

【表格：两条演示链路（购物、时间，时间流程按实际完成度填写）】

| 用例 | 步骤 | 预期 | 实际 |
|---|---|---|---|
| 购物决策演示 | 创建“想买 1299 元降噪耳机”→补全预算/替代品→启动辩论→查看 RAG/工具/判决书→复盘 | 全链路完成 | 【待填写】 |
| 时间决策演示 | 创建“是否参加占用周末两天的社团活动”→补全当前任务/收益→启动辩论→查看时间成本/判决 | 全链路完成 | 【待填写；若未完成请如实说明】 |

## 5.3 RAG 评测

【表格：按实际评测脚本输出填写】

| 指标 | 含义 | 结果 |
|---|---|---|
| Top-k 命中 | 检索结果是否包含预期类型 | 【待填写】 |
| 命中类型 | 是否命中购物/时间正确类别 | 【待填写】 |
| 是否进入法官上下文 | 证据是否被引用 | 【待填写】 |
| P/R/MRR/NDCG（如已实现） | 检索质量指标 | 【待填写】 |

> 参考工具：`rag/evaluate_rag.py`、`rag/evaluate_rag_standard.py`、`rag/evaluate_dialogue_quality.py`。

【截图：RAG 检索结果或评测输出截图】

## 5.4 代码缺陷与修复

【表格：按实际开发过程填写，示例格式如下】

| 编号 | 问题描述 | 影响 | 修复方式 | 验证 |
|---|---|---|---|---|
| BUG-01 | 【待填写】 | 【待填写】 | 【待填写】 | 【待填写】 |
| BUG-02 | 【待填写】 | 【待填写】 | 【待填写】 | 【待填写】 |

常见可写的问题（若实际遇到过）：

- LLM 输出非 JSON，导致解析失败 → 增加 fallback 与格式校验。
- RAG 返回空数组时要避免法官 Agent 编造历史 → 增加“未找到历史记录”提示。
- MCP 工具参数为空/负数 → 增加校验并转成 `failed` ToolResult。
- 前后端字段/枚举不一致 → 统一为 `snake_case` 并同步 API 文档。
- 案件反馈后观察清单状态未更新 → 增加联动逻辑。

## 5.5 项目展示

### 5.5.1 购物决策完整演示

【截图：创建案件页 → 多轮对话 → RAG 证据 → 成本工具 → 正反辩论 → 判决书 → 观察清单】

说明文字：

- 前端如何展示流程。
- RAG 命中了哪些历史记录。
- 工具返回了什么指标。
- 法官给出了什么裁决。

### 5.5.2 时间决策完整演示

【截图：时间案件创建、对话、时间成本结果、判决】

【待填写：若时间链路尚未完整实现，请如实说明当前进度，不要写成已完成】

### 5.5.3 Agent 执行轨迹展示

【截图：trace 面板或命令行动态】

说明文字：

- 展示 input_parser → RAG → cost_analyzer → pro → con → judge 的顺序。
- 展示每一步耗时、状态和失败兜底。

### 5.5.4 MCP 工具调用日志

【截图：工具调用日志 / demo 输出】

说明文字：

- 展示 cost_analyzer 输入输出。
- 展示 cooling_reminder 生成的提醒。
- 展示 decision_score（如已实现）。

---

# 06 项目总结

> 负责人：全员（各自模块总结后汇总）
> 状态：待填写
> 目标页数：约 2 页
> 素材：各模块开发记录、`docs/03_Milestones.md`、`docs/07_Architecture_Description.md`

---

## 6.1 项目总结与体会

### 6.1.1 项目整体完成情况

【待填写：1～2 段】

建议写：

- 本项目完成了 XX（如可运行 Web Demo、多 Agent 辩论、RAG、MCP 工具、判决书等），实现了哪些课程要求。
- 团队按 A/B/C/D/E 模块分工，通过分支 + PR 协作，最终合并到 `dev`/`main`。
- 系统可演示购物决策完整链路，并形成“历史记录 → RAG → 判决 → 复盘 → 历史记录”的闭环。

### 6.1.2 技术收获

【待填写：每模块 1～3 条，可由对应成员补充】

| 成员/模块 | 主要收获 |
|---|---|
| A 前端 | 【待填写：例如 React 状态管理、接口联调、多页面展示】 |
| B 后端 | 【待填写：例如 FastAPI 路由、SQLite 建模、状态流转、异常处理】 |
| C Agent | 【待填写：例如 Prompt 设计、LLM 调用与 fallback、多 Agent 编排】 |
| D RAG | 【待填写：例如 BM25 检索、数据构建、评测指标、防幻觉】 |
| E 工具与工程化 | 【待填写：例如 MCP 契约、工具边界测试、调用日志、一键启动】 |

### 6.1.3 团队协作体会

【待填写：2～3 段】

建议写：

- 通过每日同步（昨天完成/今天计划/当前卡点/需要谁配合）管理进度。
- 接口契约先行（`docs/04_API.md`），减少前后端与模块间联调成本。
- 遇到问题时如何定位、如何通过 trace/日志取证、如何 review 他人代码。

## 6.2 不足与改进

【表格：从以下方向筛选，结合实际填写】

| 不足 | 原因 | 改进方向 |
|---|---|---|
| 时间决策链路尚未完整实现（如属实） | 三周时间紧张，优先保证购物主链路 | 后续补齐 time 流程与演示 |
| RAG 目前为 BM25，未接入向量模型 | 数据规模小、时间有限 | 可升级为 embedding + 混合检索 |
| 用户认证功能仍待完善 | 优先级靠后 | 后续统一加入 JWT/权限控制 |
| 前端交互与移动端适配不足 | 时间有限 | 后续做响应式与体验优化 |
| 缺少真实用户数据，演示偏 demo | 隐私与数据获取限制 | 后续小范围试用并脱敏收集反馈 |
| 自动化测试覆盖仍不完整 | 以主链路为主 | 增加端到端和边界场景测试 |
| 部署仍以脚本为主，未完全容器化 | 可选加分项 | 后续补 Docker 部署与 CI |

【待填写：补充团队感受最深的其他不足和改进】

---

# 07 参考文献与附录

> 负责人：组长，全员配合
> 状态：待填写
> 目标页数：参考文献 1 页 + 附录可选 1～2 页
> 素材：学校模板格式说明、`docs/04_API.md`、`docs/03_Milestones.md`、`docs/05_TestPlan.md`

---

## 7.1 参考文献

> 格式参考 GB/T 7714-2015《信息与文献 参考文献著录规则》。
> 正文中须用上标序号 [1] 等标注引用位置，且参考文献建议以近 5 年权威期刊/教材/文档为主。

### 7.1.1 参考文献列表（按实际引用填写）

```text
[1] 【待填写：作者.题名[文献类型标识].出版地:出版者,出版年:起止页码.】
[2] 【待填写：作者.题名[J].刊名,出版年,卷(期):页码.】
[3] 【待填写：作者.题名[C]//会议论文集名.出版地:出版者,出版年:页码.】
[4] 【待填写：作者.题名[EB/OL].发布日期/引用日期.获取地址.】
```

### 7.1.2 可按需引用的主题素材

- 检索增强生成（RAG）：可引用 RAG 相关综述或论文。
- 大语言模型 Agent：可引用 ReAct / Tool Use / Function Calling 相关文献。
- BM25 检索算法：可引用信息检索教材或 BM25 原始文献。
- MCP（Model Context Protocol）：可引用官方文档（如适用）。
- 软件工程/系统设计：可引用教材。
- 项目仓库内部文档可作为附录或自引（`docs/01_MVP.md`、`docs/02_SPEC.md`、`docs/04_API.md` 等）。

> ⚠️ 引用必须真实存在且与正文对应；禁止编造论文、教材或链接。

---

## 7.2 附录（可选）

### 附录 A 接口一览表

【表格：可直接复制 `docs/04_API.md` 第 6 节接口总览】

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| POST | `/api/cases` | 创建案件 |
| POST | `/api/cases/{case_id}/debate` | 启动 Agent 分析 |
| ... | ... | ... |

### 附录 B 启动与测试命令

```bash
# 一键启动
start_all.bat

# 后端
uvicorn backend.main:app --reload

# 前端
cd frontend && npm run dev

# RAG（按实际入口）
uvicorn rag.retriever:app --port 8001

# 测试
pytest
```

### 附录 C 演示案例数据

【表格：购物案例与时间案例的输入、关键字段、预期裁决】

| 案例 | 用户输入 | 关键字段 | 预期/实际裁决 |
|---|---|---|---|
| 购物-降噪耳机 | 想买 1299 元降噪耳机，学习需要安静 | 预算剩余、已有普通耳机 | 【待填写】 |
| 时间-社团活动 | 是否参加占用周末两天的社团活动 | 当前任务、活动收益 | 【待填写；按实际完成度】 |

### 附录 D 团队成员分工表

【表格：成员、模块、主要贡献】

| 成员 | 模块 | 主要贡献 | 对应报告章节 |
|---|---|---|---|
| A | 前端 | 【待填写】 | 2、3.4、4.2、5.3 |
| B | 后端 | 【待填写】 | 3.1、4.1、4.2 |
| C | Agent | 【待填写】 | 1、3.3、4.2 |
| D | RAG | 【待填写】 | 3.1、3.3、4.2、5 |
| E | 工具/工程化 | 【待填写】 | 3.3、4.2、5 |

<!-- TODO: 提交 Word 前删除模板中的“参考目录（提交时请删除该内容）”等说明。 -->

---
