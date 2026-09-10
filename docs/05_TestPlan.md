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

Windows 上可以用仓库根目录的 `run_tests.bat` 代替手工设置变量：它封装了上面同一组隔离变量，默认跑 `tests`，也支持传目标，例如 `run_tests.bat tests\test_input_parser.py`、`run_tests.bat tests -k savings`。双击运行时窗口会保留结果，从 cmd 窗口调用则直接返回退出码。脚本不替代上面的手工命令，环境变量或依赖变化时两者行为应保持一致。

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

### 9.3 预算金额来源修复（budget_source）

2026-09-10，工作分支 `dev` 工作区改动（未提交、未推送），基线 `dev@d79a0a2`。环境为 Windows / Python 3.12.4 / pytest 9.1.1，沿用§2的内存数据库、禁用 dotenv、无真实模型 Key、关闭实时历史拉取。

改动内容：`mcp_tools/cost_analyzer.py` 增加可选参数 `budget_source`（`monthly_budget` 默认 / `savings`）与存量分级表；`mcp_tools/mcp.py` 暴露同名 schema 字段并校验非法值；`backend/app/agents/input_parser.py` 按显式存量词识别金额来源，且只在本次真的写入金额时更新标签；`backend/app/services/mcp_adapter.py`、`backend/routers/tools.py` 透传；`mcp_tools/demo.py` 增加存量示例。

| 实际命令/检查 | 结果 |
|---|---|
| 基线：`git worktree add` 到 `dev@d79a0a2` 后跑同一命令 | 292 passed、5 failed、7 warnings，37.59秒 |
| `uv run --frozen pytest -p no:cacheprovider -q --tb=line --show-capture=no tests` | 317 passed、5 failed、7 warnings，7.52秒 |
| `uv run --frozen python -m compileall -q backend tests rag mcp_tools` | 通过 |
| `git diff --check` | 通过，无空白错误 |
| `python -m mcp_tools.demo` | 通过；同一金额在 `monthly_budget` 下为 high、在 `savings` 下为 medium |

新增25条用例全部通过：`test_cost_analyzer.py` +5（存量三档、超出资金池、默认口径不变、未知来源报错）、`test_mcp_tools.py` +4（schema 枚举、透传、默认值、非法值 INVALID_ARGS）、`test_input_parser.py` +10（存量词识别、月预算识别、存量金额不被当成价格、预算纠正翻转标签、无金额表达时保留标签、标签不参与最低字段、LLM 路径写入与不写入金额两种情况、存量口语变体、存量词不吞价格）、`test_debate_router.py` +2（端到端回归对）、`test_tools_router.py` +2（HTTP 接受 savings、非法来源失败）、`test_chat_router.py` +2（消息路径打 savings / monthly_budget 标签）。

真实 Key 测试追加修复：用户在浏览器中用"我自己攒有1000块钱，不影响日常支出"复现时，金额仍被按月预算判为 high。核对 `data/decisionjury.db` 的案件记录后确认是存量词表只列了"攒了/攒下"等固定搭配、漏掉"攒有"。词表改为按词根收录（攒 / 存款 / 储蓄 / 积蓄 / 闲钱 / 私房钱 / 存了 / 存下 / 存起来），并新增"存量词与金额之间不得出现买/购"的约束以防吞掉商品价格。用该案件的原始字段重跑：`budget_source=savings`、`risk_level=medium`、`final_decision=delay`（修复前为 high / reject）。该轮同样未执行真实 DeepSeek 调用，模型的字段抽取仍属未验收部分。

端到端回归对（本次修复的核心证据，`tests/test_debate_router.py`）：同一组数字 799/1000，带 `budget_source=savings` 时 cost_analyzer 为 medium、`final_decision=delay`；不带时仍为 high、`final_decision=reject`。该对用例锁住"修复误判"与"不放真·超预算"两侧。

5个失败仍为§9.1所列 `tests/test_migrate.py` 迁移测试，与基线完全一致，未因本次改动增加或减少。7条warning仍为既有 Pydantic Config 与 Starlette 422 常量弃用提示。

本轮未做：真实 DeepSeek Key 下的 parser/庭审验收、浏览器闭环、部署验收。因此本次只声明"隔离单元与契约测试通过、端到端规则链路通过"，不声明真实模型路径或线上部署已验收。本轮未修改任何测试或业务代码来绕过遗留失败。
