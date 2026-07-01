# DecisionJury SPEC 项目规格说明书

## 1. 项目概述

DecisionJury 是一个面向日常低风险决策的多 Agent 冷静决策助手。系统聚焦购物决策和时间决策，通过正反方 Agent 辩论、历史记录 RAG 检索、MCP 工具调用和法官 Agent 裁决，帮助用户在冲动或犹豫时获得更理性的辅助建议。

项目不追求替用户做决定，而是帮助用户完成一套可解释的决策流程：

```text
看清动机 -> 补全信息 -> 检索历史 -> 计算成本 -> 正反分析 -> 输出建议 -> 设置冷静期
```

## 2. 项目目标

### 2.1 产品目标

- 帮助用户减少冲动消费。
- 帮助用户评估时间安排是否合理。
- 让用户能看到正反两方面理由，而不是只听单一建议。
- 通过历史记录提醒用户避免重复踩坑。
- 通过冷静期提醒把建议转化为后续行动。

### 2.2 技术目标

- 调用至少一个 LLM API。
- 实现至少一个 RAG 检索功能。
- 实现至少两个 MCP 工具并被 Agent 调用。
- 支持多轮对话和基本状态管理。
- 能生成结构化判决书。
- 能通过前端完成完整演示。

## 3. 目标用户

### 3.1 购物决策用户

- 大学生。
- 年轻消费者。
- 数码、服饰、课程、会员服务等消费频率较高的人。
- 容易因为促销、种草内容、情绪上头而购买的人。

### 3.2 时间决策用户

- 大学生。
- 社团成员。
- 学生干部。
- 小组项目成员。
- 容易接太多任务、难以拒绝的人。

## 4. 用户痛点

### 4.1 购物决策痛点

- 商品种草信息太多，用户容易只看到优点。
- 用户很难记住自己过去买过哪些闲置物品。
- 购物前很少认真计算预算占比。
- 购买动机可能是情绪驱动，而不是真实需求。
- 普通 AI 问答缺少用户个人历史记录。

### 4.2 时间决策痛点

- 用户容易低估活动或任务占用的时间。
- 用户常常忽略已有任务和截止时间。
- 用户不擅长评估机会成本。
- 用户很难根据历史拖延记录调整当前决策。
- 普通待办工具只记录任务，不帮助判断是否值得接。

## 5. 项目边界

### 5.1 支持范围

系统只处理：

- 购物决策。
- 时间决策。

### 5.2 不支持范围

系统不处理：

- 医疗决策。
- 法律决策。
- 投资理财决策。
- 借贷决策。
- 就业离职决策。
- 亲密关系决策。
- 其他可能带来重大现实后果的高风险决策。

### 5.3 输出边界

系统输出是辅助建议，不是强制结论。  
系统应该使用“建议”“可以考虑”“风险较高”等表述，避免“必须”“一定”“保证”等绝对化表述。

## 6. 核心业务流程

### 6.1 总流程

```text
用户提交决策问题
  |
输入解析 Agent 判断案件类型
  |
系统判断信息是否完整
  |
多轮追问补全关键字段
  |
RAG 检索历史记录和规则知识
  |
调用 MCP 工具计算成本或设置提醒
  |
正方 Agent 分析收益
  |
反方 Agent 分析风险
  |
法官 Agent 综合裁决
  |
生成判决书
  |
保存历史记录和观察清单
```

### 6.2 购物决策流程

```text
用户提交购物想法
  |
提取商品、价格、购买动机
  |
追问预算、已有替代品、预计使用频率
  |
检索历史购物记录、闲置记录、预算偏好
  |
调用成本计算工具
  |
正方 Agent 分析购买价值
  |
反方 Agent 分析冲动风险、闲置风险和平替方案
  |
法官 Agent 输出 buy / delay / reject / alternative
  |
如需暂缓，调用冷静期提醒工具
```

### 6.3 时间决策流程

