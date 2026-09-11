# DecisionJury 测试计划与验收记录

> 适用代码基线：`dev@53d70bc`，本轮范围为购物决策。`time` 主流程延期，不作为验收缺陷；已有时间工具/检索单测可作为组件兼容测试保留。本文中的“预期”不是已通过结果。

## 1. 验收分层

| 层次 | 要证明什么 | 不能替代什么 |
|---|---|---|
| 静态核对 | 字段、路由、规则、文档与代码相符 | 真实运行和部署 |
| 单元/契约测试 | 规则、schema、mock响应、adapter和隔离路由行为 | 真实DeepSeek质量、浏览器体验 |
| 真实API验收 | parser、正反方、法官说明实际调用模型且无静默降级 | 整个Web持久化闭环 |
| 端到端/页面 | 注册 → 创建 → 补充 → 庭审/报告 → 提醒 → 复盘 | 生产安全和可靠性 |
| 部署演练 | 当前构建、数据保留、服务互通和演示复现 | 长期可用性或未测的公网性能 |

## 2. 安全测试环境

使用专门终端，不读取/打印 Key 文件内容，不对日常数据库做测试。TestClient 生命周期会执行数据库检查，仅替换请求依赖不足以保护真实数据库，因此测试前同时设置 `DATABASE_URL`。

Windows PowerShell，仓库根目录：

```powershell
$env:DATABASE_URL = "sqlite:///:memory:"
$env:ENV = "development"
$env:DEEPSEEK_API_KEY = ""
$env:PYTHON_DOTENV_DISABLED = "1"
$env:RAG_LIVE_RECORDS = "0"
$env:PYTHONIOENCODING = "utf-8"
uv run --frozen pytest -p no:cacheprovider tests
```

这些变量只用于该测试终端；不要随后在同一终端启动日常服务。`PYTHON_DOTENV_DISABLED=1` 禁用已锁定版本 python-dotenv 的文件加载，避免清空环境变量后又从本机 `.env` 读入 Key。测试库 fixture 使用外键和占位用户/案件；新用例应使用独立 ID，不将固定占位 ID 当作空数据。

Linux/macOS 可在单条命令范围设置同样的变量：

```bash
DATABASE_URL=sqlite:///:memory: ENV=development DEEPSEEK_API_KEY= PYTHON_DOTENV_DISABLED=1 RAG_LIVE_RECORDS=0 PYTHONIOENCODING=utf-8 uv run --frozen pytest -p no:cacheprovider tests
```

首次安装依赖见 [README](../README.md)。`httpx2` 已列在开发依赖中，不再以手动安装未记录包的方式维持测试环境。

当前先显式指定 `tests/`：根目录自动收集会导入 `backend/test/test_feedback_quick.py`，该辅助脚本在导入时直接查询/写入默认数据库，并非隔离 fixture 用例。在内存空库会报错，在日常数据库上则可能写入测试案件；不要通过切回真实数据库规避此问题。迁移测试另有引擎隔离缺陷，见§9，指定目录并不代表全部通过。

### 2.1 定向命令

以下命令沿用上面的隔离环境：

```powershell
uv run --frozen pytest -p no:cacheprovider tests/test_input_parser.py tests/test_llm_client.py tests/test_judge_agent.py tests/test_agent_flow.py tests/test_mcp_adapter.py tests/test_rag_adapter.py
uv run --frozen pytest -p no:cacheprovider tests/test_rag.py tests/test_rag_data_loader.py tests/test_dialogue_quality_metrics.py tests/test_rag_standard_metrics.py
uv run --frozen pytest -p no:cacheprovider tests/test_cost_analyzer.py tests/test_cooling_reminder.py tests/test_decision_score.py tests/test_mcp_tools.py tests/test_tools_router.py
uv run --frozen pytest -p no:cacheprovider tests/test_cases_router.py tests/test_chat_router.py tests/test_debate_router.py tests/test_history_router.py tests/test_watchlist_router.py tests/test_feedback_router.py tests/test_trace_route.py tests/test_health_route.py tests/test_migrate.py
uv run --frozen python -m compileall -q backend tests rag mcp_tools
git diff --check
```

`test_chat_router.py` 文件名保留，但新契约是 `/api/cases/{case_id}/messages`，不要求恢复旧 `/api/chat`。

## 3. 信息收集回归

| 场景 | 输入/操作 | 核心预期 |
|---|---|---|
| 最低字段 | 商品名、价格、剩余预算齐全 | 无冲突时 ready_for_debate；增强字段可仍缺失 |
| 邻接预算 | 想买降噪耳机，价格 1299 元，本月预算还剩 2000 元 | price=1299，budget=2000 |
| 语序/标点 | 预算在前、价格在后；不同分句标点 | 同一语义不互相覆盖 |
| 中文金额 | 预算大概还有三千左右；预算还剩两千五 | 预算3000/2500，不误识别为商品价格 |
| 价格补充 | 价格大概是2500元。 | price=2500 |
| 明确纠正 | 刚才价格说错了，不是2500，是2200。 | price=2200，既有预算不受影响 |
| 预算纠正 | 预算不是3000，是2500 | 更新预算，不生成错误price |
| 频率否定 | 我不是每天用，大概一周两次 | 不提取被否定的“每天” |
| 金额歧义 | 无上下文的多个金额 | 记录歧义/针对性追问，不强行当作确定价格和预算 |
| 模型非法数据 | 非对象/非法金额/不支持字段等 | 按当前校验契约拒绝并fallback |
| 累计状态 | 多轮分别给商品、价格、预算 | 检查 merged_fields，不只检查本轮 extracted_fields |
| 最低完成但有选填缺失 | 未填写用途/频率 | 不以 missing_fields 非空强行重开收集 |

parser 的元数据与用户对话上下文不等同于完整的跨轮记忆；本轮不验收“最多三轮保证退出”这一尚未实现的功能。

## 4. Agent、庭审与工具

- 完整 C 结果有4个 Agent steps 和4条庭审事件；speaker/order/phase 固定对应书记员、正方、反方、法官。
- `result.debate_events` 与 `report.debate_events` 一致；正反方内容包含各自摘要与论点，evidence 与真实上下文相符。
- 正反方没有交叉反驳/二次回应；模型请求次数和页面逐步播放不能据此误记。
- 法官规则产生 final_decision/confidence；LLM说明不得覆盖结论；远端失败或非法JSON时保留本地说明。
- C 不按高风险标记直接中断，但 B 风险拒绝分支不得进入正常庭审；分别验证 C 和 B，避免用旧C断言代替当前契约。
- 价格1299、预算2000：成本风险high；预算3000：占比约0.43、medium。检查成本结果不是展示文案随意编造。
- decision_score 输入 high/0.7/0.6/true 时计算为18、high，不是旧示例中的54。
- 评分工具失败应记录失败，不强制终止流程，也不伪造有效分数；法官不直接以评分替换规则结论。
- 提醒为条件步骤；trace 含评分后通常为7或8条，不固定七条。
- 提醒失败应保留“手动设置复盘提醒”等可行动提示；成功 metrics 含title/reason，但不等于数据库已写入。

## 5. RAG 验收

### 5.1 检索查询与指标

