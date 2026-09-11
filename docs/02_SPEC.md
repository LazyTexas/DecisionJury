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
2. 成本风险 medium、触发原因为冲动型（促销/种草/他人推荐/情绪），或**相关**证据带 idle/regret/budget 标签 → `delay`。
3. 有非空且不是“无/没有”的替代品 → `alternative`。
4. 使用频率为每天/每日/经常/高频 → `buy`。
5. 其他 → `delay`。

LLM 接收规则结论、双方观点、RAG 和工具上下文，只生成说明，不能覆盖规则结果。评分工具会进入上下文，但当前 `_decide` 不直接使用 `decision_score` 的数值。法官置信度也是本地启发式，不是模型输出的置信度或统计校准概率。

#### 5.1.1 判决规则 v2（2026-09-10 修复）

旧版对自由文本做精确字符串比较，出现“同义不同判”：`每天`→buy 而 `每天使用`→delay；`没有`→无替代品而 `暂无/没有其他水果`→被当成有替代品；`促销`→delay 而 `朋友推荐/旧物损坏`→buy；4 元商品落兜底 delay；无关历史（围巾/投影仪）也能把结论打成 delay。现行规则：

1. **字段归一化**（`backend/app/agents/field_normalizer.py`，判决与 `decision_score` 共用）：
   - 频率 → 受控值 `daily / weekly_3plus / weekly_1_2 / monthly / occasional / unknown`（`每天使用`、`日常使用`、`一周五天` 均正确归类）；
   - 触发原因 → `need / promotion / recommendation / emotion / unknown`（`朋友推荐/社交影响/种草` 同属 recommendation）；
   - 替代品 → `{has, known, items, covers_core_need}`，`无/没有/暂无/没有其他X/无其他X` 统一判为“没有”；空值表示“未说明”而不是“没有”。
2. **硬约束（先短路）**：
   - `H1` 成本风险 high → `reject`；
   - `H2` 占比 ≤1% 且成本风险 low 且无相关风险证据 → `buy`（小额低风险消费不进冷静期）。
3. **决策表**（**按此顺序判定，先命中先返回**）：
   - `R1` 成本 medium / 冲动型触发 / 相关证据含风险信号 → `delay`；
   - `R2` 替代品明确 `covers_core_need=true` → `alternative`；
   - `R3` 高频使用且 `decision_score ≥ 45`（成本工具必须成功）→ `buy`；
   - `R4` 仅提到替代品、是否等效未知 → `alternative`；
   - `R5` 成本 low 且综合评分 ≥45（且未触发任何风险规则）→ `buy`；
   - `R6` 其他 → `delay`（成本工具失败时不放行，按保守口径处理）。
   - **优先级说明（2026-09-11 修正）**：`R2` 判定在 `R1`（medium/冲动/历史风险）**之前**——
     已有物品确实能覆盖核心需求时，"不需要重复买"比"预算有压力，先冷静"更强也更可行动
     （`delay` 的后续动作是"复盘真实需求"，而真相是旧物已经够用；此前 299 元电饭煲案出现
     "反方说替代品已覆盖、判定依据却只写预算压力"的自相矛盾）。
     **高风险档不受此优先级影响**：`H1` 的 reject 在此之前返回；`E6`（高额刚需）是 fall-through，
     会继续交给 `R3/R5` 决定放行，因此 `R2` 加了 `risk_level != "high"` 的边界——
     不让一个模型判断的布尔值（`covers_core_need` 实测存在波动）覆盖高风险档的既有行为。
     回归用例：`tests/test_judge_rules.py::test_covering_alternative_outranks_medium_cost_risk`
     与 `::test_high_risk_path_still_wins_over_covering_alternative`。
   - **不对称是刻意的**：只有**已确认能覆盖**的替代品（`R2`）优先于中等成本风险；
     **仅提到、能否替代未知**（`R4`）不优先——预算压力中等时仍先判 `delay`，由后续动作
     "比较已有替代品或低价替代方案能否满足核心用途"承担提醒职责
     （用例：`::test_unconfirmed_alternative_still_waits_for_budget_pressure`）。
4. **证据相关性门槛**：只有与本案相关（类目一致 + 商品名词面重合）的证据才能影响判决；无关证据仍展示，并在依据里标注“仅作参考、未计入判决”。
5. **可解释输出**：报告新增 `decision_basis`（命中规则 `rule` / 说明 `detail` / 影响 `effect`）与 `decision_strength`（结论强度，硬约束 0.9、R1/R2 0.8、R3 0.7、R4 0.65、R5 0.6、R6 0.5）。`confidence` 保留原含义，但页面文案改为“证据置信度”，与结论强度区分。
6. 回归用例见 `tests/test_judge_rules.py`（同义写法矩阵、低成本短路、无关证据、替代品语义、成本工具失败等）。

#### 5.1.2 收集阶段的对话策略（2026-09-10 新增）

收集阶段（创建案件 + 每轮消息）的回复**不再是单个字符串**，而是结构化的 `reply_plan`（实现：`backend/app/agents/reply_composer.py`，由 `input_parser._finalize` 生成，`routers/chat.py` 与创建案件路由透出）：

```
每轮回复 = 承接(ack) + 只问一个问题(question) + 快捷选项(chips) + 能否结束(can_stop/optional)
```

规则（全部为本地确定性逻辑，不依赖模型，便于测试与降级一致）：

