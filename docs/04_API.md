# DecisionJury API 契约文档 v0.3

> 文档核对基线：`dev@53d70bc`。v0.3 是文档同步编号，不改变 URL 或运行时代码。本次仅交付 `shopping`；`time` 枚举、工具和数据兼容保留，不承诺时间案件主流程。以下示例为契约说明，不是本轮真实 API 验收记录。

## 1. 维护与当前限制

B 维护 HTTP/存储，C 维护 Agent 和 adapter，D 维护检索，E 维护工具，A 校对页面消费字段。文档与代码不一致时先记录差异，不把期望行为伪装成现状。

- B 已在 PR #89 补齐 `/debate` 提醒保存所需的 `Reminder` 导入，路由回归通过；页面闭环与重复保存等仍需验收。
- `PATCH /cases/{case_id}` 仍按七项字段计算状态，与创建/消息使用的 C 最低三项条件不一致。以下分别说明，不声称本轮已统一代码。
- 注册登录存在，但无 JWT/统一会话鉴权。部分接口比较 `user_id`，另一些没有所属用户校验，不构成生产级权限保护。
- 不因接口/工具返回 HTTP 200 就认定业务、模型或数据库保存成功。

## 2. 通用约定

### 2.1 路径与服务

B 业务接口前缀为 `/api`，注册登录为 `/auth`。RAG 的 `/api/rag/search` 在独立 D 服务（本地默认8001），不是默认后端8000的同名路由。

### 2.2 命名与时间

JSON字段和枚举使用 `snake_case`。时间用ISO 8601字符串；C/工具常含时区，B数据库返回可能不带时区，消费方需按项目时区约定处理，不假设每条都有偏移量。

### 2.3 HTTP方法

GET查询，POST创建或触发，PATCH局部修改，DELETE删除/软删除。案件、历史和观察清单已经有DELETE接口，不再是“暂不使用”。

### 2.4 成功响应

```json
{"success": true, "data": {}, "message": ""}
```

### 2.5 失败响应

```json
{"success": false, "data": null, "message": "CASE_NOT_FOUND"}
```

`data` 不保证为null：缺失字段/风险拒绝可携带说明。工具HTTP异常可能是外层success=true、内层status=failed，见§11。

### 2.6 身份前提

创建案件、历史和提醒前，`user_id` 必须存在于users表，否则可触发外键错误。登录返回用户信息而非token；客户端不能凭此宣称服务端已验证后续请求身份。

## 3. 枚举

| 名称 | 值与解释 |
|---|---|
| case_type | 本轮为shopping；time仅兼容/延期 |
| case_status | collecting、ready_for_debate、debating、completed、rejected、archived |
| shopping final_decision | buy购买、delay暂缓、reject不建议购买、alternative考虑替代 |
| time final_decision | accept/partial_accept/delay/reject为历史预留，不承诺当前主流程产出 |
| agent | input_parser、pro_agent、con_agent、judge_agent |
| tool_name | cost_analyzer、decision_score、cooling_reminder |
| risk_level | low、medium、high；工具不适用时可为null |
| history result | worth、regret、neutral（新增历史请求由Literal校验） |
| reminder表状态 | waiting、reviewed、cancelled |
| 提醒工具metrics.status | scheduled，与表状态不同 |

`final_decision=reject` 是建议不买，不等于 `case_status=rejected` 的拒绝处理。`archived` 枚举存在，但不是每次复盘自动归档。

## 4. 状态与字段合并

创建/消息使用 C parser，C最低字段 `product_name / price / monthly_budget_left` 齐全且无冲突即可ready；增强字段仍可列在missing_fields中。B高风险路径可以覆盖C状态为rejected。创建已读取is_complete；消息在非高风险分支使用 `is_complete or not missing_fields` 判定ready，而非直接照搬C的case_status。后一兼容分支未单独检查conflicts，不能描述为B已完整实现C的所有状态约束。

```text
collecting → ready_for_debate → debating → completed
collecting / ready_for_debate → rejected（B风险判断）
```

`POST /debate` 先比较user_id，再检查状态；非ready状态可能统一返回MISSING_FIELDS，不可据错误码假设每次都缺购物字段。成功后保存结果；失败回滚、重复请求和状态恢复需按实际路由验证。