购物标准查询：“想买降噪耳机”“想买学习用品”；无命中查询选择种子中无相关内容的词，期望空数组。脚本中保留的“参加社团活动”“参加技术分享”是组件兼容样例，不属于本轮时间主流程验收。

```powershell
$env:RAG_LIVE_RECORDS = "0"
uv run --frozen python rag/evaluate_rag.py --out "$env:TEMP/decisionjury-rag-eval.json"
uv run --frozen python rag/evaluate_rag_standard.py --out "$env:TEMP/decisionjury-rag-standard.json"
```

记录数据集版本、query、top_k、相关集合定义、命中和分数。规则脚本的 faithfulness 是词项重合比例，answer_relevancy 是预设要点命中比例；不是人工语义忠实度，也不是模型准确率。

### 5.2 服务与数据流

1. 检索命中时，RAG证据进入正反方与法官上下文、报告与引用信息。
2. 正常无命中：空数组，rag_search trace为completed。
3. RAG断连/非法响应：空数组，trace为failed，后续Agent可继续。
4. 反馈成功写入历史后，下一次按用户拉取有机会检索到它；不保证每条复盘都命中。
5. 静态种子不能被表述为当前用户真实经历；实时用户过滤单独验证。

## 6. B 与页面验收

测试用户必须先经 `POST /auth/register` 创建，不能随便使用数据库不存在的 `user_id`。统一使用一个独立测试用户及新案件。

| 操作 | 检查点 |
|---|---|
| 创建/补充 | shopping、累计字段、reply、状态、消息持久化 |
| PATCH 与消息路径 | 分别记录完成条件；当前 PATCH 仍检查七项，不将它当作 parser 最低三项的等价路径 |
| GET messages | 必填user_id；items为id/session_id/role/type/content/created_at，分页与升序正确 |
| POST debate | 必填user_id，不匹配为FORBIDDEN；缺失字段返回非空data追问信息 |
| 成功庭审 | data.debate_events和data.report；刷新后GET report仍可回放 |
| GET trace | 单独查询轨迹，不从debate HTTP响应假设有trace |
| 提醒保存 | 检查提醒ID、case/user外键、title/reason、due_at、waiting状态 |
| 观察清单 | 只显示该用户waiting提醒；DELETE需user_id，缺参422、他人FORBIDDEN，成功取消后隐藏 |
| 反馈 | 历史新增、案件状态和关联提醒更新；随后验证RAG候选 |
| 历史 | result只接受worth/regret/neutral，非法值按校验返回 |
| 异常 | 无案件、无报告、拒绝状态、非法请求、网络失败有明确结果 |