```text
用户提交时间安排问题
  |
提取活动、占用时间、动机
  |
追问当前任务、截止时间、活动收益、是否可部分参加
  |
检索历史任务延期记录、活动复盘、时间偏好
  |
调用成本计算工具
  |
正方 Agent 分析参加收益
  |
反方 Agent 分析时间成本和机会成本
  |
法官 Agent 输出 accept / partial_accept / delay / reject
  |
如需后续提醒，调用冷静期提醒工具
```

## 7. Agent 角色设计

### 7.1 输入解析 Agent

职责：

- 判断案件类型。
- 提取关键字段。
- 判断缺失字段。
- 决定是否继续追问。

输出格式：

```json
{
  "case_type": "shopping",
  "extracted_fields": {
    "item_name": "降噪耳机",
    "price": 1299,
    "motivation": "学习需要安静"
  },
  "missing_fields": ["monthly_budget_left", "owned_alternatives"],
  "next_question": "你本月预算还剩多少？是否已经有类似耳机？"
}
```

### 7.2 正方 Agent

职责：

- 分析执行该决策的收益。
- 说明它为什么可能值得做。
- 不允许忽略预算和时间约束。
- 必须结合用户动机输出观点。

购物场景关注：

- 商品能解决的问题。
- 使用频率是否足够。
- 长期价值是否明显。
- 是否符合用户当前目标。

时间场景关注：

- 活动收益。
- 成长价值。
- 人际价值。
- 是否与长期目标一致。

### 7.3 反方 Agent

职责：

- 分析风险、成本和替代方案。
- 主动寻找冲动因素。
- 主动引用历史记录。
- 不允许只输出情绪化反对。

购物场景关注：

- 闲置风险。
- 预算压力。
- 溢价风险。
- 平替方案。

时间场景关注：

- 作业或项目延期风险。
- 精力消耗。
- 机会成本。
- 是否可以拒绝或部分参加。

### 7.4 法官 Agent

职责：

- 综合正方、反方、RAG 证据和工具结果。
- 输出明确但非强制的辅助建议。
- 生成结构化判决书。
- 如果证据不足，需要说明不确定性。

输出必须包含：

```json
{
  "final_decision": "delay",
  "confidence": 0.78,
  "reasons": [],
  "evidence": [],
  "tool_results": {},
  "next_actions": []
}
```

## 8. RAG 设计

### 8.1 知识库类型

RAG 知识库分为两类：

#### 用户历史库

- 历史购物决策。
- 历史时间决策。
- 后悔记录。
- 闲置记录。
- 预算偏好。
- 时间偏好。

#### 决策规则库

- 冲动消费判断规则。
- 时间成本评估规则。
- 冷静期建议规则。
- 决策复盘模板。

### 8.2 Chunk 设计

每条历史记录作为一个独立 chunk。

示例：

```json
{
  "type": "shopping_history",
  "text": "2026-06-05 用户购买机械键盘 399 元，实际使用频率较低，复盘结论为冲动购买。",
  "tags": ["electronics", "idle", "regret"],
  "created_at": "2026-06-05"
}
```

### 8.3 检索策略

MVP 使用以下任一方案即可：

- BM25 检索。
- 向量检索。
- BM25 + 向量混合检索。

检索返回 Top 3 到 Top 5 条结果。

### 8.4 检索输出

每条结果至少包含：

- text。
- score。
- source。
- tags。

## 9. MCP 工具设计

### 9.1 cost_analyzer

功能：

- 购物场景：计算商品价格、预算占比、剩余预算、风险等级。
- 时间场景：计算占用时长、空闲时间占比、任务冲突等级。

购物输入：

```json
{
  "case_type": "shopping",
  "price": 1299,
  "monthly_budget_left": 2000
}
```

购物输出：

```json
{
  "risk_level": "medium",
  "metrics": {
    "budget_ratio": 0.65,
    "budget_left_after_purchase": 701
  },
  "explanation": "该商品占剩余预算约 65%，建议进入冷静期。"
}
```

