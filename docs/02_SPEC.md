# DecisionJury SPEC 项目规格说明书

> 实现基线：`dev@53d70bc`。本次只交付购物决策；`time` 为延期范围，保留的工具、枚举、数据不代表时间主流程可用。本文描述已检查的代码机制，不替代 [测试计划](05_TestPlan.md) 中的运行验收。

## 1. 产品定位与边界

面向日常购物，帮助用户整理用途、价格、预算和替代品，看到正反两面理由、相关历史和计算依据。输出是辅助建议，不是消费效果保证或法律意义上的判决。

不扩展医疗、法律、投资、借贷、辞职、亲密关系等高风险场景。C parser 保留 `is_high_risk` 标记，C 主流程本身不以该标记直接停止；B 的创建、消息和辩论路由仍有拒绝路径。不得将 C 的行为描述成整个项目已取消高风险边界。该分类采用关键词/模型判断，不保证覆盖或准确识别所有风险语境。

## 2. 架构与职责

```text
浏览器（React / TypeScript / Vite）
  → B FastAPI（/api 业务接口、/auth 注册登录）
    → SQLAlchemy / SQLite
    → C adapter → Python 顺序编排
      → DeepSeek HTTPS API
      → D RAG HTTP 服务 → BM25 → 种子 + B 历史接口
      → C 工具 adapter → E call_tool → 规则工具与日志
```

| 层 | 实现与职责 | 不承担的职责 |
|---|---|---|
| A 前端 | 案件、消息、判决、庭审回放、历史和观察清单展示 | 不直接持有模型 Key 或调用模型 |
| B 后端 | API、用户记录、案件状态、JSON/trace/历史/提醒持久化 | 不替代 C 的字段解析和判决规则 |
| C Agent | parser、正反方、法官、LLM 协议、RAG/MCP adapter | 不直接向数据库写提醒 |
| D RAG | jieba + BM25，返回可引用记录 | 不生成最终建议、不编造个人历史 |
| E 工具 | 成本、评分、提醒数据、调用日志、工程脚本 | 不决定完整案件状态或最终结论 |

基础框架为 Python + uv/pytest、FastAPI、SQLAlchemy、SQLite，前端为 React 18 + TypeScript + Vite。Python 版本/依赖以根目录 `pyproject.toml` 为准。没有使用 LangGraph/LangChain 编排，也没有 ChromaDB/FAISS 向量库；不能将原方案候选技术列成当前技术栈。

## 3. 端到端流程

1. 注册演示用户，再用其真实 `user_id` 创建购物案件，避免外键失败。
2. B 调用 `parse_input`，保存 C 的 `merged_fields`、缺失字段与案件状态；消息轮次同时保存用户和助手消息。
3. 三个最低字段齐全、无冲突且未被 B 拒绝后，允许调用 `POST /api/cases/{case_id}/debate`，请求体包含所属用户 ID。
4. B 将案件置为 `debating`，调用 `run_case_decision_flow`；C adapter 只接受 `shopping`。
5. C 重新解析累计输入，依序调用检索、工具和 Agent，形成报告、事件与 trace。
6. B 保存完整结果、trace 和成功提醒；PR #89 已补齐 `Reminder` 导入。路由测试通过不等于浏览器完整闭环已验收。
7. 前端通过报告/trace 接口读取结果。用户反馈写入历史，RAG 下次请求尝试拉取实时历史作为候选。

C 真实调用顺序：

```text
input_parser
  → rag_search
  → cost_analyzer
  → decision_score
  → pro_agent
  → con_agent
  → cooling_reminder（条件触发）
  → judge_agent
```

提醒在法官之前生成，不是法官生成 `delay` 后才调用。当前触发条件见 `backend/app/orchestrator/decision_flow.py` 的 `_should_create_reminder`：成本风险为 medium/high，或触发原因是促销、种草、情绪。实际 trace 通常为 7 或 8 步，不能固定写成七步。

## 4. 输入解析与状态

### 4.1 字段

| 字段 | 意义 | 最低必需 |
|---|---|---|
| product_name | 商品或服务名称 | 是 |
| price | 商品价格 | 是 |
| monthly_budget_left | 本月剩余预算 | 是 |
| purpose | 用途 | 否 |
| owned_alternatives | 已有替代品 | 否 |
| expected_usage_frequency | 预计频率 | 否 |
| trigger_reason | 购买触发原因 | 否 |

默认路径先构建本地解析结果，再尝试模型；无 Key 用本地规则，模型请求/校验失败时返回本地结果。支持的口语、中文金额和明确纠正都有规则及对应测试，但不保证理解任意表达。

### 4.2 合并与结束条件

- `extracted_fields` 是本轮提取，`merged_fields` 才是累计结果。
- 保留本轮未提及的历史值；同名非空本轮字段可覆盖旧值；`correction_fields` 最后覆盖。
- `MINIMUM_DECISION_FIELDS` 为商品名、价格、剩余预算；最低字段齐全且 `conflicts` 为空时，C 的购物结果可进入 `ready_for_debate`。
- `missing_fields` 仍列七项中未收集的增强字段，所以可以非空；`is_complete` 指最低条件满足，不是七项全齐。
- B 还执行自身风险/状态判断；UI 不应仅凭有缺失字段就重新阻塞分析。