两个购物手动案例见 [MVP §6](01_MVP.md#6-两个购物验收案例)。PR #89 已修复 /debate 的 `Reminder` 导入，上述存储和页面闭环仍需逐项验收。不要通过避开该分支宣布全流程通过。

注册登录不等于完整权限系统；当前尚无JWT/统一会话鉴权，生产安全不能勾选通过。

## 7. 真实 DeepSeek 验收

使用与日常数据分离的演示服务，加载测试人员授权的真实 Key；不得把明文写进日志、截图或提交。

- 确认实际模型与请求目的，依次记录parser、正方、反方、法官说明的成功/失败。
- 单独直连成功只能证明网络调用，不代表整个请求无fallback；应结合脱敏日志、受控探针或调用证据。
- 校验结构化JSON、口语输入、金额纠正、字段合并、规则判决不被模型覆盖。
- 在受控环境验证超时/断连/非法响应，恢复配置后重新验收。
- 记录调用耗时，但不把一次样例延迟或mock耗时作为稳定性能指标。

已有脚本 `rag/e2e_verify.py` 可作辅助，但默认用户必须先注册；脚本不是完整浏览器/提醒验收，本轮未复跑该实时脚本。Docker镜像不包含全部评测脚本，执行位置见 [部署文档](../deploy/DOCKER.md)。

## 8. 记录格式与发布门槛

每条验收记录包含：

```text
代码commit：
日期/验证人：
环境/数据库隔离方式：
模式：本地规则 / mock / 真实DeepSeek / 受控故障
命令或页面操作：
输入和预期：
实际结果（passed/failed/skipped）：
脱敏证据位置：
未完成项和负责人：
```

本次文档同步基线为 `53d70bc`，保留同步前 `a965900` 的测试记录供对比。旧文档的 `30 passed` 是早期C定向记录，缺少对应的完整当前基线证据，不再称为“当前测试结果”。D历史记录另见 [D进度](06_Role_D_RAG_Progress.md)。新的数字必须来自实际执行，不得根据测试文件数量推算。

发布前要求本轮购物关键路径通过、已知B阻塞关闭、真实API与降级分别验收、文档和PPT状态一致、至少一名组员review。不再要求时间主流程通过，也不因延期而删除现有组件测试。

## 9. 本轮实际验证记录

### 9.1 同步前基线 a965900

2026-09-09，AI 文档同步时执行；业务代码基线 `a96590045337b60352d03869135d868e69a3df8a`，工作分支 `feature/docs-shopping-scope` 仅有人读 Markdown 改动。环境为 Windows / Python 3.14.4 / pytest 9.1.1，使用§2的内存数据库、禁用 dotenv、无真实模型 Key 和关闭实时历史拉取配置。

| 实际命令/检查 | 结果 |
|---|---|
| `uv run --frozen pytest -p no:cacheprovider` | 收集到290项后因辅助脚本中断：1 error、1 warning，未执行测试正文 |
| `uv run --frozen pytest -p no:cacheprovider tests -q --tb=line` | 283 passed、7 failed、8 warnings，35.41秒 |
| `uv run --frozen python -m compileall -q backend tests rag mcp_tools` | 通过；编译检查不能发现运行时未导入的名称 |
| `git diff --check` | 通过；仅Git换行转换提示，无空白错误 |
| 文档结构检查 | 12份UTF-8文档、18段JSON示例、45个本地链接及其标题锚点检查通过 |

失败明细：

- `tests/test_debate_router.py::test_debate_success`、`test_debate_response_contains_trace`：当时调用 `Reminder(...)` 时 `NameError`；后续PR #89已修复，最新结果见§9.2。
- `tests/test_migrate.py::test_get_existing_columns`：查询结果为空集合。`test_migrate_cases / test_migrate_histories / test_migrate_traces / test_migrate_reminders`：对应表不存在。这些用例在 fixture 引擎建表，但被测函数使用 `backend.migrate.engine`，没有切换到 fixture 引擎；需要 B/测试完善隔离，不能据此判定真实部署迁移必然失败或已经通过。
- 根目录收集错误来自 `backend/test/test_feedback_quick.py` 对空数据库的导入期查询。建议由 B/测试改为显式运行的辅助入口或真正的隔离用例，本次不修改它。

8条 warning 来自既有 Pydantic class Config 和 Starlette 422 常量弃用提示。C 的 parser、LLM、judge、Agent flow、RAG/MCP adapter 测试文件在本次 `tests/` 执行中均通过，属于本地/mock/受控响应验证。未执行真实 DeepSeek、浏览器全流程、Docker 构建或线上部署验收，也未改动业务代码来绕过失败。

### 9.2 同步 PR #88、#89 后基线 53d70bc

同日推送前拉取远端并快进到 `53d70bc9324f043986c7f104d65c66953ad03025`，保持上述隔离环境。本次功能分支相对该基线仍只改12份Markdown文档。

执行 `uv run --frozen pytest tests -p no:cacheprovider -q --tb=line --show-capture=no`：**292 passed、5 failed、10 warnings，35.79秒**。

- 所有辩论路由测试通过；新增GET messages测试也通过。原有两个Reminder导入错误已消失，不再作为当前待修复项。
- 5个失败仍为§9.1所列迁移测试，fixture与被测函数引擎不一致的问题尚未修复。
- 10条warning仍为Pydantic Config与Starlette 422常量弃用提示。
- 根目录辅助脚本未变；本次复跑显式限定tests目录，没有重新运行根目录收集。
- 观察清单删除新增user_id校验、parser元数据接入与报告损坏分支按代码同步文档；不以本次现有用例通过宣称这些新增边界全部有专项测试。
- 未运行真实模型、浏览器或部署验收；本次不修改测试或业务代码以绕过遗留失败。

### 9.4 判决规则 v2 修复（字段归一化 + 决策表 + 证据相关性）

2026-09-10，工作区分支 `feature/docs-shopping-scope`，基线 `2c68835`（与 `origin/dev@9c907ca` 的判决代码相同：`judge_agent.py` 两版一致）。环境为 Windows / Python 3.14.4 / pytest 9.1.1，沿用§2的内存数据库、禁用 dotenv、无真实模型 Key、关闭实时历史拉取。

改动内容：

- 新增 `backend/app/agents/field_normalizer.py`：频率 / 触发原因 / 替代品三类自由文本归一到受控值，并提供证据相关性判定；判决与 `decision_score` 共用同一份实现。
- 重写 `backend/app/agents/judge_agent.py` 的判定：`H1` 高风险 reject、`H2` 占比≤1% 且 low 小额短路 buy、`R1` 成本 medium / 冲动触发 / 相关风险证据 delay、`R2` 替代品明确覆盖核心需求 alternative、`R3` 高频且评分≥45 buy、`R4` 仅提到替代品 alternative、`R5` 频率未知但低风险 buy、`R6` 兜底 delay；成本工具失败时不放行。报告新增 `decision_basis` 与 `decision_strength`。
- `backend/app/services/mcp_adapter.py`：`usage_value` / `impulse_trigger` / `history_risk` 改用归一字段与相关证据。
- 前端判决书新增「判决依据」区块，`confidence` 文案改为「证据置信度」并显示结论强度。
- 新增 `tests/test_judge_rules.py`（16 条）；`tests/test_judge_agent.py` 的风险证据用例改为相关证据（原用例使用无关证据，正是被修掉的行为）。

执行与结果：

```text
uv run --frozen pytest tests -p no:cacheprovider -q --tb=line --show-capture=no
=> 307 passed, 5 failed, 10 warnings（5 个失败仍为 §9.1/§9.2 所列迁移测试隔离问题，与本改动无关）

uv run --frozen pytest tests/test_judge_rules.py tests/test_judge_agent.py tests/test_mcp_adapter.py \
    tests/test_decision_score.py tests/test_agent_flow.py -q
=> 67 passed

npm --prefix frontend run build
=> tsc -b && vite build 通过（291.45 kB / gzip 98.01 kB）
```

已修掉的反例（均写入 `tests/test_judge_rules.py`）：`每天使用`/`日常使用` 不再落到 `每天` 之外；`暂无/没有其他水果/无其他替代品` 不再被当成“有替代品”；`朋友推荐/社交影响` 与促销同样进入冷静期；4 元级消费不再判暂缓；无关历史证据（围巾/投影仪）不再一票打成 delay；成本工具失败时不放行。

### 9.5 解析完整性、追问与评分口径修复（C 模块三条反馈）

2026-09-10 追加，同一环境与基线。改动内容：

- `backend/app/agents/input_parser.py`：
  - `_extract_price` 新增“动词在金额之后”（`花4元买`）与“同句已识别预算时另一金额为价格”（`预算 3000 元，芒果 4 元`）两类句式；无预算时保留金额歧义判定，不猜价格。
  - `_extract_product` 新增对应的“金额+买/入手+商品名”与“`<商品> N 元`”兜底（跳过预算金额与预算上下文）。
  - 新增 `ENHANCED_FIELDS` / `_enhanced_question`：核心三字段齐全但增强字段缺失时，`next_question` 返回“（可选）补充一句可以让判断更准：…”，不再返回 None；本地路径与 LLM 路径口径一致。
- `backend/routers/chat.py`：`ready_for_debate` 状态的回复拼接 C 的可选追问，页面不再只有一句泛泛的“可以分析”。
- `backend/app/services/llm_client.py`：新增 `_coerce_amount` 宽松解析（`5元/斤`→5、`约1000元`→1000、`¥1,299`→1299、`一千二`→1200），并把金额非法从“整轮 raise → 静默降级到本地正则”改为**字段级降级**（只丢该字段）；原始写法记入 `field_meta.raw_text`；结构类违规（未知字段/未知顶层键/非法 confidence）仍然拒绝。
- `backend/app/services/mcp_adapter.py`：用途与频率都未知时 `usage_value` 由 0.3（等于扣 8 分）改为中性 0.5，避免“没填字段”被当成“使用价值低”。
- 新增 `tests/test_parser_and_followup.py`（14 条）；`tests/test_llm_client.py` 的金额用例改为断言字段级降级。

执行与结果：

```text
uv run --frozen pytest tests -p no:cacheprovider -q --tb=line --show-capture=no
=> 321 passed, 5 failed（仍是 §9.1/§9.2 的迁移测试隔离问题）
```

真实 DeepSeek 端到端复验（独立库 + 未占用端口，最后清理）：

| 场景 | 结果 |
|---|---|
| 建案 `预算 3000 元，芒果 4 元` | `merged={product_name:芒果, price:4, monthly_budget_left:3000}`，`missing` 不再含商品名/价格 |
| `我想买芒果 → 花4元买 → 想补充营养，没有其他水果` | 第三轮 `missing=['expected_usage_frequency','trigger_reason']`（与反馈中的期望一致），每轮 `next_question` 均非空且为具体问题 |
| `水果价格是5元一斤，我的预算是2000元` | `_parser_used=deepseek`（不再静默降级）、`price=5.0`、`budget=2000`、`product=水果` |
| 6 元苹果 / 预算 400 | `buy`（`H2`） |
| 30 元香蕉 / 预算 100 / “没有其他水果” | `delay`（`R1`，成本 medium） |
| 1000 元智能手表 / 预算 29000 / “没有手表” / 每天用 | `buy`（`R3`） |

已知限制：`5元/斤` 只保留数值 5，单价与总价尚未区分（原始写法存在 `field_meta.raw_text`，B 的建案路径当前只持久化 `merged_fields`，未落 `field_meta`）。

### 9.6 收集阶段对话体验（承接 + 一次一问 + 跳过 + 熔断）

2026-09-10 追加，同一环境与基线。改动内容：

- 新增 `backend/app/agents/reply_composer.py`：把字段状态翻译成 `reply_plan`（`ack` 承接句、`question` 一个问题、`chips` 快捷选项、`can_stop/optional`、`reply` 成品文案、`progress`），并集中管理文案表、跳过信号、可选追问上限（2 轮）。
- `input_parser.parse_input` 末尾新增 `_finalize()`：处理“跳过”（增强字段记 `未说明` 并移出 `missing_fields`；核心字段不允许跳过，改为“给个范围也行”）、`_optional_asked` 计数熔断，并生成 `reply_plan`；本地规则路径与模型路径表现一致。
- 追问文案全部口语化：`为了进入购物法庭分析，还需要补充：…` → `这个大概多少钱？` / `大概多久会用一次？`；核心信息齐后为 `想更准的话，再补一句：…`。
- `routers/chat.py` 与 `routers/cases.py` 透出 `reply_plan`；B 优先使用 C 的成品文案，原兜底文案仅在没有 `reply_plan` 时使用。
- 前端 `ChatPage.tsx`：渲染快捷选项（点击即发送）、`can_stop` 时提示“信息已够，可以直接出判决书”、进度面板区分“待补充/建议补充”；并修正输入框锁定条件——只有七项全齐才锁，核心信息齐了仍可继续补充或纠正（旧逻辑在 ready 状态直接禁用输入）。
- 新增 `tests/test_reply_composer.py`（14 条）；`tests/test_parser_and_followup.py`、`tests/test_input_parser.py` 的追问文案断言同步更新。

执行与结果：

```text
uv run --frozen pytest tests -p no:cacheprovider -q --tb=line --show-capture=no
=> 335 passed, 5 failed（仍是 §9.1/§9.2 的迁移测试隔离问题）

npm --prefix frontend run build
=> tsc -b && vite build 通过
```

真实 DeepSeek 多轮复验（独立库与端口，最后清理）：

```text
建案 键盘30元，预算5000元
  助手：记下了：商品是键盘、价格 30 元、预算还剩 5000 元。 想更准的话，再补一句：主要拿来做什么用？
  快捷：['工作/学习用','家用','娱乐','说不清']  can_stop=true
用户：日常工作用，公司那把太旧了
  助手：记下了：用途：日常工作、购买原因：公司那把太旧了。 想更准的话，再补一句：你手上已经有能替代它的东西吗？
用户：差不多每天都用
  助手：记下了：使用频率：差不多每天。 核心信息够了，随时可以出判决书；也可以再补一两句让它更准。
用户：不知道            （可选追问已达 2 轮，进入熔断；该字段按跳过处理）
  助手：记下了：已有替代品：先跳过。 行，这项先跳过。 核心信息够了，随时可以出判决书；也可以再补一两句让它更准。
```

未覆盖：SSE 流式输出、意图分流（反问/闲聊）、服务端消息作为前端唯一来源（前端仍读 localStorage 缓存）。

### 9.7 自然对话化：模型写文案 + 本地护栏（2026-09-10）

2026-09-10 追加，同一环境与基线。改动内容：

- `llm_client`：`input_parser` 提示词重写为"购物参谋"角色，要求额外输出 `dialogue{ack,insight,question,chips,answer_to_user,intent}`；调用时附带 `recent_turns / last_question / already_asked_fields`；新增 `_sanitize_dialogue` 校验裁剪；结构校验放宽为"必需键齐全即通过"（未知顶层键忽略、未知字段丢弃并记入 `field_meta.dropped`）。
- `input_parser`：解析失败**重试一次**；`_finalize` 传入对话上下文与纠错信息，生成含模型文案的 `reply_plan`，并记录 `_last_question / _asked_fields`；`reply_plan` 增加 `degraded / degraded_reason / parser_used / stop_requested`。
- `reply_composer`：新增 `_apply_model_dialogue` 护栏（只保留第一个问句、复读检测、系统口吻黑名单、矛盾回显"xx已改成…"）；`is_stop_signal` + `stop_requested`。
- `routers/chat.py`：取最近 6 条消息作为 `recent_turns`。
- 前端：快捷选项按钮、`stop_requested` 自动进入辩论、降级提示条、输入框锁定条件修正（仅七项全齐才锁）。

执行与结果：

```text
uv run --frozen pytest tests -p no:cacheprovider -q --tb=line --show-capture=no
=> 336 passed, 5 failed（仍是 §9.1/§9.2 的迁移测试隔离问题）

npm --prefix frontend run build  => 通过
```

真实 DeepSeek 七轮剧本（含多字段一句话、反问、纠正、跳过、喊停，独立库与端口，最后清理）：

```text
用户：想买个键盘，公司那把太旧了
助手：明白，公司那把键盘太旧，你想换个新的。 办公用键盘建议优先看手感静音和耐用度，别只看价格。 这次买键盘大概想花多少钱？
      intent=provide_info chips=['100元以内','100-300元','300-600元']
用户：300 左右吧，预算这个月还剩 5000
助手：键盘 300 左右，本月还剩 5000，明白。 这个价位办公键盘选择挺多，建议优先看手感。 买来主要放公司办公用吗？
用户：其实我每天都要敲好几个小时代码
助手：明白，你是每天敲几小时代码的重度使用者 长时间打字建议优先看手感，轴体和腕托比灯效更值得花钱。 你手头除了公司那把旧键盘，还有别的键盘能用吗？
用户：那我买机械的还是静音的？
助手：你在纠结机械还是静音键盘。 静音轴适合办公，机械手感更好。 如果办公室环境安静，选静音轴；追求手感选机械轴。 你更看重手感还是安静？
      intent=ask_back（先回答用户的问题，再问自己的）
用户：不是 300，是 500
助手：价格已改成 500 元。 明白，价格是 500 不是 300，已经改成 500 了。 你们办公室环境安静吗？
      intent=correct
用户：不知道
助手：没关系，办公室安不安静可以先不纠结。 拿不准就选静音轴，安静和手感基本能兼顾，也不容易吵到同事。 你手头除了公司那把旧键盘，还有别的键盘能顶一阵吗？
      intent=skip（跳过该项且不复读原问题）
用户：够了吧，直接分析
助手：好的，我这就整理分析。 信息已够，我直接出建议。
      intent=stop, stop_requested=true（前端自动进入辩论）
```

未覆盖：SSE 流式输出（承接句已本地瞬时生成，模型段落仍是整段返回）、多模态、跨案件长期记忆。

### 9.8 模型与思考模式配置（依据 DeepSeek 官方文档实测，2026-09-10）

官方文档要点（[思考模式](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/)、[模型 & 价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing)）：

- 思考模式**默认开启**且 effort 默认 `high`；关闭方式 `{"thinking": {"type": "disabled"}}`；
- 思考模式**不支持** `temperature`（设置不报错但不生效），`top_p` 下限被抬到 0.95；
- 思考链通过 `reasoning_content` 返回，**token 计入输出额度**；
- 在售模型为 `deepseek-flash`（V4.1-Flash）与 `deepseek-v4-pro`；**`deepseek-v4-flash` 已是下线旧名**，请求会被路由到 V4.1-Flash。

独立实测（`deepseek-flash`，同一提示词与输入，各 4 次）：

| 配置 | 平均延迟 | JSON 合法 | 说明 |
|---|---|---|---|
| `thinking: disabled` | **1.52s**（1.34~1.87s） | **4/4** | 输出约 140~170 tokens |
| `reasoning_effort: low`（思考仍开启，即改动前行为） | 3.96s | 0/4（受 max_tokens=800 限制被截断） | 思维链占满输出额度 |
| `reasoning_effort: max` | 4.46s | 0/2（同上受额度限制） | 需配合放大 `max_tokens` |
| 流式 + 关思考 | 首字 **1.02s** / 总 1.60s，185 chunk | — | chunk 自带 `usage`，无需 `stream_options` |

改动内容：

- `DEEPSEEK_MODEL` 默认改为官方在售的 `deepseek-flash`，可用环境变量覆盖；构造参数不再硬编码模型名。
- 任务分组：`COLLECTION_TASKS = {input_parser}` → **关闭思考**（并让 `temperature` 真正生效）；`DEBATE_TASKS = {pro_agent, con_agent, judge_agent}` → 开启思考，`reasoning_effort` 默认 **max**，并显式放大 `max_tokens`（默认 8192）。
- 辩论阶段单次调用可能超过 30 秒，超时放宽为 120 秒（`DEEPSEEK_DEBATE_TIMEOUT_SECONDS`）。
- 新增/更新测试：`test_input_parser_request_disables_thinking`、`test_debate_request_uses_max_reasoning_effort`，并同步模型名断言。

端到端复验（真实 API，独立库与端口，最后清理）：

```text
[收集] 建案解析 1.91s；后续两轮 1.46s / 1.50s，degraded=False，parser_used=deepseek
       示例："懂了，写代码天天用，那手感确实关键 每天长时间敲代码，轴体和键位布局比外观更值得挑 现在手头有在用的键盘吗？"
[判决] 启动辩论（reasoning_effort=max）总耗时 29.60s，success=True
       final_decision=delay，结论强度 0.8，依据 [E0, R1, E1]
=> 307+30 passed / 5 failed（迁移测试隔离问题，同 §9.1）
```

可选环境变量：`DEEPSEEK_MODEL`、`DEEPSEEK_REASONING_EFFORT`（minimal/low/medium/high/xhigh/max/ultra，默认 max）、`DEEPSEEK_DEBATE_TIMEOUT_SECONDS`（默认 120）、`DEEPSEEK_MAX_TOKENS`（默认 8192）、`DEEPSEEK_TIMEOUT_SECONDS`（收集阶段，默认 30）。

### 9.9 辩论阶段进度推送（SSE）

收集阶段关思考后单轮已降到 1.4–1.9 秒，**流式的边际收益很小，因此不做 token 流式**；真正的等待黑洞是辩论阶段（开启 max 思考后实测 26–30 秒整段返回，前端只有一句"分析中…"）。

改动内容：

- `orchestrator/decision_flow.run_decision_flow` 新增可选 `progress` 回调，在 解析 / RAG / 工具 / 正方 / 反方 / 法官 六个阶段边界推送 `{stage, status, summary, arguments?}`；`adapter.run_case_decision_flow` 透传。
- `routers/debate.py`：把辩论执行与落库抽成 `_run_debate_core(db, case, case_id, progress)`，`POST /debate` 行为不变；新增 `POST /api/cases/{case_id}/debate/stream`（`text/event-stream`），在工作线程内用独立 Session 执行核心流程，通过队列把事件推给 SSE 生成器，结束推 `__done__`（含完整响应）或 `__error__`。
- 前端 `api.startDebateStream()`：`fetch` + `ReadableStream` 解析 SSE；`ChatPage` 在等待期间渲染"确认材料 → 检索历史复盘 → 成本与评分 → 正方发言 → 反方发言 → 法官评议"的实时进度，正方/反方一完成即显示其论点摘要。

真实复验（`POST /api/cases/case_aa9765d4/debate/stream`，真实 API + max 思考）：

```text
content-type: text/event-stream; charset=utf-8
[  0.0s] parse        running
[  1.4s] parse        done     已确认可以进入分析
[  1.4s] rag          running  检索历史复盘证据
[  2.5s] tools        done     该商品占剩余预算约 25%，风险等级为 medium。
[  2.5s] pro_agent    running  正方 Agent 正在组织支持购买的理由
[  9.8s] pro_agent    done     从支持购买的角度看，500 元机械键盘属于预算内、高频使用…
[  9.8s] con_agent    running  反方 Agent 正在评估风险与替代方案
[ 18.2s] con_agent    done     该机械键盘售价 500 元，占剩余预算 25%…
[ 18.2s] judge_agent  running  法官正在依据规则结论撰写判决说明
[ 26.4s] judge_agent  done     本案对机械键盘的辅助建议是：建议暂缓购买 3 天后复盘。
[ 26.5s] __done__  success=True
```

```text
uv run --frozen pytest tests -q  => 337 passed, 5 failed（迁移测试隔离问题）
npm --prefix frontend run build   => 通过
```

未覆盖：SSE 断线重连（当前断线即中断，需重新点"启动辩论分析"）；事件未持久化（trace 表在流程结束时一次性写入，进度事件只走内存队列）。

### 9.10 报告可复算、论点去注水、记忆以服务端为准（批量修复）

2026-09-10 追加，同一环境与基线。改动内容：

- **报告可复算**：`DecisionReport` 新增 `rule_version`（当前 `judge-rules-v2`）与 `input_snapshot`（归一化后的判定输入：频率/触发/替代品/成本占比/风险/评分/证据条数），事后可复算"当时按哪版规则、用什么输入判的"。
- **正方/反方论点去注水**：`con_agent` 不再把 `cost_analyzer` 的 summary 原文塞进 `arguments`（此前报告里会出现"该商品占剩余预算约 25%，风险等级为 medium。"这类工具句），改为仅在成本工具失败时提示人工核对；风险证据引用改为可读句。
- **替代品等效判断落地**：解析提示词要求模型在 `field_meta.owned_alternatives.covers_core_need` 给出 true/false/null，`input_parser` 并入 `alternative_covers_need`，判决 `R2`（明确覆盖核心需求 → alternative）由此真正可用；提示词同时补充"否定与条件句按语义处理（我不是每天用/暂时不买/如果降价再买）"。
- **记忆以服务端为准**：前端 `getCaseMessages` 改为读取 `GET /api/cases/{id}/messages`（映射 id/session_id/role/content/created_at），本地缓存降级为渲染缓存与离线兜底 —— 换设备、清缓存后对话可恢复。

执行与结果：

```text
uv run --frozen pytest tests -q  => 337 passed, 5 failed（迁移测试隔离问题，同 §9.1）
npm --prefix frontend run build   => 通过（tsc -b && vite build）
```

仍未解决（如实记录）：① 没有黄金对话集与质量指标，"当前准确率"仍无数字；② 字段 schema 仍为 7 个扁平字段，单价/数量/单位语义缺失（`5元/斤` 只存数值）；③ 金额歧义仅覆盖"既无预算又无价格"；④ RAG 仍为 BM25 词面检索；⑤ 观察清单 `reviewed` 分支不可达；⑥ 规则升级前的旧报告无 `decision_basis`，无法回填。

### 9.11 黄金剧本集与真实 API 复验（2026-09-10）

新增 `tests/test_golden_dialogues.py`（15 条剧本），把收集与判决的关键路径固化为断言：一句话多字段、缺失项单调收敛、跳过/拒绝跳过核心字段、纠正回显、带单位金额、追问熔断、小额短路、替代品语义、冲动触发、无关证据、成本工具失败、单价不放行、报告可复算与论点清洁、"无系统腔 + 一次只问一个"。首次运行即抓出 2 个真 bug（纠正回显只在模型路径生效；`<商品>价格是N元` 抓不到商品名），并在此后抓出 3 个自伤回归（LLM 路径引用未定义变量导致整轮回落、单位正则不认"5元一斤"、只给 H2 加单价护栏漏了 R5）。

**真实 API 复验**（`deepseek-flash`，收集阶段关思考；独立库与端口，最后清理）：

| 验收项 | 结果 |
|---|---|
| 单价 / 数量语义 | `水果5元一斤，我想买10斤，预算还剩2000元` → `price=5.0, price_is_unit=True, price_unit=斤, quantity=10`，2.06s；判决 `delay`，依据 `[E2, R6]`，`price_basis=unit_price_x_quantity`（单价不再被当成总价走小额放行） |
| 替代品等效判断 | `想买降噪耳机…已经有普通耳机了` → `alternative_covers_need=False`（R2/R4 依据真实语义生效）；该字段需同时写进系统提示与 `required_output` 才会被模型遵守——只写系统提示时实测返回 null |
| 否定表达 | `我不是每天用，只是偶尔` → 存储 `偶尔使用`，归一为 `occasional`；判决依据 `[R1]` 而非高频放行（此前 `不是每天用` 会被"每天"两字误判为 daily） |
| 条件表达 | `暂时不买，先看看` → trigger 保持空，回复按"先了解不必下单"处理，未当成肯定购买意图 |
| 服务端记忆 | `GET /api/cases/{id}/messages` 返回完整 4 条对话（用户 2 + 助手 2），前端已切换为该来源 |

```text
uv run --frozen pytest tests -q  => 353 passed, 5 failed（仍为迁移测试隔离问题）
```

仍未解决：① 无质量指标（黄金集是行为断言，不是准确率统计）；② 金额歧义仅覆盖"既无预算又无价格"；③ RAG 仍为 BM25 词面检索；④ 观察清单 `reviewed` 分支不可达；⑤ 规则升级前的旧报告无 `decision_basis`；⑥ 降级率未做长跑统计；⑦ SSE 断线不重连。

未覆盖：真实 DeepSeek 下的端到端复验、Docker/部署演练；旧报告没有 `decision_basis`，页面显示“该报告生成于规则升级之前”。

### 9.12 用户视图边界、历史文本权威性与降级可观测（2026-09-11）

三轮真实 API 复验（每轮 5~7 个全新案例；独立 SQLite 库与端口：backend 8010 + RAG retriever 8011；
`deepseek-flash`，收集阶段关思考、辩论阶段 `reasoning_effort=max`）。

**第一轮：边界中间件把机器契约也改了（10 个用例失败 → 修复）**

响应出口的"唯一清洗关卡"最初对**所有** JSON 做子串替换，导致 `tool_name="decision_score"` 变成"决策评分"、
`missing_fields=["monthly_budget_left"]` 变成"本月剩余预算"、`steps[].agent="pro_agent"` 变成"正方"、
`/api/tools/*` 调试契约被改写；`public_report` 还删掉了 `tool_name`，而前端
`VerdictPage.tsx` / `TraceLogView.tsx` / `constants.ts` 正是按英文 id 渲染与查表（判决书页工具名会渲染成空）。
修复：路径白名单（只有 `/api/cases*`、`/api/history*`、`/api/watchlist*` 走清洗，`/api/tools/*` 等调试面原样返回）
+ 标识符守卫（整体是 `daily`、`pro_agent`、`buy` 这类受控取值一律不改写）
+ 契约字段保留、中文名以 `tool_label`、`used_tool_labels` **并行新增**。
规则固化在 `tests/test_user_facing_boundary.py`（35 例，含"每条路由必须显式归类"）。

**第二轮：判决用了纠正前的数量（真 bug）**

"猫砂，一袋25，想买4袋…" 加后续 "不是4袋，是2袋"：字段已是 `quantity=2`，但判决按 4 袋算成 100 元/11%，
正确应为 50 元/5.6%。根因：判决阶段重放案件**首条描述**，而合并语义是"新文本覆盖旧值"，旧数字把用户纠正盖回去了。
修复：`parse_input(existing_is_authoritative=True)`（判决路径专用：已收集字段优先、只补缺口；普通对话轮语义不变），
回归用例 `tests/test_parser_and_followup.py::test_debate_replay_keeps_corrected_quantity`。

**第三轮：5 个新案例（含口语化与中文数字），抓出两个判决书缺陷**

| 案例 | 字段结果 | 判决 | 依据 |
|---|---|---|---|
| 二手相机 6000 / 预算 3000 | price 6000、budget 3000 | reject | H1（200%） |
| 空气炸锅（口语"三百五""一千五"） | price 350、budget 1500、频率 weekly_1_2 | delay | R1 |
| 换电饭煲 299 / 1200（旧锅还能用） | price 299、covers=true | delay | R1 |
| 猫粮 一袋80 想买3袋 → 纠正 2袋 | price 80、quantity **2**、占比 **0.16** | buy | R5 |
| 囤纸巾 199 / 900（促销 + 已有半箱） | price 199、quantity 2.0、covers=true | delay | R1 |

抓出的两个真缺陷（均已修复并加回归）：

1. **静默降级冒充模型观点**：`DeepSeekLLMClient.complete_json` 捕获所有异常后无声返回 mock 文案，
   前一轮 5 案中 3 案的某一方论点是 `MockLLMClient` 模板句（"预期使用频率为有一定频率，可能支撑长期价值"），
   且 `error=None`——判决书把模板句当成正方/反方的真实观点。修复：失败重试一次 → 记 warning →
   返回体带 `_degraded_reason`；pro/con 改为 `status="failed"`、`error="llm_degraded:…"`、`arguments=[]`（不再用模板填空）；
   法官说明降级时退回本地规则文案并在 `steps[].error` 标记。修复后同一批案例：**0 降级**，双方论点 6~10 条。
2. **凭"原始描述"造出的数量矛盾**：判决书写出"结构化字段记录为2袋，但原始描述是想买3袋…成本风险被低估"，
   矛盾是喂进去的（模型同时看到原话与纠正后的字段）。修复：辩论/判决上下文把原话标注为
   "原始描述（用户最先说的话，可能已被后续对话更正；数值以以上字段为准）" + 系统提示声明字段权威性；
   修复后同一案例判决书不再出现"矛盾""3袋"。

另有 1 处流程问题定点修复：纠正类发言后模型给同一问题加了衔接词又问一遍
（"这次是…呀？" → "那这次是…呀？"），逐字符比较判不出复读。
修复：`_normalize_for_compare` 剥掉句首衔接词（那/那么/然后/所以…），真实 API 复验确认改问另一个待补字段。

```text
uv run --frozen pytest tests -q                                  => 443 passed
uv run --frozen pytest tests/test_metamorphic.py tests/test_golden_dialogues.py \
    tests/test_semantic_facts.py tests/test_quality_gate.py \
    tests/test_user_facing_boundary.py -q                        => 90 passed
```

**第四轮：R2 优先级修正（2026-09-11 追加，用户确认后实施）**

① 决策表把 `R2`（已有替代品明确覆盖核心需求 → alternative）上移到 `R1`（中等成本风险/冲动/历史风险）
之前：已有物品确实能用时，"不需要重复买"比"预算有压力，先冷静"更强也更可行动。
实施中发现并处理了两件事：

- **`E6` 是 fall-through，不是 return**（原先的"高风险不受影响"假设不成立）：把 `R2` 上移后，
  "高额刚需 + 替代品可覆盖"会从 `E6 + R3`（buy）变成 `alternative`。这超出本次批准范围，且
  `covers_core_need` 是模型判断字段（实测有波动），因此给 `R2` 加了 `risk_level != "high"` 边界，
  高风险档行为完全保持原样（用例 `test_high_risk_path_still_wins_over_covering_alternative`）。
- **规则改了但真实跑仍不生效**：定点复验（299 元电饭煲 / 1200，"旧的没坏，就是想换个新的"）
  第一次仍是 `delay`，原因是模型把 `alternative_covers_need` 判成 **false**——`R2` 根本没机会命中。
  根因是提示词口径模糊（"能否覆盖核心需求"没说清是**功能**覆盖还是**用户意愿**）。
  补齐口径（"还能用/没坏/洗洗能用 → true；坏了/开胶/鼓包/失效 → false；只说有旧物 → null；
  不得把'想换新'当作覆盖不了的理由"）后重跑：

| 复验案例（真实 API） | `covers_core_need` | 判决 | 判定依据 |
|---|---|---|---|
| 旧的没坏，就是想换个新的 | **true** | **alternative** | **R2**（依据只写替代品，不再自相矛盾） |
| 旧的坏了不能用了 | false | delay | R1（中等成本风险） |
| 只提到旧物、能否使用未知 | null | delay | R1（后续动作仍提示"比较已有替代品"，即 R4 的提醒职责） |

刻意的不对称：**确认能覆盖**的替代品（R2）优先于中等成本风险；**仅提到、未知**（R4）不优先
（用例 `test_unconfirmed_alternative_still_waits_for_budget_pressure`）。

```text
uv run --frozen pytest tests -q                                  => 449 passed
uv run --frozen pytest tests/test_metamorphic.py tests/test_golden_dialogues.py \
    tests/test_semantic_facts.py tests/test_quality_gate.py \
    tests/test_user_facing_boundary.py -q                        => 90 passed
```

仍未解决（需产品口径，非机械缺陷）：
① R5 会把 16% 的低风险消费放行成 `buy`，而评分工具自身建议"暂缓"，判决书里同时出现两种口径；
② `covers_core_need` 的判定口径已写清并复验通过，但仍是模型判断——要不要再加一条确定性本地规则
（出现"还能用/没坏"且无"坏了/开胶/鼓包"等失效词时强制 true）尚未决定；
③ **消耗品囤货的口径变化（R2 优先级修正的连带影响，已实测）**：`囤纸巾（双十一预售，199/900，家里还有半箱）`
由 `delay（R1）` 变为 **`alternative（R2）`**，判定依据写作"已有替代品明确可以覆盖核心需求，无需重复购买"。
两种口径都说得通（判决书正文原本就在讲"需求已被现有存货覆盖"），但"半箱纸巾"是否算"覆盖核心需求"
属于产品判断：若希望囤货类仍走"促销冲动→冷静期"的叙事，需要把提示词口径补成
"消耗品的'还有存货'不等于覆盖核心需求（除非存货足以撑到下次合理采购周期）"。

### 9.13 第四轮真实复验：5 案覆盖 5 条规则，逐份读完整判决书（2026-09-11）

5 个全新案例、真实 API（backend 8010 + RAG 8011，独立 SQLite），刻意让它们落在不同规则路径上，
四种判决值全覆盖：`reject(H1)` / `buy(H2)` / `buy(R3)` / `alternative(R2)` / `buy(R5)`。

| 案例（口语化输入） | 关键字段 | 判决 | 依据 | 占比 |
|---|---|---|---|---|
| 冰箱彻底坏了，得赶紧换一台，3500，我这月就剩 2000 | price 3500、budget 2000、动机 need、频率 daily | reject | H1 | 175% |
| 刷短视频看到个 **9块9** 的手机支架，预算还剩 800 | price **9.9**、动机 promotion | buy | H2 | 1.2% |
| 咖啡豆，一包 120，想买两包，预算还剩 3000 | price 120（单价/包）、quantity 2 → 合计 240 | buy | R3 | 8% |
| 想买个新吸尘器，家里那个还能用就是有点旧，899，预算还剩 2500 | price 899、`covers_core_need=true` | alternative | R2 | 36% |
| 洗衣液，一桶 45，想买 4 桶…**不对，是 2 桶**，预算还剩 600 | price 45（单价/桶）、quantity **2** → 90 | buy | R5 | 15% |

三个检查项结果：① 流程无降级（`_parser_used=deepseek` ×5）、无内部键外泄、无追问复读；
② 字段全对（口语"9块9"→9.9、单价×数量、纠正后的数量进入判决快照 `数量=2`）；
③ 5 份完整判决书逐份读过，**在摘要里抓到一处系统性缺陷**（见下）。

**本轮抓到的缺陷（只有读完整判决书才会发现，判决结果本身全对）**

1. **摘要金额张冠李戴**（`_build_case_summary`）：总价口径写成"**预算**约 9.9 元"（预算是另一个字段 800），
   单价口径把"单价×数量"的**合计**写成"**单价**约 90 元"（单价是 45/桶）。
   这是用户读到的第一句话，前几轮一直存在，因为只核对"判决对不对"而漏掉。
   修复：总价 → "价格约 X 元"；单价 → "单价约 45 元/桶，共 2 桶（合计约 90 元）"；
   单价无数量 → "单价约 5 元/斤（数量未确认，总价待定）"。
   回归用例 `tests/test_quality_gate.py` 新增 3 条（指标 4）。
2. **内部主键泄漏到法官说明**：出现"已成功创建 3 天冷静期提醒（r_18b73537）"。
   修复：`sanitize_user_text` 剥掉文案里的 `r_/case_/report_/event_/msg_/trace_ + hex` 主键
   （括号形式连括号一起去掉；整体就是该 id 的**取值**由标识符守卫保护，不受影响）。
   回归用例 `::test_internal_ids_are_stripped_from_prose`。

**观察项（判定为合理行为，未改）**：当某一轮用户只做纠正、没有回答上一个问题时，
系统会**换一种措辞把同一个问题再问一遍**（本轮：手机支架的"放哪儿用"问了两次、洗衣液的"有没有替代品"问了两次）。
问题确实尚未回答，丢问会让案件卡住，且措辞已随上下文调整；`reply_composer` 的复读防护是逐字符归一化比较，
只能拦住字面复读，拦不住改写式重问——这是刻意的下限保护，不是漏网。

```text
uv run --frozen pytest tests -q                                  => 453 passed
uv run --frozen pytest tests/test_metamorphic.py tests/test_golden_dialogues.py \
    tests/test_semantic_facts.py tests/test_quality_gate.py \
    tests/test_user_facing_boundary.py -q                        => 94 passed
```

复验产物：`%TEMP%\dj-fix\round4b_verdicts.md`（5 份完整判决书原文）、`run5b.py`（可重跑脚本）。

### 9.14 用户实测 bug 修复：判决书"出不来" + unknown 抹掉明确频率（2026-09-11）

**用户实测报告**：对话页点「启动辩论分析」后一直提示无法生成判决书，反复点击无效。
（案例 `case_d4ee4fb0`，筋膜枪 200 元 / 预算 200 / 已有泡沫轴 / 原话"一周三次"）

**定位**：后端其实成功了——库里 `status=completed`、`final_decision=reject`、报告 7.2KB、8 步 trace 全部 completed。
两条独立缺陷叠加：

1. **前端没解包流式信封**：`debate/stream` 的 `__done__.response` 是 `{success,data,message}`，
   前端直接当业务数据用 → `result.report` 恒 `undefined` → 永远走 `setError('辩论未生成判决书')`，从不跳转；
   此后每次重试因案件已 `completed` 返回 `MISSING_FIELDS`（同样被信封吞掉），现象就是"一直出不来"。
   修复：`frontend/src/api/index.ts::unwrapDebateEnvelope`（按 `request()` 同样的规则解包 + `success:false` 报错）。
2. **`unknown` 受控值被当成主张**：原话"一周三次"（归一 `weekly_3plus`）被模型的
   `frequency_canonical="unknown"` 判成冲突 → 降级"未说明" → `_is_necessity` 判非刚需 → `H1` reject。
   用该案真实字段离线验算：`unknown` → reject(H1)；按文本归一 → 结论改变。
   修复：`resolve_frequency` / `resolve_trigger` / `build_facts` 三处一致——`unknown` 让位给文本归一，
   只有"具体受控值 vs 文本"矛盾才判冲突（否定作用域、真冲突降级均保持不变）。

顺带修掉三处小问题：① `confidence` 写成 `"0.85（较高）"`/`"85%"` 时整轮 LLM 结果作废（真实日志
`LLM result confidence is not numeric`）→ 改为宽松解析；② 案件 `completed` 后对话页仍显示「启动辩论分析」
→ 改为「查看判决书」；③ 高风险档下 `R4` 的说明写"无法确认是否覆盖"而字段是"已确认可覆盖" → 措辞如实化。

**验证（真实 API + 真实浏览器）**：

```text
uv run --frozen pytest tests -q                                  => 461 passed
uv run --frozen pytest tests/test_metamorphic.py tests/test_golden_dialogues.py \
    tests/test_semantic_facts.py tests/test_quality_gate.py \
    tests/test_user_facing_boundary.py -q                        => 98 passed
npm --prefix frontend run build                                  => tsc + vite 构建通过
```

浏览器端到端（`%TEMP%\dj-fix\verify_fix.mjs`，Chrome headless）：注册 → 建案（口语化输入）→
点「启动辩论分析」→ **26.9s 后跳转判决书**（`navigated: true`）→ 摘要显示"使用频率：每周三次以上"
（不再被 unknown 抹掉、依据无 `E5`）→ 返回对话页显示「查看判决书」且点击可跳转；全程 0 前端错误。
截图：`%TEMP%\dj-fix\shots\fix-02-verdict.png`（判决书渲染完整：8 步执行过程 / 正反方 / 证据 / 工具 / 依据 / 复盘入口）。

**修复后仍未决的口径问题（同一案暴露）**：该案修复后结论为 `buy`（依据 `E6+R3`：高风险档 + 高频 + 评分 46 ≥ 45）。
即"已有替代品**已确认可覆盖**需求"在**高风险档**不参与改判（`R2` 刻意不越过高风险档，且 `R4` 排在 `R3` 之后），
于是"泡沫轴已覆盖需求 + 花掉 100% 剩余预算"仍给出「建议购买」。是否让替代品信号在高风险档也优先于 `R3` 放行，
属于产品口径，尚未决定。


### 9.15 严格 JWT 一键启动 + RAG 实时联动凭据透传（2026-09-11）

**基线**：`merge-test/latest-dev-20260911@b4cdc51` ＋ 本次**未提交**工作区改动。

**背景**：一键脚本 `start_all.bat` 的写法 `cmd /c "… && set ENFORCE_JWT=true && …"` 有两个坑：
外层引号与内层 `set "X=Y"` 冲突；不带引号时 cmd 会把值存成 `"true "`（尾随空格），
而 `Config.ENFORCE_JWT` 用的是 `== "true"`，于是"看起来开了严格鉴权，实际仍是兼容模式"。
同时严格模式会切断 RAG 的实时历史联动：RAG 请求 `GET /api/history` 不带 `Authorization` → 401 → 静默回退静态数据。

**改动**：`start_all.bat`（父脚本 `set "ENFORCE_JWT=true"`，由 `start` 启动的子进程继承）；
`backend/app/services/rag_adapter.py`（为该 `user_id` 现签 JWT 放进 `Authorization` 头）；
`rag/retriever.py`（读 `Authorization` 头并透传，不改 POST body 契约）；
`rag/data_loader.py`（`auth_token` 参数 → 请求头）。RAG 只转发、不验签，鉴权仍在 B 完成。

**验证环境**：Windows 11 + Git Bash + 项目 `.venv`（Python 3.12.4）；E2E 全程真实 HTTP，
数据库为临时文件（不触碰 `data/decisionjury.db`），端口 8010/8011。

```text
run_tests.bat（隔离：内存库 / 无 API Key / RAG_LIVE_RECORDS=0）        => 503 passed, 0 failed（10.2s）

旧写法  cmd /c "… && set ENFORCE_JWT=true && …" 后端子进程                => Config.ENFORCE_JWT = False（raw env = 'true '）
新写法  父脚本 set "ENFORCE_JWT=true" + start 继承                        => Config.ENFORCE_JWT = True （raw env = 'true'）

严格模式 GET /api/history 无 token                                       => HTTP 401 {"code": "UNAUTHORIZED"}
严格模式 POST /auth/login                                                => 200，返回 access_token（token_type=bearer）
严格模式 带 token GET /api/history                                       => 200
带 token 写入 history_27ace35c / history_dee2e330
经 search_rag_evidence() 走 C→D→B（透传 token）                          => 结果第 1 条即刚写入的记录，本次调用 RAG 日志无回退提示
直连 RAG（不带 Authorization）同 query                                   => 不含该记录，RAG 日志出现"回退使用静态 JSON 数据"
```

**未做/边界**：Docker Compose 仍是兼容模式（未设 `ENFORCE_JWT`）；RAG 侧不验签、无 scope/短 TTL 限制；
没有刷新 token 流程；一键脚本的真实浏览器端到端（注册 → 建案 → 判决）仍待人工点一遍。