时间输入：

```json
{
  "case_type": "time",
  "hours_required": 16,
  "free_hours_this_week": 20,
  "urgent_tasks": 2
}
```

时间输出：

```json
{
  "risk_level": "high",
  "metrics": {
    "time_ratio": 0.8,
    "urgent_tasks": 2
  },
  "explanation": "该活动占用本周 80% 空闲时间，且存在紧急任务冲突。"
}
```

### 9.2 cooling_reminder

功能：

- 将案件加入观察清单。
- 设置冷静期天数。
- 生成提醒任务。

输入：

```json
{
  "user_id": "u001",
  "case_id": "case_001",
  "title": "降噪耳机冷静期复盘",
  "days": 3,
  "reason": "预算占比较高"
}
```

输出：

```json
{
  "reminder_id": "r001",
  "due_at": "2026-07-04T20:00:00+08:00",
  "status": "scheduled"
}
```

### 9.3 decision_score 可选工具

功能：

- 输出必要性评分。
- 输出风险评分。
- 输出冲动指数。
- 输出推荐等级。

该工具不是 MVP 必做项。

## 10. 系统架构

```text
Frontend
  |
FastAPI Backend
  |
Agent Orchestrator
  |-- LLM API
  |-- RAG Retrieval
  |-- MCP Tools
  |-- State Store
  |
SQLite / Vector Store
```

## 11. 数据存储设计

建议使用：

- SQLite：保存用户、案件、观察清单、提醒任务。
- ChromaDB 或 FAISS：保存历史记录向量。

### 11.1 users

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | 用户 ID |
| name | string | 用户昵称 |
| created_at | datetime | 创建时间 |

### 11.2 cases

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | 案件 ID |
| user_id | string | 用户 ID |
| case_type | string | shopping 或 time |
| title | string | 案件标题 |
| description | text | 用户原始描述 |
| status | string | collecting、ready_for_debate、debating、completed |
| final_decision | string | 最终裁决 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 11.3 case_messages

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | 消息 ID |
| case_id | string | 案件 ID |
| role | string | user、assistant、agent |
| content | text | 消息内容 |
| created_at | datetime | 创建时间 |

### 11.4 decision_history

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | 历史记录 ID |
| user_id | string | 用户 ID |
| case_type | string | shopping 或 time |
| summary | text | 历史摘要 |
| result | string | worth、regret、neutral |
| tags | string | 标签 |
| created_at | datetime | 创建时间 |

### 11.5 reminders

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | 提醒 ID |
| user_id | string | 用户 ID |
| case_id | string | 案件 ID |
| title | string | 提醒标题 |
| due_at | datetime | 到期时间 |
| status | string | scheduled、done、cancelled |

## 12. 状态管理

系统需要保存：

- 当前案件状态。
- 已收集字段。
- 缺失字段。
- 历史对话。
- Agent 输出。
- RAG 检索结果。
- 工具调用结果。
- 最终裁决。

## 13. 非功能需求

- 响应时间：单次普通对话建议控制在 10 秒内。
- 可解释性：裁决书必须说明依据。
- 可演示性：核心流程必须能稳定复现。
- 可维护性：Prompt、工具、数据结构分文件管理。
- 可扩展性：后续可以增加订阅决策，但 MVP 不做。

## 14. 异常处理

- LLM 调用失败：返回友好提示，允许用户重试。
- RAG 无结果：明确说明“未找到相关历史记录”，不能编造。
- MCP 工具失败：保留 Agent 分析，但标记工具结果缺失。
- 用户输入高风险决策：拒绝裁决，提示项目仅支持低风险日常决策。

## 15. 成功标准

- 两类案件流程均可完整运行。
- RAG 和 MCP 工具能被 Agent 实际调用。
- 判决书结果可解释。
- 前端能展示多 Agent 过程。
- 项目能完成答辩演示。