`PATCH /cases/{case_id}` 的本地七字段判断尚未采用上述最低规则，详见§8.3。

## 5. 公共数据结构

### 5.1 Case

详情/更新响应直接在data下返回：case_id、user_id、case_type、title、description、**case_status**、collected_fields、missing_fields、final_decision、report_id、created_at、updated_at。

案件列表项仅包含 `case_id / title / case_type / status / description / updated_at / message_count / has_report`，不是完整详情。列表使用 **status** 而非case_status，两种返回不能直接混用。数据库内部status不意味着HTTP详情也使用这个名字。

### 5.2 Message

最新GET messages的item形状：

```json
{
  "id": "msg_001",
  "session_id": "case_001",
  "role": "user",
  "type": "text",
  "content": "价格大概是2500元。",
  "created_at": "2026-07-01T10:03:00"
}
```

当前路由不是message_id/case_id/message_type命名，前端需要显式适配。role通常为user/assistant；存储模型也允许其他角色字符串。

### 5.3 AgentStep

| 字段 | 类型 | 说明 |
|---|---|---|
| agent | string | 四个Agent之一 |
| status | string | completed / failed |
| summary | string | 摘要 |
| confidence | number | 0～1启发式值，不是校准概率 |
| arguments | string[] | 论点或判决说明 |
| used_rag_ids | string[] | 关联证据ID |
| used_tool_names | string[] | 关联工具名 |
| error | string/null | 错误 |

### 5.4 RagEvidence

字段为 `id / title / content / score / source / case_type / tags / created_at`。前六项分别为字符串（score为number），tags为字符串数组，created_at可为null。score为BM25相关性分数，不要求0～1；证据内容是content，不是旧SPEC中的text。

### 5.5 ToolResult

```json
{
  "tool_name": "cost_analyzer",
  "status": "success",
  "summary": "该商品占剩余预算约 65%，风险等级为 high。",
  "risk_level": "high",
  "metrics": {"budget_ratio": 0.65, "budget_left_after_purchase": 701},
  "error": null
}
```

所有字段均为稳定结构；status为success/failed，risk_level及error可为null，metrics为对象。成功工具数据不等于数据库写入成功。

### 5.6 DecisionReport

| 字段 | 类型 | 说明 |
|---|---|---|
| report_id / case_id / case_type | string | 报告与案件标识，当前shopping |
| final_decision | string | 本地规则唯一决定 |
| confidence | number | 本地置信度，不采用法官LLM返回值覆盖 |
| summary / case_summary | string | 判决说明与案件摘要 |
| pro_points / con_points | string[] | 双方论点 |
| rag_evidence | RagEvidence[] | 证据 |
| tool_results | ToolResult[] | 工具结果，包括失败结果 |
| next_actions | string[] | 本地后续动作 |
| created_at | string | 生成时间 |
| debate_events | DebateEvent[] | 默认空列表；当前完整庭审4条 |

### 5.7 TraceItem

C内部包含 `trace_id / step / type / name / input_summary / output_summary / duration_ms / status / error`。type为agent/rag_search/tool_call，step从1开始；error可为null。

B另行生成数据库trace ID，并在GET trace中增加created_at。不要用C内存trace ID等同数据库ID。正常调用包含decision_score，cooling_reminder条件触发，通常7或8条，不固定七条。

### 5.8 ParserResult（C 内部调用契约）

定义位置：`backend/app/schemas/decision.py`。调用入口为
`parse_input(raw_input, existing_collected_fields=None)`，返回 dataclass；
`to_dict()` 可将其序列化。以下字段不是新增 HTTP 请求参数。

| 字段 | 类型 | 说明 |
|---|---|---|
| case_type | string/null | 识别的案件类型，当前购物解析为 `shopping` |
| is_supported | boolean | 是否在 parser 支持范围内 |
| is_high_risk | boolean | 高风险主题标记；B 路由另有拦截逻辑 |
| reject_reason | string/null | 拒绝原因或风险标记原因 |
| extracted_fields | object | 本轮提取的购物字段，不等于累计字段 |
| merged_fields | object | 合并历史、本轮提取与纠正后的累计字段，供 B 保存 |
| missing_fields | string[] | 七个购物字段中仍缺失的项目，包括非最低必需项 |
| next_question | string/null | 追问候选文案；已就绪时应以 `case_status` 为准 |
| case_status | string | `collecting`、`ready_for_debate` 或 `rejected` |
| agent_step | AgentStep | 本次解析执行记录；解析置信度在此结构内 |