1. **承接**：本轮新识别/纠正的字段回显成人话（`记下了：价格 30 元、预算还剩 5000 元。`）；没有新字段时不硬凑。
2. **只问一个**：`question` 最多一句，阻塞字段文案取自 `MISSING_FIELD_QUESTIONS`，已去掉“为了进入购物法庭分析”这类系统口吻（如 `这个大概多少钱？`、`大概多久会用一次？`）。
3. **核心齐了就邀请结束**：`can_stop=true` 时前端提示“可以直接出判决书”，`missing_fields` 里的剩余项在页面上标为“建议补充”，不阻塞分析。
4. **可选追问熔断**：`is_complete` 后的可选追问最多 2 轮（`_optional_asked` 计数），之后只给结束邀请。
5. **允许跳过**：用户回“不知道/不清楚/不太确定/跳过/随便”等（`is_skip_signal`）时，**增强字段**记为 `未说明`（`SKIPPED_VALUE`）并从 `missing_fields` 移除，回复带“行，这项先跳过。”；**核心字段**不允许跳过，改为“这项还是得有个大概的数，给个范围也行：…”。
6. **快捷选项**：`chips` 按当前问题给出（频率 → 每天/每周几次/偶尔；用途 → 工作学习/家用/娱乐/说不清 等），前端点击即以该文本发送。
7. **金额歧义**优先于普通追问：`question` 换成“哪个是商品价格，哪个是本月预算？”，不给 chips。
8. 回归用例见 `tests/test_reply_composer.py`；`reply_plan` 字段契约见 [API §8.4](04_API.md)。

#### 5.1.3 对话文案由模型写、护栏在本地（2026-09-10）

收集阶段的"说话方式"从纯本地模板升级为**模型撰写 + 本地护栏**，成本不变（仍是每轮 1 次调用）：

- `input_parser` 的提示词要求模型额外输出 `dialogue`：`ack`（承接，≤30 字）/ `insight`（可选的一句有价值回应）/ `question`（**只问一个**，可选补充加"（可选）"）/ `chips`（0~3 个快捷选项）/ `answer_to_user`（用户反问时先回答）/ `intent`（provide_info·correct·ask_back·chitchat·skip·stop）。
- 调用时把 `recent_turns`（最近 6 条）、`last_question`、`already_asked_fields` 一并发给模型，使其能承接上下文、不复读、处理指代。
- **本地护栏**（`reply_composer._apply_model_dialogue`）负责四件事：只保留第一个问句；与上一轮问题重复则丢弃并改用本地模板；命中系统口吻黑名单（"为了进入…""字段""请补充"等）即丢弃该段文案；用户改过信息时回显"xx已改成 …"。
- **降级不崩人设**：模型不可用时回落到本地模板（承接句本来就是本地生成），并在 `reply_plan` 里标 `degraded/degraded_reason/parser_used`，前端提示"这轮用的是本地规则"。
- **失败重试**：解析调用失败重试一次；结构校验改为"必需键齐全即通过"，未知顶层键忽略、未知字段只丢该字段（字段级降级），不再整轮作废。
- **自动开审**：仅当模型判定 `intent=stop` **且**用户原话命中停止词（直接分析/别问了/够了…）且核心信息已齐时，`reply_plan.stop_requested=true`，前端自动进入辩论。

#### 5.1.4 受控值契约（2026-09-10，契约优先）

为消除"同一语义两套实现"（模型写中文自由文本 + 本地正则再猜一次），解析层改为**模型直接输出受控值**，本地归一化退化为"校验 + 兜底"：

| 契约字段 | 取值 | 说明 |
|---|---|---|
| `frequency_canonical` | `daily / weekly_3plus / weekly_1_2 / monthly / occasional / unknown` | 频率不再用中文表达 |
| `trigger_canonical` | `need / promotion / recommendation / emotion / unknown` | 触发原因同上 |
| `price_basis` | `unit` / `total` | 声明给出的是单价还是总价 |
| `price_unit` / `quantity` | 单位 / 数量 | 成本占比不再靠猜 |
| `alternative_covers_need` | `true / false / null` | 已有物品能否覆盖核心需求 |

取用规则（`field_normalizer.resolve_frequency / resolve_trigger`，判决与评分共用唯一入口）：

1. **受控值优先**；不在白名单内视为"未给"，回落到文本归一（本地兜底路径仍可用）。
2. **冲突降级**：受控值与文本归一结果矛盾时（例如受控值 `daily`、原话"只是偶尔"）→ 取 `unknown` 并标记冲突，**不允许模型用错误受控值覆盖正确文本**。
3. **金额一致性**：只有入库价格恰好等于原话里的单价值时才标记 `price_is_unit`；若模型已换算成总价（`2元一寸 × 27寸 = 54`），则清除单价标记，避免成本工具再乘一次数量。
4. 展示字段（`expected_usage_frequency` / `trigger_reason`）保留用户原话，供回显与追溯；判决与评分只读受控值。

回归：`tests/test_golden_dialogues.py` 剧本 16（受控值优先 / 非法值回落 / 冲突降级）、剧本 17（总价不得被当单价再乘）。

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

`decision_score` 用成本、历史风险、使用价值、冲动触发四维规则产生 0～100 分；不依赖 LLM。成本工具失败时 C 可以返回失败评分结果，不用默认分冒充真实计算。

`usage_value` 由 C 的 adapter 取值：高频 0.9、已知用途或已知频率 0.65、**用途与频率都未知时给中性 0.5**（未填字段不再被当成“低价值”扣分），冲动触发与历史风险则改用归一化字段与相关证据统计。

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
