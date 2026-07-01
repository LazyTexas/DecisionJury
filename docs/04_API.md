# DecisionJury API 契约文档 v0.2

## 1. 文档目的

本文档用于统一前端、后端、Agent、RAG、MCP 工具之间的接口契约。A/B/C/D/E 开发时必须以本文档为准。

接口字段发生变化时，必须先更新本文档，再修改代码和测试。

接口维护规则：

- B 后端 API 与状态管理负责维护本文档。
- A 前端提出页面展示字段需求。
- C Agent 编排提出 AgentStep、DecisionReport、TraceItem、RAG/MCP 接入字段需求。
- D RAG 提出 RagEvidence 字段需求。
- E MCP 提出 ToolResult 字段需求。
- 跨模块接口变更必须在 PR 中说明影响范围。

## 2. 命名与通用约定

### 2.1 基础路径

```text
/api
```

### 2.2 接口命名规则

- 路径采用 REST 风格。
- 资源名使用英文小写复数，例如 `cases`、`messages`、`reports`。
- 动作作为子资源，例如 `debate`、`search`、`feedback`。
- JSON 字段统一使用 `snake_case`。
- 枚举值统一使用小写 `snake_case`。
- 时间统一使用 ISO 8601。

不使用以下风格：

```text
/api/createCase
/api/getReport
/api/startAgent
```

### 2.3 HTTP 方法规则

| 方法 | 用途 |
|---|---|
| GET | 查询资源 |
| POST | 创建资源或触发动作 |
| PATCH | 局部更新资源 |
| DELETE | 删除资源，MVP 暂不使用 |

### 2.4 通用成功响应

```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

### 2.5 通用错误响应

```json
{
  "success": false,
  "data": null,
  "message": "CASE_NOT_FOUND"
}
```

### 2.6 时间格式

```text
2026-07-04T20:00:00+08:00
```

## 3. 核心枚举

### 3.1 case_type

| 值 | 说明 |
|---|---|
| shopping | 购物决策 |
| time | 时间决策 |

### 3.2 case_status

| 值 | 说明 |
|---|---|
| collecting | 正在收集信息 |
| ready_for_debate | 信息完整，可以进入 Agent 分析 |
| debating | Agent 分析中 |
| completed | 已完成判决 |
| rejected | 高风险或不支持，拒绝处理 |
| archived | 已归档 |

### 3.3 shopping final_decision

| 值 | 说明 |
|---|---|
| buy | 建议购买 |
| delay | 建议暂缓 |
| reject | 建议不购买 |
| alternative | 建议寻找替代方案 |

### 3.4 time final_decision

| 值 | 说明 |
|---|---|
| accept | 建议接受 |
| partial_accept | 建议部分接受 |
| delay | 建议延后 |
| reject | 建议拒绝 |

### 3.5 agent_name

| 值 | 说明 |
|---|---|
| input_parser | 输入解析 Agent |
| pro_agent | 正方 Agent |
| con_agent | 反方 Agent |
| judge_agent | 法官 Agent |

### 3.6 tool_name

| 值 | 说明 |
|---|---|
| cost_analyzer | 成本计算工具 |
| cooling_reminder | 冷静期提醒工具 |
| decision_score | 决策评分工具，可选 |

### 3.7 risk_level

| 值 | 说明 |
|---|---|
| low | 低风险 |
| medium | 中风险 |
| high | 高风险 |

## 4. 状态流转

```text
collecting
  -> ready_for_debate
  -> debating
  -> completed

collecting
  -> rejected

completed
  -> archived