以下扩展字段均有默认值，旧调用方无需增加构造参数：

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| correction_fields | object | `{}` | 本轮明确纠正，合并时优先于同名提取值与历史值 |
| field_meta | object | `{}` | 字段状态与来源的可选说明，按购物字段名索引 |
| conflicts | object[] | `[]` | 尚未解决的歧义；当前本地规则记录 `amount_ambiguity` 及金额候选 |
| next_question_key | string/null | `null` | 追问关联的购物字段名，或金额澄清用的 `price_or_budget` |
| is_complete | boolean | `false` | 在支持的购物分支中，最低字段齐全且无冲突；不代表七项全部齐全 |
| termination_reason | string/null | `null` | `complete_minimum_fields`、`missing_required_fields`、`uncertain_required_fields`；默认/不支持分支可为 `null` |
| parser_used | string/null | `null` | `local` 为本地解析，`deepseek` 为模型解析，`local_fallback` 为模型失败后回退；默认/不支持分支可为 `null` |

`field_meta` 单项可包含 `status`（`confirmed` / `uncertain` / `missing`）、
`confidence`、`provenance`、`value`、`raw_text`、`approximate`、`unit`、`candidates`；
商品替换记录还可包含 `action`、`old_value`、`new_value`。这些子项并非每次齐全，
也不是跨轮持久化状态；不应以模型自报置信度单独决定是否进入分析。

完成条件与合并规则：

- 七项字段为 `product_name / price / purpose / monthly_budget_left / owned_alternatives / expected_usage_frequency / trigger_reason`。
- 最低必需项仅为 `product_name / price / monthly_budget_left`。`is_complete` 与 `case_status` 由 C 计算，不直接采用模型返回的同名值。
- 当前实现保留本轮未提及的历史字段，同名非空本轮字段覆盖历史值，`correction_fields` 最后覆盖。不要将其误写成“普通提取永远不会覆盖历史值”。
- 价格与预算按各自语义提取；邻近分句中的预算关键词不应使明确价格消失。
- 当三个最低字段齐全而用途等信息缺失时，`case_status=ready_for_debate` 与非空 `missing_fields` 可以同时成立。当前本地分支仍可能返回选填项追问候选，调用方不应因此重新阻塞分析。
- `termination_reason` 是本轮收集条件的说明，不表示已实现最大轮数或无进展熔断。

HTTP 暴露范围（本次保持不变）：

- `POST /api/cases` 选择返回 `case_status / collected_fields / missing_fields / next_question` 等字段；`collected_fields` 来自 C 的 `merged_fields`。
- `POST /api/cases/{case_id}/messages` 保存 `merged_fields`、缺失字段和状态，并以 `reply` 返回回复；非高风险分支使用 `is_complete or not missing_fields` 判断就绪。七个扩展字段未全部按原名透传。
- B 创建案件时，在值非空时把 conflicts / next_question_key / termination_reason / parser_used 分别存为 collected_fields 中的 `_conflicts / _current_question_key / _termination_reason / _parser_used`。消息路径只写 `_conflicts / _current_question_key / _parser_used`，不更新 `_termination_reason`。这些内部键可随 collected_fields 响应暴露，不是新增顶层响应字段。
- `field_meta` 没有整体持久化；已有下划线键的清理和跨轮刷新仍需验证，不能保证记录永远对应最新一轮。`DebateResult`、`DecisionReport` 不因此新增 parser 元数据。前端要展示歧义时应与 B 明确内部键的消费契约。

### 5.9 DebateEvent

| 字段 | 类型 | 说明 |
|---|---|---|
| event_id | string | 如event_001，不是数据库消息ID |
| order | integer | 从1递增，按此排序 |
| speaker | string | clerk / pro_agent / con_agent / judge_agent |
| phase | string | case_summary / opening_statement / closing_argument / verdict |
| content | string | 可展示的发言文本 |
| evidence | string[] | 关联RAG ID或工具名，默认[] |
| status | string | completed / failed，默认completed |

完整案件四条顺序：clerk/case_summary、pro_agent/opening_statement、con_agent/closing_argument、judge_agent/verdict。正反方独立陈述，无互相反驳。旧报告缺事件时调用方兼容[]，不伪造历史发言。

