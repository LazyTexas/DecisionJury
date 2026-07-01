# DecisionJury API 文档

## 1. 文档目的

本文档用于统一前端、后端、Agent、RAG、MCP 工具之间的数据格式。所有接口开发和联调必须以本文档为准。

如果接口字段发生变化，必须同步更新本文档。

## 2. 通用约定

### 2.1 基础路径

```text
/api
```

### 2.2 通用响应格式

```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

### 2.3 通用错误响应

```json
{
  "success": false,
  "data": null,
  "message": "CASE_NOT_FOUND"
}
```

### 2.4 时间格式

统一使用 ISO 8601：

```text
2026-07-04T20:00:00+08:00
```

## 3. 核心枚举

### 3.1 case_type

```text
shopping
time
```

### 3.2 case_status

```text
collecting
ready_for_debate
debating
completed
archived
```

### 3.3 shopping final_decision

```text
buy
delay
reject
alternative
```

### 3.4 time final_decision

```text
accept
partial_accept
delay
reject
```

### 3.5 risk_level

```text
low
medium
high
```

## 4. 创建决策案件

```text
POST /api/cases/create
```

### 4.1 请求参数

```json
{
  "user_id": "u001",
  "case_type": "shopping",
  "title": "是否购买降噪耳机",
  "description": "我想买一副 1299 元的降噪耳机，最近学习需要安静。"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| user_id | string | 是 | 用户 ID |
| case_type | string | 是 | shopping 或 time |
| title | string | 是 | 案件标题 |
| description | string | 是 | 用户原始描述 |

### 4.2 返回参数

```json
{
  "success": true,
  "data": {
    "case_id": "case_001",
    "case_type": "shopping",
    "status": "collecting",
    "missing_fields": ["monthly_budget_left", "owned_alternatives"],
    "next_question": "你本月预算还剩多少？是否已经有类似耳机？"
  },
  "message": "case created"
}
```

## 5. 多轮对话

```text
POST /api/chat
```

### 5.1 请求参数

```json
{
  "user_id": "u001",
  "case_id": "case_001",
  "message": "我本月预算还剩 2000 元，已有一副普通耳机。"
}
```

### 5.2 返回参数

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

## 6. 查询案件详情

```text
GET /api/cases/{case_id}
```

### 6.1 返回参数

```json
{
  "success": true,
  "data": {
    "case_id": "case_001",
    "user_id": "u001",
    "case_type": "shopping",
    "title": "是否购买降噪耳机",
    "description": "我想买一副 1299 元的降噪耳机，最近学习需要安静。",
    "status": "completed",
    "final_decision": "delay",
    "report_id": "report_001",
    "created_at": "2026-07-01T10:00:00+08:00",
    "updated_at": "2026-07-01T10:10:00+08:00"
  },
  "message": ""
}
```

## 7. 启动多 Agent 分析

```text
POST /api/cases/{case_id}/debate
```

### 7.1 请求参数

```json
{
  "user_id": "u001"
}
```

### 7.2 返回参数

```json
{
  "success": true,
  "data": {
    "case_id": "case_001",
    "status": "completed",
    "steps": [
      {
        "agent": "pro_agent",
        "status": "completed",
        "summary": "该耳机能改善学习环境，存在明确使用场景。"
      },
      {
        "agent": "con_agent",
        "status": "completed",
        "summary": "价格占剩余预算比例较高，且已有普通耳机。"
      },
      {
        "agent": "judge_agent",
        "status": "completed",
        "summary": "建议暂缓 3 天后再决定。"
      }
    ]
  },
  "message": "debate completed"
}
```

## 8. RAG 检索

```text
POST /api/rag/search
```

### 8.1 请求参数

```json
{
  "user_id": "u001",
  "case_id": "case_001",
  "query": "降噪耳机 学习 电子产品 冲动消费",
  "top_k": 3
}
```

### 8.2 返回参数

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "text": "上个月购买蓝牙键盘后使用频率较低。",
        "score": 0.82,
        "source": "decision_history",
        "tags": ["electronics", "idle"]
      }
    ]
  },
  "message": ""
}
```

## 9. 查询历史记录

```text
GET /api/history?user_id=u001
```

### 9.1 返回参数

```json
{
  "success": true,
  "data": [
    {
      "history_id": "h001",
      "case_type": "shopping",
      "summary": "上个月购买蓝牙键盘后使用频率较低。",
      "result": "regret",
      "tags": ["electronics", "idle"],
      "created_at": "2026-06-20T12:00:00+08:00"
    }
  ],
  "message": ""
}
```

## 10. 添加历史记录

```text
POST /api/history
```

### 10.1 请求参数

```json
{
  "user_id": "u001",
  "case_type": "shopping",
  "summary": "购买蓝牙键盘后使用频率较低。",
  "result": "regret",
  "tags": ["electronics", "idle"]
}
```

### 10.2 返回参数

```json
{
  "success": true,
  "data": {
    "history_id": "h002"
  },
  "message": "history created"
}
```

## 11. 成本计算工具

```text
POST /api/tools/cost
```

### 11.1 购物场景请求

```json
{
  "case_type": "shopping",
  "price": 1299,
  "monthly_budget_left": 2000
}
```

### 11.2 购物场景返回

```json
{
  "success": true,
  "data": {
    "risk_level": "medium",
    "metrics": {
      "budget_ratio": 0.65,
      "budget_left_after_purchase": 701
    },
    "explanation": "该商品占剩余预算约 65%，建议进入冷静期。"
  },
  "message": ""
}
```

### 11.3 时间场景请求

```json
{
  "case_type": "time",
  "hours_required": 16,
  "free_hours_this_week": 20,
  "urgent_tasks": 2
}
```

### 11.4 时间场景返回

```json
{
  "success": true,
  "data": {
    "risk_level": "high",
    "metrics": {
      "time_ratio": 0.8,
      "urgent_tasks": 2
    },
    "explanation": "该活动占用本周 80% 空闲时间，且存在紧急任务冲突。"
  },
  "message": ""
}
```

## 12. 冷静期提醒工具

```text
POST /api/tools/reminder
```

### 12.1 请求参数

```json
{
  "user_id": "u001",
  "case_id": "case_001",
  "title": "降噪耳机冷静期复盘",
  "days": 3,
  "reason": "预算占比较高，建议冷静 3 天后复盘。"
}
```

### 12.2 返回参数

```json
{
  "success": true,
  "data": {
    "reminder_id": "r001",
    "due_at": "2026-07-04T20:00:00+08:00",
    "status": "scheduled"
  },
  "message": "reminder created"
}
```

## 13. 查询观察清单

```text
GET /api/watchlist?user_id=u001
```

### 13.1 返回参数

```json
{
  "success": true,
  "data": [
    {
      "case_id": "case_001",
      "title": "降噪耳机",
      "reason": "预算占比较高，建议冷静 3 天。",
      "due_at": "2026-07-04T20:00:00+08:00",
      "status": "waiting"
    }
  ],
  "message": ""
}
```

## 14. 生成判决书

```text
POST /api/report/generate
```

### 14.1 请求参数

```json
{
  "case_id": "case_001"
}
```

### 14.2 返回参数

```json
{
  "success": true,
  "data": {
    "report_id": "report_001",
    "summary": "本案建议暂缓购买 3 天。",
    "final_decision": "delay",
    "sections": {
      "case_summary": "用户想购买 1299 元降噪耳机用于学习。",
      "pro_opinion": "存在学习降噪场景，可能提高专注度。",
      "con_opinion": "价格占剩余预算较高，且已有普通耳机。",
      "evidence": ["上个月购买蓝牙键盘后使用频率较低。"],
      "tool_result": "预算占比 65%。",
      "next_action": "加入观察清单，3 天后复盘。"
    }
  },
  "message": ""
}
```

## 15. 获取 Agent 执行轨迹

```text
GET /api/cases/{case_id}/trace
```

### 15.1 返回参数

```json
{
  "success": true,
  "data": {
    "case_id": "case_001",
    "trace": [
      {
        "step": 1,
        "type": "rag_search",
        "input": "降噪耳机 学习 电子产品",
        "output_summary": "召回 3 条历史记录",
        "duration_ms": 120
      },
      {
        "step": 2,
        "type": "tool_call",
        "tool_name": "cost_analyzer",
        "output_summary": "预算占比 65%",
        "duration_ms": 30
      }
    ]
  },
  "message": ""
}
```

## 16. 提交决策复盘

```text
POST /api/cases/{case_id}/feedback
```

### 16.1 请求参数

```json
{
  "user_id": "u001",
  "actual_action": "not_buy",
  "satisfaction": 5,
  "review": "冷静三天后发现不是刚需，没有购买。"
}
```

### 16.2 返回参数

```json
{
  "success": true,
  "data": {
    "saved_to_history": true
  },
  "message": "feedback saved"
}
```

## 17. 错误码

| 错误码 | 含义 | 处理方式 |
|---|---|---|
| CASE_NOT_FOUND | 案件不存在 | 检查 case_id |
| MISSING_FIELDS | 案件信息不完整 | 前端继续追问用户 |
| UNSUPPORTED_CASE_TYPE | 不支持的案件类型 | 只允许 shopping 或 time |
| HIGH_RISK_DECISION | 高风险决策 | 拒绝裁决并提示范围边界 |
| LLM_ERROR | 大模型调用失败 | 提示重试 |
| RAG_ERROR | 检索失败 | 允许无历史依据继续 |
| TOOL_ERROR | 工具调用失败 | 标记工具结果缺失 |

## 18. 前后端联调要求

- 前端必须能处理 `missing_fields`。
- 前端必须能展示 Agent 分析过程。
- 前端必须能展示 RAG 证据。
- 前端必须能展示工具调用结果。
- 前端必须能展示最终判决书。
- 后端返回字段不能随意改名。