```

规则：

- 信息不足时保持 `collecting`。
- 信息完整后进入 `ready_for_debate`。
- 调用 `POST /api/cases/{case_id}/debate` 后进入 `debating`。
- Agent 分析和判决书生成完成后进入 `completed`。
- 医疗、法律、投资、贷款、辞职、亲密关系、重大人生决策等高风险输入进入 `rejected`。

## 5. 公共数据结构

### 5.1 Case

```json
{
  "case_id": "case_001",
  "user_id": "u001",
  "case_type": "shopping",
  "title": "是否购买降噪耳机",
  "description": "我想买一副 1299 元的降噪耳机，最近学习需要安静。",
  "status": "ready_for_debate",
  "collected_fields": {
    "price": 1299,
    "monthly_budget_left": 2000,
    "owned_alternatives": "普通耳机"
  },
  "missing_fields": [],
  "final_decision": null,
  "report_id": null,
  "created_at": "2026-07-01T10:00:00+08:00",
  "updated_at": "2026-07-01T10:05:00+08:00"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| case_id | string | 是 | 案件 ID |
| user_id | string | 是 | 用户 ID |
| case_type | string | 是 | `shopping` 或 `time` |
| title | string | 是 | 案件标题 |
| description | string | 是 | 用户原始描述 |
| status | string | 是 | 案件状态 |
| collected_fields | object | 是 | 已收集的结构化字段 |
| missing_fields | string[] | 是 | 仍缺失的字段 |
| final_decision | string/null | 是 | 最终裁决，未完成时为 null |
| report_id | string/null | 是 | 判决书 ID，未生成时为 null |
| created_at | string | 是 | 创建时间 |
| updated_at | string | 是 | 更新时间 |

### 5.2 Message

```json
{
  "message_id": "msg_001",
  "case_id": "case_001",
  "role": "user",
  "content": "我本月预算还剩 2000 元。",
  "created_at": "2026-07-01T10:03:00+08:00"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| message_id | string | 是 | 消息 ID |
| case_id | string | 是 | 案件 ID |
| role | string | 是 | `user`、`assistant`、`agent` |
| content | string | 是 | 消息内容 |
| created_at | string | 是 | 创建时间 |

### 5.3 AgentStep

```json
{
  "agent": "judge_agent",
  "status": "completed",
  "summary": "建议暂缓购买 3 天。",
  "confidence": 0.75,
  "arguments": ["预算占比较高", "已有普通耳机"],
  "used_rag_ids": ["history_001"],
  "used_tool_names": ["cost_analyzer", "cooling_reminder"],
  "error": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| agent | string | 是 | Agent 名称 |
| status | string | 是 | `completed` 或 `failed` |
| summary | string | 是 | 当前 Agent 输出摘要 |
| confidence | number | 是 | 置信度，范围 0 到 1 |
| arguments | string[] | 是 | 主要理由、风险或裁决依据 |
| used_rag_ids | string[] | 是 | 使用的 RAG 证据 ID |
| used_tool_names | string[] | 是 | 使用的工具名 |
| error | string/null | 是 | 失败原因，成功时为 null |

### 5.4 RagEvidence

```json
{
  "id": "history_001",
  "title": "历史闲置记录",
  "content": "用户曾购买蓝牙键盘后使用频率较低。",
  "score": 0.82,
  "source": "decision_history",
  "case_type": "shopping",
  "tags": ["electronics", "idle"],
  "created_at": "2026-06-20T12:00:00+08:00"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| id | string | 是 | 证据 ID |
| title | string | 是 | 证据标题 |
| content | string | 是 | 可引用证据内容 |
| score | number | 是 | 检索相关性分数 |
| source | string | 是 | 来源，例如 `decision_history` 或 `rule_knowledge` |
| case_type | string | 是 | 关联案件类型 |
| tags | string[] | 是 | 标签 |
| created_at | string/null | 是 | 创建时间，无时间时为 null |

### 5.5 ToolResult

```json
{
  "tool_name": "cost_analyzer",
  "status": "success",
  "summary": "该商品占剩余预算约 65%，预算压力中等。",
  "risk_level": "medium",
  "metrics": {
    "budget_ratio": 0.65,
    "budget_left_after_purchase": 701
  },
  "error": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| tool_name | string | 是 | 工具名称 |
| status | string | 是 | `success` 或 `failed` |
| summary | string | 是 | 工具结果摘要 |
| risk_level | string/null | 是 | 风险等级，无风险等级时为 null |
| metrics | object | 是 | 工具结构化指标 |
| error | string/null | 是 | 失败原因，成功时为 null |

### 5.6 DecisionReport

```json
{
  "report_id": "report_001",
  "case_id": "case_001",
  "case_type": "shopping",
  "final_decision": "delay",
  "confidence": 0.75,
  "summary": "本案建议暂缓购买 3 天。",
  "case_summary": "用户想购买 1299 元降噪耳机用于学习。",
  "pro_points": ["存在学习降噪场景，可能提高专注度。"],
  "con_points": ["价格占剩余预算较高，且已有普通耳机。"],
  "rag_evidence": [],
  "tool_results": [],
  "next_actions": ["加入观察清单，3 天后复盘。"],
  "created_at": "2026-07-01T10:10:00+08:00"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| report_id | string | 是 | 判决书 ID |
| case_id | string | 是 | 案件 ID |
| case_type | string | 是 | 案件类型 |
| final_decision | string | 是 | 最终裁决 |
| confidence | number | 是 | 法官 Agent 置信度 |
| summary | string | 是 | 判决摘要 |
| case_summary | string | 是 | 案件摘要 |
| pro_points | string[] | 是 | 正方观点 |
| con_points | string[] | 是 | 反方观点 |
| rag_evidence | RagEvidence[] | 是 | 引用的 RAG 证据 |
| tool_results | ToolResult[] | 是 | 工具调用结果 |
| next_actions | string[] | 是 | 后续动作 |
| created_at | string | 是 | 创建时间 |

### 5.7 TraceItem

```json
{
  "trace_id": "trace_001",
  "step": 1,
  "type": "agent",
  "name": "input_parser",
  "input_summary": "用户想购买降噪耳机",
  "output_summary": "识别为 shopping，缺少预算和替代品信息",
  "duration_ms": 900,
  "status": "completed",
  "error": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trace_id | string | 是 | 轨迹 ID |
| step | number | 是 | 执行顺序 |
| type | string | 是 | `agent`、`rag_search`、`tool_call` |
| name | string | 是 | Agent 名称、工具名或检索名 |
| input_summary | string | 是 | 输入摘要 |
| output_summary | string | 是 | 输出摘要 |
| duration_ms | number | 是 | 耗时 |
| status | string | 是 | `completed` 或 `failed` |
| error | string/null | 是 | 错误信息，成功时为 null |

## 6. 接口总览

| 方法 | 路径 | 用途 | 实现方 | 主要调用方 |
|---|---|---|---|---|
| GET | `/api/health` | 健康检查 | B | 全员 |
| POST | `/api/cases` | 创建案件 | B | A |
| GET | `/api/cases/{case_id}` | 查询案件详情 | B | A/C |
| PATCH | `/api/cases/{case_id}` | 更新案件字段 | B | A/B |
| POST | `/api/cases/{case_id}/messages` | 多轮补充信息 | B/C | A |
| POST | `/api/cases/{case_id}/debate` | 启动 Agent 分析 | B/C | A |
| GET | `/api/cases/{case_id}/trace` | 查询执行轨迹 | B/C | A |
| GET | `/api/cases/{case_id}/report` | 查询判决书 | B/C | A |
| POST | `/api/cases/{case_id}/feedback` | 提交复盘 | B | A |
| GET | `/api/history?user_id=u001` | 查询历史记录 | B/D | A/D |
| POST | `/api/history` | 添加历史记录 | B/D | A |
| POST | `/api/rag/search` | RAG 检索 | D | C |
| POST | `/api/tools/cost-analyzer` | 成本计算 | E | C |
| POST | `/api/tools/cooling-reminder` | 冷静期提醒 | E | C |
| GET | `/api/watchlist?user_id=u001` | 查询观察清单 | B/E | A |

## 7. 健康检查

```text
GET /api/health
```

返回：

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "version": "0.2"
  },
  "message": ""
}
```

## 8. 案件接口

### 8.1 创建案件

```text
POST /api/cases
```

请求：

```json
{
  "user_id": "u001",
  "case_type": "shopping",
  "title": "是否购买降噪耳机",
  "description": "我想买一副 1299 元的降噪耳机，最近学习需要安静。"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| user_id | string | 是 | 用户 ID |
| case_type | string | 是 | `shopping` 或 `time` |
| title | string | 是 | 案件标题 |
| description | string | 是 | 用户原始描述 |

返回：

```json
{
  "success": true,
  "data": {
    "case": {
      "case_id": "case_001",
      "user_id": "u001",
      "case_type": "shopping",
      "title": "是否购买降噪耳机",
      "description": "我想买一副 1299 元的降噪耳机，最近学习需要安静。",
      "status": "collecting",
      "collected_fields": {
        "price": 1299,
        "purpose": "学习"
      },
      "missing_fields": ["monthly_budget_left", "owned_alternatives"],
      "final_decision": null,
      "report_id": null,
      "created_at": "2026-07-01T10:00:00+08:00",
      "updated_at": "2026-07-01T10:00:00+08:00"
    },
    "next_question": "你本月预算还剩多少？是否已经有类似耳机？"
  },
  "message": "case created"
}
```

### 8.2 查询案件详情

```text
GET /api/cases/{case_id}
```

路径参数：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| case_id | string | 是 | 案件 ID |

返回：

```json
{
  "success": true,
  "data": {
    "case": {
      "case_id": "case_001",
      "user_id": "u001",
      "case_type": "shopping",
      "title": "是否购买降噪耳机",
      "description": "我想买一副 1299 元的降噪耳机，最近学习需要安静。",
      "status": "completed",
      "collected_fields": {
        "price": 1299,
        "monthly_budget_left": 2000,
        "owned_alternatives": "普通耳机"
      },
      "missing_fields": [],
      "final_decision": "delay",
      "report_id": "report_001",
      "created_at": "2026-07-01T10:00:00+08:00",
      "updated_at": "2026-07-01T10:10:00+08:00"
    }
  },
  "message": ""
}
```

### 8.3 更新案件字段

```text
PATCH /api/cases/{case_id}
```

请求：

```json
{
  "user_id": "u001",
  "title": "是否购买降噪耳机",
  "description": "我想买一副 1299 元的降噪耳机。",
  "collected_fields": {
    "monthly_budget_left": 2000,
    "owned_alternatives": "普通耳机"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| user_id | string | 是 | 用户 ID |
| title | string | 否 | 新标题 |
| description | string | 否 | 新描述 |
| collected_fields | object | 否 | 用户补充的结构化字段 |

返回：

```json
{
  "success": true,
  "data": {
    "case": {}
  },
  "message": "case updated"
}
```

`case` 使用公共结构 `Case`。

### 8.4 多轮补充信息

```text
POST /api/cases/{case_id}/messages
```

请求：

```json
{
  "user_id": "u001",
  "message": "我本月预算还剩 2000 元，已有一副普通耳机。"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| user_id | string | 是 | 用户 ID |
| message | string | 是 | 用户补充信息 |

返回：

```json
{
  "success": true,
  "data": {
    "reply": "信息已补充。当前案件信息已经完整，可以进入正反方分析。",
    "case_status": "ready_for_debate",
    "collected_fields": {
      "monthly_budget_left": 2000,
      "owned_alternatives": "普通耳机"
    },
    "missing_fields": []
  },
  "message": ""
}
```

## 9. Agent 分析接口

### 9.1 启动多 Agent 分析

```text
POST /api/cases/{case_id}/debate
```

请求：

```json
{
  "user_id": "u001"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| user_id | string | 是 | 用户 ID |

返回：

```json
{
  "success": true,
  "data": {
    "case_id": "case_001",
    "case_status": "completed",
    "steps": [
      {
        "agent": "input_parser",
        "status": "completed",
        "summary": "识别为 shopping，信息完整。",
        "confidence": 0.92,
        "arguments": ["识别到商品价格、预算和替代品"],
        "used_rag_ids": [],
        "used_tool_names": [],
        "error": null
      },
      {
        "agent": "pro_agent",
        "status": "completed",
        "summary": "该耳机能改善学习环境，存在明确使用场景。",
        "confidence": 0.7,
        "arguments": ["学习场景明确", "降噪功能与目标相关"],
        "used_rag_ids": [],
        "used_tool_names": [],
        "error": null
      },
      {
        "agent": "con_agent",
        "status": "completed",
        "summary": "价格占剩余预算比例较高，且已有普通耳机。",
        "confidence": 0.82,
        "arguments": ["预算压力中等", "存在已有替代品"],
        "used_rag_ids": ["history_001"],
        "used_tool_names": ["cost_analyzer"],
        "error": null
      },
      {
        "agent": "judge_agent",
        "status": "completed",
        "summary": "建议暂缓 3 天后再决定。",
        "confidence": 0.75,
        "arguments": ["预算占比 65%", "历史存在电子产品闲置记录"],
        "used_rag_ids": ["history_001"],
        "used_tool_names": ["cost_analyzer", "cooling_reminder"],
        "error": null
      }
    ],
    "rag_evidence": [],
    "tool_results": [],
    "report": {}
  },
  "message": "debate completed"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| case_id | string | 是 | 案件 ID |
| case_status | string | 是 | 分析后的案件状态 |
| steps | AgentStep[] | 是 | Agent 执行结果 |
| rag_evidence | RagEvidence[] | 是 | 本次使用的证据 |
| tool_results | ToolResult[] | 是 | 本次工具调用结果 |
| report | DecisionReport | 是 | 生成的判决书 |

### 9.2 高风险输入返回示例

当输入属于医疗、法律、投资、贷款、辞职、亲密关系、重大人生决策等高风险范围时，不进入正反方辩论。

```json
{
  "success": false,
  "data": {
    "case_id": "case_001",
    "case_status": "rejected",
    "reason": "high_risk_domain"
  },
  "message": "HIGH_RISK_DECISION"
}
```

## 10. RAG 接口

### 10.1 RAG 检索

```text
POST /api/rag/search
```

请求：

```json
{
  "user_id": "u001",
  "case_id": "case_001",
  "case_type": "shopping",
  "query": "降噪耳机 学习 电子产品 冲动消费",
  "top_k": 3
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| user_id | string | 是 | 用户 ID |
| case_id | string | 是 | 案件 ID |
| case_type | string | 是 | 案件类型 |
| query | string | 是 | 检索查询文本 |
| top_k | number | 否 | 返回条数，默认 3 |

返回：

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "id": "history_001",
        "title": "历史闲置记录",
        "content": "用户曾购买蓝牙键盘后使用频率较低。",
        "score": 0.82,
        "source": "decision_history",
        "case_type": "shopping",
        "tags": ["electronics", "idle"],
        "created_at": "2026-06-20T12:00:00+08:00"
      }
    ]
  },
  "message": ""
}
```

规则：

- 返回结果必须符合 `RagEvidence`。
- 没有结果时返回空数组 `[]`。
- RAG 不允许编造历史记录。
- RAG 只返回证据，不直接输出最终建议。

## 11. MCP 工具接口

MVP 阶段先用 HTTP 接口模拟 MCP 工具调用，后续可以封装为 MCP tool schema。工具输出必须符合 `ToolResult`。

### 11.1 成本计算工具

```text
POST /api/tools/cost-analyzer
```

购物场景请求：

```json
{
  "case_id": "case_001",
  "case_type": "shopping",
  "price": 1299,
  "monthly_budget_left": 2000
}
```

时间场景请求：

```json
{
  "case_id": "case_002",
  "case_type": "time",
  "hours_required": 16,
  "free_hours_this_week": 20,
  "urgent_tasks": 2
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| case_id | string | 是 | 案件 ID |
| case_type | string | 是 | `shopping` 或 `time` |
| price | number | shopping 必填 | 商品价格 |
| monthly_budget_left | number | shopping 必填 | 本月剩余预算 |
| hours_required | number | time 必填 | 需要投入小时数 |
| free_hours_this_week | number | time 必填 | 本周可支配时间 |
| urgent_tasks | number | time 必填 | 紧急任务数量 |

返回：

```json
{
  "success": true,
  "data": {
    "tool_name": "cost_analyzer",
    "status": "success",
    "summary": "该商品占剩余预算约 65%，预算压力中等。",
    "risk_level": "medium",
    "metrics": {
      "budget_ratio": 0.65,
      "budget_left_after_purchase": 701
    },
    "error": null
  },
  "message": ""
}
```

### 11.2 冷静期提醒工具

```text
POST /api/tools/cooling-reminder
```

请求：

```json
{
  "user_id": "u001",
  "case_id": "case_001",
  "title": "降噪耳机冷静期复盘",
  "cooling_days": 3,
  "reason": "预算占比较高，建议冷静 3 天后复盘。",
  "watch_items": ["是否仍然需要", "是否有低价替代品"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| user_id | string | 是 | 用户 ID |
| case_id | string | 是 | 案件 ID |
| title | string | 是 | 提醒标题 |
| cooling_days | number | 是 | 冷静期天数 |
| reason | string | 是 | 设置提醒的原因 |
| watch_items | string[] | 是 | 冷静期观察项 |

返回：

```json
{
  "success": true,
  "data": {
    "tool_name": "cooling_reminder",
    "status": "success",
    "summary": "已创建 3 天冷静期提醒。",
    "risk_level": null,
    "metrics": {
      "reminder_id": "reminder_001",
      "cooling_days": 3,
      "due_at": "2026-07-04T20:00:00+08:00",
      "watch_items": ["是否仍然需要", "是否有低价替代品"]
    },
    "error": null
  },
  "message": ""
}
```

工具失败时：

```json
{
  "success": true,
  "data": {
    "tool_name": "cooling_reminder",
    "status": "failed",
    "summary": "冷静期提醒创建失败。",
    "risk_level": null,
    "metrics": {},
    "error": "REMINDER_CREATE_FAILED"
  },
  "message": ""
}
```

规则：

- 工具失败不应导致 Agent 主流程中断。
- 法官 Agent 必须在判决书中标记工具结果缺失。
- 工具只提供结构化依据，不直接决定最终裁决。

## 12. 判决书与轨迹接口

### 12.1 查询判决书

```text
GET /api/cases/{case_id}/report
```

返回：

```json
{
  "success": true,
  "data": {
    "report": {
      "report_id": "report_001",
      "case_id": "case_001",
      "case_type": "shopping",
      "final_decision": "delay",
      "confidence": 0.75,
      "summary": "本案建议暂缓购买 3 天。",
      "case_summary": "用户想购买 1299 元降噪耳机用于学习。",
      "pro_points": ["存在学习降噪场景，可能提高专注度。"],
      "con_points": ["价格占剩余预算较高，且已有普通耳机。"],
      "rag_evidence": [],
      "tool_results": [],
      "next_actions": ["加入观察清单，3 天后复盘。"],
      "created_at": "2026-07-01T10:10:00+08:00"
    }
  },
  "message": ""
}
```

### 12.2 查询 Agent 执行轨迹

```text
GET /api/cases/{case_id}/trace
```

返回：

```json
{
  "success": true,
  "data": {
    "case_id": "case_001",
    "trace": [
      {
        "trace_id": "trace_001",
        "step": 1,
        "type": "agent",
        "name": "input_parser",
        "input_summary": "用户想购买降噪耳机",
        "output_summary": "识别为 shopping，缺少预算和替代品信息",
        "duration_ms": 900,
        "status": "completed",
        "error": null
      },
      {
        "trace_id": "trace_002",
        "step": 2,
        "type": "rag_search",
        "name": "rag_search",
        "input_summary": "降噪耳机 学习 电子产品",
        "output_summary": "召回 1 条历史记录",
        "duration_ms": 120,
        "status": "completed",
        "error": null
      }
    ]
  },
  "message": ""
}
```

## 13. 历史记录接口

### 13.1 查询历史记录

```text
GET /api/history?user_id=u001
```

返回：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "history_id": "history_001",
        "user_id": "u001",
        "case_type": "shopping",
        "summary": "上个月购买蓝牙键盘后使用频率较低。",
        "result": "regret",
        "tags": ["electronics", "idle"],
        "created_at": "2026-06-20T12:00:00+08:00"
      }
    ]
  },
  "message": ""
}
```

### 13.2 添加历史记录

```text
POST /api/history
```

请求：

```json
{
  "user_id": "u001",
  "case_type": "shopping",
  "summary": "购买蓝牙键盘后使用频率较低。",
  "result": "regret",
  "tags": ["electronics", "idle"]
}
```

返回：

```json
{
  "success": true,
  "data": {
    "history_id": "history_002"
  },
  "message": "history created"
}
```

## 14. 观察清单与复盘接口

### 14.1 查询观察清单

```text
GET /api/watchlist?user_id=u001
```

返回：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "case_id": "case_001",
        "title": "降噪耳机",
        "reason": "预算占比较高，建议冷静 3 天。",
        "due_at": "2026-07-04T20:00:00+08:00",
        "status": "waiting"
      }
    ]
  },
  "message": ""
}
```

### 14.2 提交决策复盘

```text
POST /api/cases/{case_id}/feedback
```

请求：

```json
{
  "user_id": "u001",
  "actual_action": "not_buy",
  "satisfaction": 5,
  "review": "冷静三天后发现不是刚需，没有购买。"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| user_id | string | 是 | 用户 ID |
| actual_action | string | 是 | 用户实际行为 |
| satisfaction | number | 是 | 满意度，1 到 5 |
| review | string | 是 | 复盘文本 |

返回：

```json
{
  "success": true,
  "data": {
    "saved_to_history": true,
    "history_id": "history_003"
  },
  "message": "feedback saved"
}
```

## 15. 错误码

| 错误码 | 含义 | 处理方式 |
|---|---|---|
| CASE_NOT_FOUND | 案件不存在 | 检查 `case_id` |
| MISSING_FIELDS | 案件信息不完整 | 前端继续追问用户 |
| UNSUPPORTED_CASE_TYPE | 不支持的案件类型 | 只允许 `shopping` 或 `time` |
| HIGH_RISK_DECISION | 高风险决策 | 拒绝裁决并提示范围边界 |
| LLM_ERROR | 大模型调用失败 | 提示重试，可使用 mock |
| LLM_JSON_PARSE_ERROR | LLM 输出无法解析 | 保留原始输出并提示重试 |
| RAG_ERROR | 检索失败 | 允许无历史依据继续 |
| TOOL_ERROR | 工具调用失败 | 标记工具结果缺失 |
| VALIDATION_ERROR | 请求字段错误 | 检查请求参数 |

## 16. 联调要求

- A 前端必须能展示 `steps`、`rag_evidence`、`tool_results`、`trace`、`report`。
- B 后端必须保证接口路径、字段名、枚举值与本文档一致。
- C Agent 编排必须输出 `AgentStep`、`DecisionReport`、`TraceItem`。
- D RAG 必须返回 `RagEvidence[]`，无结果时返回空数组。
- E MCP 工具必须返回 `ToolResult`，失败时返回 `status: failed` 和 `error`。
- 所有模块必须使用 `snake_case` 字段名。
- 接口变更必须先改本文档，再改代码。