### 5.10 DebateResult（C内部结果）

`success / message / case_id / case_status / steps / rag_evidence / tool_results / report / trace / reason / debate_events`。

report在未完成时可为null，reason可为null，debate_events默认[]。C的顶层事件与report.debate_events一致。B持久化完整结果，但HTTP响应按§9、§12选择字段，不整体透传这个结构。

## 6. 接口总览

| 方法 | 路径 | 责任 |
|---|---|---|
| GET | /api/health | B |
| POST | /auth/register | B |
| POST | /auth/login | B |
| POST / GET | /api/cases | B |
| GET / PATCH / DELETE | /api/cases/{case_id} | B |
| POST / GET | /api/cases/{case_id}/messages | B/C |
| POST | /api/cases/{case_id}/debate | B/C |
| GET | /api/cases/{case_id}/report | B/C |
| GET | /api/cases/{case_id}/trace | B/C |
| POST | /api/cases/{case_id}/feedback | B |
| POST / GET | /api/history | B/D |
| DELETE | /api/history/{history_id} | B |
| PATCH | /api/history/{history_id}/restore | B |
| GET | /api/watchlist | B |
| DELETE | /api/watchlist/{reminder_id} | B |
| POST | /api/tools/cost-analyzer | E/B |
| POST | /api/tools/cooling-reminder | E/B |
| POST | /api/tools/decision-score | E/B |
| POST | /api/rag/search（独立RAG服务） | D |

没有恢复旧 `/api/chat`，没有新增SSE/WebSocket路由。

## 7. 健康检查

`GET /api/health`：

```json
{"success": true, "data": {"status": "ok", "version": "1.0.0"}, "message": ""}
```

只验证进程/API，不验证模型、检索命中或提醒存储。

## 8. 案件与身份接口

### 8.1 创建案件

`POST /api/cases`，以下四个字符串字段必填：

```json
{
  "user_id": "demo_user",
  "case_type": "shopping",
  "title": "是否购买降噪耳机",
  "description": "我想买一副1299元的降噪耳机，最近学习需要安静，预计每天使用，这次是刚需。"
}
```

data包含case_id、case_status、collected_fields、missing_fields、next_question、is_high_risk、reject_reason；collected_fields是累计字段，不只是description。next_question及模型提取文案不是固定值。空description可进入收集；不要从title必然推断已经得到product_name。

请求模型的case_type为str，不等于任意类型有主流程。当前用户操作只提交shopping。

### 8.2 查询案件详情

`GET /api/cases/{case_id}`：data直接是§5.1详情，无data.case包装。不存在返回CASE_NOT_FOUND。当前没有该路由所属用户参数校验，不把它视为已鉴权。

### 8.3 更新案件字段

`PATCH /api/cases/{case_id}`：user_id、title、description、collected_fields均可选。collected_fields按key更新，不是整对象替换；非空本轮字段可以覆盖旧值。

```json
{"title": "更新后的标题", "collected_fields": {"monthly_budget_left": 3000}}
```

data与详情一致，message为case updated。当前实现仍检查七个购物字段来切换状态，与parser最低三项策略不同；普通对话补充应走/messages，不能声称两条路径已完全等价。

### 8.4 多轮补充信息

`POST /api/cases/{case_id}/messages`：

```json
{"user_id": "demo_user", "message": "本月预算还剩3000元，已有普通耳机。"}
```

data包含reply、case_status、collected_fields、missing_fields、is_high_risk、reject_reason。检查price仍为1299、budget为3000；reply可能是模型或本地文本，不能逐字断言。保存C的merged_fields，不要求extracted_fields包含全部旧字段。

### 8.5 用户注册

`POST /auth/register`：user_id/name/password为必填字符串。成功data为user_id/name，message为“注册成功”；重复为success=false、data=null、message“用户已存在”。只在隔离环境使用测试账号。

### 8.6 用户登录

`POST /auth/login`：user_id/password必填；成功data为user_id/name，message“登录成功”。失败为“用户不存在”或“密码错误”。没有返回Bearer token/JWT，也没有统一cookie会话。

### 8.7 分页消息

`GET /api/cases/{case_id}/messages?user_id=demo_user&page=1&page_size=20`。