`ParserResult` 还提供 `field_meta / conflicts / next_question_key / termination_reason / parser_used`。详情见 [API §5.8](04_API.md#58-parserresultc-内部调用契约)。B 已在 collected_fields 中保存部分下划线前缀元数据，并通过 is_complete 判断就绪；field_meta 未整体持久化，创建和消息路径的元数据更新范围也不同，不宣称完整字段置信度记忆或最大三轮退出机制。本地分支在最低字段满足时仍可能带增强字段追问，状态是能否开始分析的重要依据。

### 4.3 价格与预算回归示例

```text
想买降噪耳机，价格 1299 元，本月预算还剩 2000 元
```

本地价格 1299、预算 2000；金额上下文限制在标点分句内，防止后面的预算关键词吞掉价格。纠正“不是2500，是2200”应更新价格，而“预算不是3000，是2500”应更新预算。歧义金额不得被当作两个确定字段使用。

## 5. Agent 与 DeepSeek

| 角色 | 处理方式 |
|---|---|
| input_parser | 专用 `complete_parser_json` + 字段校验，本地重算合并、缺失与状态 |
| pro_agent | `complete_json("pro_agent", payload)`，输出支持购买的摘要与论点 |
| con_agent | `complete_json("con_agent", payload)`，独立分析风险，不接收正方陈述 |
| judge_agent | 本地 `_decide / _confidence`，再调用 `complete_json("judge_agent", payload)` 生成说明 |

通用模型协议是 `summary / arguments / confidence`，parser 使用独立结构与校验规则。`backend/app/prompts/` 保存角色提示词说明；当前请求没有读取这些 Markdown 文件，实际 system/user 提示词由 `backend/app/services/llm_client.py` 的 `_build_system_prompt / _build_user_prompt` 构造，并在同文件校验响应。仅修改提示词 Markdown 不会改变实际模型请求，运行行为以这些函数和 Agent 传入的 payload 为准。

默认模型 `deepseek-v4-flash`，地址 `https://api.deepseek.com/chat/completions`；使用 JSON 响应格式，默认超时 30 秒，`DEEPSEEK_TIMEOUT_SECONDS` 支持 1～120 秒，非法值回退默认。当前工厂读取 Key/timeout，不读取自定义 Base URL/model 环境变量；类构造参数可用于受控验证，不等于部署已支持任意网关切换。

无 Key 或远端失败时，正反方使用 mock；法官使用本地说明。有效 JSON 只证明结构符合要求，不能证明模型结论必然正确，也不能从 HTTP 200 推断没有发生 fallback。

### 5.1 法官规则

按当前 `_decide` 的优先顺序：

1. 成本工具成功且风险 high → `reject`。
2. 成本风险 medium、触发原因为促销/种草/情绪，或证据带 idle/regret/budget 标签 → `delay`。
3. 有非空且不是“无/没有”的替代品 → `alternative`。
4. 使用频率为每天/每日/经常/高频 → `buy`。
5. 其他 → `delay`。

LLM 接收规则结论、双方观点、RAG 和工具上下文，只生成说明，不能覆盖规则结果。评分工具会进入上下文，但当前 `_decide` 不直接使用 `decision_score` 的数值。法官置信度也是本地启发式，不是模型输出的置信度或统计校准概率。

## 6. 简化模拟法庭

| order | speaker | phase | 内容来源 |
|---|---|---|---|
| 1 | clerk | case_summary | 累计字段和当前证据/工具概览，本地构造 |
| 2 | pro_agent | opening_statement | 正方摘要和论点 |
| 3 | con_agent | closing_argument | 反方摘要和论点 |
| 4 | judge_agent | verdict | 规则最终建议和判决说明 |

`DebateResult.debate_events` 与 `DecisionReport.debate_events` 内容一致，新增字段默认空列表。事件还包含 `event_id / content / evidence / status`，evidence 关联证据 ID 和工具名。缺失信息/不支持类型不生成完整庭审。

本版只组织已有输出，非交叉质询、多轮辩论或实时推送。页面渐进播放是客户端展示，不代表后端流式生成。

## 7. RAG 实现

- D 的 `rag/retriever.py` 提供 `POST /api/rag/search`；C 经 HTTP adapter 调用，主流程 `top_k=3`。
- `rag/data_loader.py` 读取静态种子，尝试按用户请求 B 历史接口，再按 ID 合并；实时拉取失败则保留静态记录。
- jieba 搜索分词，BM25 排序，按标题去重，返回 `RagEvidence`：id、title、content、score、source、case_type、tags、created_at。
- `score` 是检索分数，不是 0～1 概率；无命中返回空数组。
- 检索服务故障与正常空结果分开记录：前者 trace failed，后者 completed。两者都允许后续分析，不允许生成伪造历史。
- `RAG_LIVE_RECORDS / BACKEND_HISTORY_URL / HISTORY_TIMEOUT` 控制实时历史；前端新复盘在后端成功保存、拉取成功并通过过滤后才可能被检索，不保证每次命中。
- 时间样例和组件检索保留，仅为历史兼容；向量与混合检索延期。

## 8. 工具实现

C 通过 `backend/app/services/mcp_adapter.py` 调用 E 的 `mcp_tools.mcp.call_tool(name, arguments)`，结果映射为 `ToolResult`。独立 `/api/tools/*` HTTP 接口存在，但 C 主流程不绕回这些 HTTP 路由；尚未实现标准 MCP Server 传输。

### 8.1 成本与评分

购物成本按原始预算占比判定：≤0.2 为 low，≤0.6 为 medium，更高为 high；预算为 0 时实现使用占比 1.0。1299/2000 ≈ 0.65 是 high，不是 medium；1299/3000 ≈ 0.43 为 medium。

同一个 `monthly_budget_left` 数值可能代表两种语义不同的钱：本月剩余可支配预算（流量），或用户为这次购物攒下的一次性资金（存量）。工具因此接受可选的 `budget_source`（`monthly_budget` 默认 / `savings`），并为存量使用另一套分级：≤0.5 low、≤1.0 medium、更高 high。C 在 parser 中按显式存量词标记来源，词表按词根收录（攒 / 存款 / 储蓄 / 积蓄 / 闲钱 / 私房钱 / 存了 / 存下 / 存起来）而不是逐个罗列固定搭配——真实测试出现过"我自己攒有1000块钱"因词表只有"攒了/攒下"而被漏识别的情况。存量词与金额之间的间隔不允许出现"买/购"或句读，避免"攒钱买个1000元的耳机"把商品价格吞成可用资金；金额在存量词之后的表达（"1000块是我自己攒的"）同样识别。标签与金额在同一次解析中同时写入；本轮没有金额表达时保留历史标签，缺失时按 `monthly_budget` 处理。只认显式存量表达，"不影响日常生活"这类不可核实的声明不作为降级依据。`savings` 只影响成本分级，不改变 §5.1 的法官规则：799/1000 由 high 降为 medium，判决相应从 reject 变为 delay；1200/1000 仍为 high。该字段不计入最低必需字段，也不改变七字段完成条件。

`decision_score` 用成本、历史风险、使用价值、冲动触发四维规则产生 0～100 分；不依赖 LLM。成本工具失败时 C 可以返回失败评分结果，不用默认分冒充真实计算。

### 8.2 提醒与数据库

E 生成提醒 ID、到期时间等数据；C 成功结果的 metrics 补充实际调用的 `title / reason`。工具状态 `scheduled` 与 B 表内 `waiting` 不是同一层的枚举。

独立工具 HTTP 路由与 B 的 `/debate` 均有落库逻辑；PR #89 已修复后者的 `Reminder` 导入。仍需验证外键、日期、事务、重复提交和观察清单页面读取。工具成功不等于落库成功，提醒数据不等于邮件/系统通知服务。

## 9. 存储与接口

SQLite 表包含 `users / cases / messages / histories / traces / reminders`。案件 `debate_result` JSON 保存 C 完整结果；trace 另存表供查询；反馈写入历史并更新相关待复盘提醒。

- `POST /api/cases/{case_id}/debate`：返回 data.steps、rag_evidence、tool_results、report、debate_events。
- `GET /api/cases/{case_id}/report`：报告字段直接平铺在 data，包含 data.debate_events；不同于 POST debate 的 data.report。
- `GET /api/cases/{case_id}/trace`：返回数据库轨迹；不要从 /debate HTTP 响应直接读取 trace。
- `GET /api/cases/{case_id}/messages`：已有分页、用户比较和按时间升序查询，响应项使用 id/session_id/type。
- 注册/登录是 `/auth` 前缀，不是 `/api/auth`。当前无 JWT/统一会话认证，不能将用户 ID 参数视为可靠鉴权。

完整字段、HTTP 错误及兼容行为以 [API](04_API.md) 为准。

## 10. 可靠性、部署与验收

开发环境结构不一致可能自动重建数据库；演示/部署保留数据时使用 `ENV=production` 并备份。SQLite 迁移只覆盖当前实现，不承诺任意模型变更自动安全升级。

Windows 使用根目录 `.venv` 和启动脚本，Linux screen 为开发服务器演示，Docker 使用 nginx 静态前端及独立后端/RAG 服务。已有配置不证明已对公网部署或达到生产安全要求。

本次只更新人读文档，不修改 Prompt、路由、模型、数据库或测试行为。运行验收覆盖购物信息收集、四事件、规则判决、模型兜底、RAG、三个工具和 B 持久化，见 [测试计划](05_TestPlan.md)。不再以时间流程作为本次完成条件。