user_id必填；page≥1，page_size为1～100、默认20；按created_at升序。data为items/total/page/page_size，item见§5.2。无案件为CASE_NOT_FOUND，不匹配用户为FORBIDDEN。

### 8.8 案件列表与删除

`GET /api/cases?user_id=demo_user&page=1&page_size=10`：user_id必填，page_size最大100，按updated_at倒序；data为items/total/page/page_size，列表项见§5.1。

`DELETE /api/cases/{case_id}?user_id=demo_user`：比较所属用户，成功data为deleted=true。删除案件并级联消息/轨迹/提醒，关联历史软删除。当前历史查询过滤软删除记录，不能承诺删除后RAG仍会通过该接口得到记录。

## 9. Agent分析接口

### 9.1 启动多Agent分析

`POST /api/cases/{case_id}/debate`：

```json
{"user_id": "demo_user"}
```

| data字段 | 类型 | 说明 |
|---|---|---|
| case_id | string | 案件ID |
| case_status | string | 成功为completed |
| steps | AgentStep[] | parser、正方、反方、法官 |
| rag_evidence | RagEvidence[] | 本次证据 |
| tool_results | ToolResult[] | 成本、评分、条件提醒结果 |
| report | DecisionReport | 判决书 |
| debate_events | DebateEvent[] | 四条庭审事件 |

顶层证据/工具与report对应列表保持一致。C内部trace不在此HTTP响应中返回，请调用§12.2。一次性JSON返回，不是实时token/事件流。失败时使用success/message及data中的说明，不能无条件访问report。

PR #89 已修复 Reminder 导入，成功路径路由测试通过；该表仍不是实际部署或完整页面闭环的验收证明。

### 9.2 高风险拒绝

当B已将案件标记为rejected，/debate拒绝并返回：

```json
{
  "success": false,
  "data": {
    "case_status": "rejected",
    "is_high_risk": true,
    "reject_reason": "该决策超出系统支持范围。"
  },
  "message": "HIGH_RISK_DECISION"
}
```

原因字符串可变化。C返回HIGH_RISK_DECISION时B另有兼容分支，data可能为null；不要将C风险元数据与所有HTTP失败结构混为一谈。

### 9.3 缺失信息与用户校验

```json
{
  "success": false,
  "data": {
    "case_status": "collecting",
    "missing_fields": ["monthly_budget_left"],
    "next_question": "请补充本月剩余预算。"
  },
  "message": "MISSING_FIELDS"
}
```

实际missing_fields可含增强字段，问题文本可变化。请求缺user_id由Pydantic返回422；user_id与案件不符返回业务FORBIDDEN。非ready状态同样可能返回MISSING_FIELDS，检查data.case_status。

## 10. RAG接口

### 10.1 RAG检索

D服务的 `POST /api/rag/search`：

```json
{"user_id": "demo_user", "case_id": "case_001", "case_type": "shopping", "query": "降噪耳机 学习", "top_k": 3}
```

user_id/case_id/case_type/query必填，top_k默认3。成功data为results数组，每项为§5.4；无命中results=[]。BM25不负责最终建议。C通过RAG_SEARCH_URL访问；RAG通过BACKEND_HISTORY_URL尝试加载当前用户历史。

time检索仍是组件兼容能力，不作为本轮完整时间案件服务。不要将种子、实时用户历史和外部知识库来源混称为真实用户证据。

## 11. MCP工具接口

当前有两个入口：C通过Python `call_tool(name, arguments)` 调用；下列HTTP路由独立存在。二者不经过同一路由，提醒持久化也不相同。尚不宣称标准MCP Server协议传输已实现。

HTTP工具异常可能返回success=true且data.status=failed；调用方必须同时检查两层。参数校验失败也可能返回success=false或422。C adapter中的失败ToolResult保证主流程可降级，不等于HTTP调用必然成功。

### 11.1 成本计算工具

`POST /api/tools/cost-analyzer`：

```json
{"case_type": "shopping", "price": 1299, "monthly_budget_left": 2000}
```

case_type必填；case_id可选。购物必需price/monthly_budget_left且非负；预算0是合法边界，实现以占比1.0处理。结果data为§5.5，1299/2000约0.65、high、余额701。阈值按未舍入占比计算：≤0.2 low、≤0.6 medium、其余high。

历史兼容的time分支要求hours_required/free_hours_this_week/urgent_tasks，仍可组件调用，但不代表本轮时间主流程可用。

### 11.2 冷静期提醒工具

`POST /api/tools/cooling-reminder`：

```json
{
  "user_id": "demo_user",
  "case_id": "case_001",
  "title": "降噪耳机冷静期复盘",
  "cooling_days": 3,
  "reason": "预算占比较高。",
  "watch_items": ["是否仍然需要", "是否有替代品"]
}
```

user_id/case_id/title必填；cooling_days默认3、reason默认空字符串、watch_items默认[]。HTTP路径成功写入Reminder表后返回ToolResult，metrics含reminder_id/cooling_days/due_at/watch_items。业务或存储失败可能外层success=true、内层status=failed，error含REMINDER_CREATE_FAILED。

#### C编排返回数据与B落库

C adapter在成功ToolResult.metrics中补充实际title/reason，保留reminder_id/due_at/cooling_days/status/watch_items；失败结果不补。它们随tool_results及report.tool_results返回。这不表示E原始call_tool或独立HTTP结果已经新增相同字段。

B的/debate已有保存分支：读取这些metrics，用案件user/case ID，保存为表内waiting。PR #89已补齐Reminder导入；日期解析、外键、事务、幂等和页面回放仍需专项验收，不能将“工具成功”或“代码已合入”当作所有存储边界已验收。

### 11.3 决策评分工具

`POST /api/tools/decision-score`：

```json
{"case_type": "shopping", "cost_risk_level": "high", "history_risk": 0.7, "usage_value": 0.6, "impulse_trigger": true}
```

只有case_type必填；默认cost_risk_level=medium、history_risk=0.5、usage_value=0.5、impulse_trigger=false。两个数值范围0～1，触发标记为boolean。time只作组件兼容。

```json
{
  "success": true,
  "data": {
    "tool_name": "decision_score",
    "status": "success",
    "summary": "综合评分偏低，建议放弃或寻找替代方案。",
    "risk_level": "high",
    "metrics": {
      "score": 18,
      "risk_level": "high",
      "dimensions": {"cost": -20, "history": -6, "usage_value": 4, "impulse": -10}
    },
    "error": null
  },
  "message": ""
}
```

50-20-6+4-10=18；得分≥70为low、≥45为medium、更低为high。纯规则，不是LLM或概率。C在正反方之前调用，作为上下文参考；当前法官_decide不直接以该分数决定结论。

## 12. 判决书与轨迹

### 12.1 查询判决书

`GET /api/cases/{case_id}/report` 返回 **data直接平铺报告字段**，并合并data.debate_events；不是data.report。这是与POST debate的返回层级区别。

B读取case.debate_result.report与顶层debate_events，无案件/无报告分别返回CASE_NOT_FOUND/REPORT_NOT_FOUND。非空debate_result若不是对象，返回REPORT_DATA_CORRUPTED；非对象report按空报告处理，非数组debate_events按[]处理。历史结果没有事件时返回[]；当前C完整报告应含四条。该接口没有重新调用模型。

### 12.2 查询执行轨迹

`GET /api/cases/{case_id}/trace` 返回data.case_id及data.trace，按step升序；item为§5.7加created_at。无案件返回CASE_NOT_FOUND；不要把技术轨迹与庭审发言混用。

## 13. 历史记录

### 13.1 查询历史

`GET /api/history?user_id=demo_user&page=1&page_size=10`。

user_id必填；page≥1，page_size实际允许1～1000（默认10）；可选case_type/result筛选。只返回is_deleted=0，按created_at倒序。data为items/total/page/page_size；item字段为history_id/user_id/case_type/title/summary/result/tags/case_id/report_id/created_at。

### 13.2 添加历史

`POST /api/history`：

```json
{"user_id": "demo_user", "case_type": "shopping", "summary": "购买前评估了耳机预算。", "result": "neutral", "tags": ["electronics"]}
```

user_id/case_type/summary/result必填，result只允许worth/regret/neutral。可选title/price/usage_frequency/context/pros/cons/final_decision/case_id/report_id/tags。成功data返回保存的完整历史信息（含history_id），message=history created。

### 13.3 删除与恢复

`DELETE /api/history/{history_id}?user_id=demo_user`：比较所属用户，标记is_deleted=1，data.deleted=true。

`PATCH /api/history/{history_id}/restore?user_id=demo_user`：比较所属用户，恢复is_deleted=0，data.restored=true。失败消息包括HISTORY_NOT_FOUND、FORBIDDEN、HISTORY_ALREADY_DELETED、HISTORY_NOT_DELETED。

软删除保留数据库记录，但当前历史HTTP查询会过滤；RAG经该HTTP入口拉取也受过滤影响，不宣称删除后依旧能检索。

## 14. 观察清单与复盘

### 14.1 查询观察清单

`GET /api/watchlist?user_id=demo_user`，user_id必填。data.items只含该用户waiting提醒，按due_at升序；字段为reminder_id/case_id/title/reason/due_at/status/created_at。

提醒页面为空可能因为尚无符合条件的记录、已复盘/取消或保存失败，不应一概归因于C工具未被调用。

### 14.2 删除观察清单项

`DELETE /api/watchlist/{reminder_id}?user_id=demo_user` 将状态设为cancelled；data为deleted=true、reminder_id。PR #89起user_id必填，缺少返回422；所属用户不符返回FORBIDDEN，无记录为REMINDER_NOT_FOUND。前端需携带该参数；这种ID比较仍不等于可信的登录会话鉴权。

### 14.3 提交决策复盘

`POST /api/cases/{case_id}/feedback`：

```json
{"user_id": "demo_user", "actual_action": "not_bought", "satisfaction": 5, "review": "冷静后选择先用已有耳机。"}
```

user_id/actual_action/satisfaction必填，review可选。actual_action为字符串，界面约定bought/not_bought/delayed/other；satisfaction建议1～5，但当前Pydantic仅声明int，没有范围约束，不将建议误写为服务端已校验。

要求案件completed；按满意度≥4/≤2/其他映射worth/regret/neutral。同案未软删除的复盘可更新，关联waiting提醒改为reviewed。成功data为saved_to_history=true、history_id，message为空；不是自动将案件置为archived。

## 15. 错误码与失败层次

| message / error | 层次与实际含义 |
|---|---|
| CASE_NOT_FOUND / REPORT_NOT_FOUND / REPORT_DATA_CORRUPTED / CASE_NOT_COMPLETED | B业务失败，通常HTTP200、success=false |
| FORBIDDEN | 部分B路由user_id比较失败，通常HTTP200，不是统一鉴权中间件 |
| MISSING_FIELDS / HIGH_RISK_DECISION | 业务失败，可携带data说明 |
| UNSUPPORTED_CASE_TYPE | C adapter/部分工具不支持类型；不表示创建接口已严格枚举校验 |
| HISTORY_NOT_FOUND / HISTORY_ALREADY_DELETED / HISTORY_NOT_DELETED | 历史业务失败 |
| REMINDER_NOT_FOUND | 观察清单业务失败 |
| VALIDATION_ERROR | Pydantic请求校验，HTTP422 |
| DATABASE_ERROR / INTERNAL_SERVER_ERROR | 全局异常处理，HTTP500 |
| INTEGRITY_ERROR | 数据库完整性错误，HTTP400 |
| INVALID_JSON_FORMAT | JSON解码异常处理；具体入口也可能归入422验证错误 |
| TOOL_ERROR / REMINDER_CREATE_FAILED | 可在ToolResult.error内，外层success不一定false |
| RAG/LLM调用失败 | C按路径降级/记录trace，不保证转换成同名HTTP500错误 |

## 16. 联调与验收

- A区分POST debate的data.report与GET report的平铺data；对空事件、旧报告、消息字段差异做兼容。
- B保存C完整结果和trace，Reminder导入已修复；继续验证元数据更新/清理、持久化和观察清单删除参数，后续统一PATCH与parser完成条件。
- C保证最低字段、合并、四庭审事件和本地规则所有权；不为本次time延期修改协议。
- D返回真实RagEvidence，E返回ToolResult；HTTP与本地调用的额外字段/副作用分开说明。
- 契约变化同步测试。Swagger的ApiResponse.data为宽类型，OpenAPI存在不等于所有嵌套字段和业务路径已获验证。
- 最新验收按 [测试计划](05_TestPlan.md) 记录；本次只同步文档，不修复业务代码。
