# DecisionJury 验收报告（外部验收 · 真实使用场景）

> 验收对象：购物决策 Web Demo（三周实训交付）。验收方式：在**最新 GitHub 代码**上真启三服务，用真实浏览器走真实用户路径，并接真实 DeepSeek API 取证。
> **结论：本轮实训口径「有条件通过 —— 暂不能结案」**：主链路真实可跑通，但存在 1 个 P0（干净环境起不来）与 3 个 P1（一键脚本鉴权开关失效、README 与实际能力不一致、会话消息未落前端）必须先关闭；生产口径不通过（差距单列）。

---

## 0. 结论

### 0.1 双口径判定

| 口径 | 判定 | 依据 |
|---|---|---|
| **三周实训交付**（AGENTS.md DoD + MVP §8 六条） | **有条件通过，暂不能结案** | MVP §8 的 6 条中 4 条实测通过（两个购物案例、四事件+规则判决+证据、RAG 命中/空/故障、提醒落库+复盘+历史）；§8.1「隔离演示环境完成」与 §8.5「文档与实际契约一致」被 §4 的 P0/P1 打破 |
| **生产上线** | **不通过** | 默认弱 `SECRET_KEY`、鉴权默认兼容模式、消息只存浏览器本地、高风险拒绝不稳定、无监控/审计/HTTPS 等；其中多数属本轮范围外，见 §3.4 |

### 0.2 结案前必须关闭（4 项，全部已给出复现步骤）

| 编号 | 严重度 | 问题 | 修复成本 |
|---|---|---|---|
| A-1 | **P0** | `uv.lock` 未随 JWT 依赖更新 → 按 README 执行 `uv sync --frozen` 得到的干净环境**后端启动即崩溃**（`ModuleNotFoundError: No module named 'jose'`） | 执行 `uv lock` 并提交，约 10 分钟 |
| A-2 | P1 | `start_all.bat` 的 `set ENFORCE_JWT=true && …` 因 cmd 尾随空格写入 `"true "`，严格鉴权**实际未生效**，后端以兼容模式运行（无 token 也能用 `user_id` 自称身份） | 改为 `set "ENFORCE_JWT=true"`，一行 |
| A-3 | P1 | README/MVP 未随 23 个新提交同步：仍写「基线 dev@53d70bc」「没有 JWT/统一会话鉴权」 | 同步文档，约 30 分钟 |
| A-4 | P1 | 多轮会话消息仍未接服务端（接口已有、库里有数据，前端只读 localStorage）→ 清缓存/换浏览器后会话为 0 条 | 前端切到 `GET /api/cases/{id}/messages`，约半天 |

### 0.3 已实测通过项（详见 §3.1）

两个购物验收案例全部跑通（真实浏览器 + 真实 DeepSeek，判决 `delay`/置信度 0.85、成本占比 43%/medium、四条庭审事件、8 步 trace、RAG 引用、冷静期提醒落库、复盘入历史）；RAG 断连与模型不可用两条降级路径均不中断主流程且不编造证据；跨用户越权读取在最新代码上已全部 `FORBIDDEN`/401；`tsc -b && vite build` 通过；`run_tests.bat` 可用。

---

## 1. 验收基线与方法

### 1.1 基线（含一次重要更正）

| 阶段 | 基线 | 说明 |
|---|---|---|
| 首轮（作废） | 本地工作区分支 `feature/docs-shopping-scope@2c68835` + 1 个未提交改动 | **未 `git fetch`，基线过时**。`origin/dev` 当时已领先 23 个提交，我在此基线上报的「/debate 缺 user_id 导致 422」「ready 即锁输入框」「跨用户可读 detail/report/trace」三项缺陷在最新代码上**均已修复**，不成立 |
| **最终（本报告结论依据）** | **`origin/dev@9c907ca`**（2026-09-10 23:35 +0800，Merge PR #100） | 用 `git worktree` 在临时目录建独立检出验收，**未改动团队工作区**（验收后 `git status` 仍只有原有的 ` M frontend/src/api/index.ts`） |

> 残留提醒：团队工作区那 1 个未提交改动（给 `/debate` 补 `user_id`）与 `origin/dev` 上已合入的修复重复，建议丢弃或对齐，避免答辩机上"能跑"与仓库版本不一致。

### 1.2 环境

- Windows / Python 3.14.4（`uv` 0.11.9）/ Node v24.15.0 / pytest 9.1.1 / Playwright-core 1.63 + 本机 Chrome（无头）
- 服务：`backend:8000`、`rag:8001`、`frontend:5173`；数据库隔离（专用 `*.db`，不动 `data/decisionjury.db`；验收前后该库均为 0 行）
- 真实模型：`DEEPSEEK_API_KEY` 取自本机未入库的 `deepseek.local.ps1`；`GET /models` 返回 `deepseek-flash / deepseek-v4-pro`，配置的 `deepseek-v4-flash` 被服务端接受并回落为 `deepseek-flash`
- 说明：本沙箱屏蔽 IPv6，故 Vite 以 `--host 127.0.0.1` 启动做页面取证（`start_all.bat` 默认只绑 `::1`，真实浏览器不受影响，见 §3.3 P3-4）

### 1.3 真实使用路径（每条都有截图/响应原文）

```text
注册 → 新建购物决策 → 多轮补充 → 启动辩论（真实 API）
  → 判决书（正/反方、RAG 引用、工具结果、裁决、后续动作）
  → 完整庭审笔录（4 条发言）→ 提交复盘 → 观察清单 / 历史记录
异常路径：RAG 断连 · 模型不可用 · 越权访问 · 无 token / 伪造 token · 高风险主题
```

---

## 2. 逐项判定：MVP §8 完成定义

| # | MVP §8 要求 | 判定 | 证据 |
|---|---|---|---|
| 1 | 两个购物场景能在**隔离演示环境**完成，多轮状态与价格/预算不串值 | **部分通过** | 案例1：1299/3000 全程不串值，`delay`/0.85；案例2：2500→2200 纠正成功、预算保持 3000（`03-case2-price-correction.png`）。**但**「干净环境按 README 建不起来」（A-1），隔离环境完成的前提不成立 |
| 2 | 四个 Agent 步骤、四条庭审事件、规则判决及证据/工具结果可展示 | **通过** | 8 步 trace（parser 4.5–6.7s、rag 60ms、工具 0ms、正/反/法官 4.7–8.9s）；四条事件顺序 `书记员/正方/反方/法官`（`02-trace-modal-four-events.png`）；`cost_analyzer` = 43%/medium；判决由规则决定（`delay`），LLM 只写说明 |
| 3 | RAG 命中、无命中、服务失败及 LLM 降级均有记录 | **通过（含一条未达标项）** | 命中：3 条引用；无命中：`success=true, results=[]`（`zzzqqq`/`氨糖软骨素钙片` 等）；服务失败：trace `rag_search status=failed` + 真实错误、主流程继续、`rag_evidence=0`、法官明说"RAG 证据为空"不编造；LLM 不可用：`_parser_used=local_fallback` + 本地法官文案，流程不崩。**未达标**：agent 步骤的 mock 降级在 trace 里仍标 `completed` 且无任何标记（P2-3） |
| 4 | 检查 B 的提醒落库、观察清单查询和复盘写入历史，验收页面闭环 | **部分通过** | 提醒落库：`r_xxx status=waiting due=+3天`；复盘：历史新增（`满意/实际行为 not_bought/满意度 4★`，`04-history-after-feedback.png`）；观察清单页渲染正常。**缺陷**：复盘后提醒转 `reviewed` 即被接口过滤，清单里直接消失，前端"已复盘"分支不可达（P2-2） |
| 5 | 文档与实际契约一致；测试记录注明 commit/环境/命令/结果，mock 与真实 API 分开 | **不通过** | docs/02–05 已随新提交同步，但 README/MVP 仍停在 `dev@53d70bc` 且称"没有 JWT"（A-3）；docs/05 §9 未记录最新 317/5 结果与 `budget_source` 之后的基线；本轮真实 API/browser 验收记录此前并不存在（本报告补齐） |
| 6 | 代码经组员 review；演示版本和启动方式明确 | **部分通过** | PR 流水（#87–#100）与 `dev` 集成分支存在，符合协作约定；**但** `main` 停在 2026-07-02（落后 dev 214 个提交），"稳定版本"未定义；演示版本应以 `dev@9c907ca` 冻结 |

**AGENTS.md DoD 逐条**：本地可运行（**否**，A-1 干净环境失败）；关键路径有测试或验收记录（通过：317 passed + 本报告）；文档同步（**否**，A-3）；无密钥/临时产物（通过：密钥未入库；旧基线根目录 `db_check2.py` 在 dev 已删除）；PR 经组员检查（无法在本地验证，需 GitHub 侧确认）。

---

## 3. 缺陷清单

### 3.1 P0 —— 阻塞结案

**A-1 干净环境按 README 起不来（`uv.lock` 未更新）**

```text
复现（全新检出 origin/dev，无 .venv）：
  uv sync --frozen           # README 第 50 行的命令
  python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
实际结果：
  File "backend/routers/cases.py", line 11, in <module>
    from backend.security import get_current_user_optional
  File "backend/security.py", line 21, in <module>
    from jose import jwt, JWTError
  ModuleNotFoundError: No module named 'jose'
```

原因：`pyproject.toml`/`backend/requirements.txt` 已加 `python-jose[cryptography]`、`bcrypt==3.2.0`，但 `uv.lock` 未重新生成（确认：`uv.lock` 在 23 个提交中未变更，其中不含 `jose`/`bcrypt`）。

影响：全新克隆、助教机器、答辩备机按 README 走会直接失败；`start_all.bat` 只在 `.venv` **不存在**时才 `uv sync`，若用户先按 README 执行过（`.venv` 已存在）就会跳过同步、持续崩溃。危险的是本机团队环境早已装好依赖，所以日常无感知。
修复：`uv lock && git add uv.lock`（Docker 路径不受影响，因为镜像用 `requirements.txt`）。

### 3.2 P1 —— 结案前关闭

**A-2 一键脚本的 JWT 开关被 cmd 尾随空格吃掉**

```bat
start "DecisionJury Backend" cmd /c "cd /d %~dp0 && set ENFORCE_JWT=true && .venv\Scripts\python.exe -m uvicorn ..."
```
实测：`cmd /v:on /c "set X=true && echo [!X!]"` → `true `（带空格）；`set Y=true&& …` → `true`。`Config.ENFORCE_JWT = os.getenv(...).lower() == "true"` 因此为 `False`。
行为证据（由 `start_all.bat` 起的后端）：无 token 请求 `GET /api/cases?user_id=dev_234155` 返回 **HTTP 200 + 数据**（若严格模式应 401）。
影响：脚本"看起来"开了严格鉴权，实际仍是兼容模式——任何调用方只要填 `user_id` 就能冒充身份。修复：`set "ENFORCE_JWT=true"`（或去掉 `true` 与 `&&` 之间的空格）。

**A-3 README/MVP 与代码不一致（欠同步）**

- README 顶部仍写「文档基线：`dev@53d70bc`」，实际 `origin/dev` 已到 `9c907ca`（+23 提交）。
- README 第 25 行「注册登录接口已存在，但没有 JWT/统一会话鉴权」——JWT 已实现（`backend/security.py`、`/auth/login` 返回 `access_token`、前端统一注入 `Authorization`）。
- README 未提及 `ENFORCE_JWT`/`SECRET_KEY` 配置，也未提及新增的 `run_tests.bat`；MVP §3 能力表未写鉴权现状。
- docs/05 §9 未收录最新测试结果（317 passed/5 failed）与 `budget_source` 之后的行为。

**A-4 会话消息不落前端（已列为"待验收"，实测确认仍未做）**

- 服务端：`GET /api/cases/{id}/messages` 返回 **2 条**（有数据）。
- 前端：`getCaseMessages()` 仍只 `loadLocalMessages()`（源码注释也还写着"后端暂无读取接口"，已过时）。
- 实测：清空该 case 的 localStorage 后打开会话 → **0 条气泡**，显示"暂无消息，先说第一句吧"（`06-known-issue-messages-lost.png`）。
- 影响：换浏览器/换设备/清缓存即丢失全部对话上下文；"刷新恢复"只在同一浏览器成立；案件列表里的"消息数"与服务端一致但页面正文为空，体验自相矛盾。

### 3.3 P2 —— 不阻塞结案，但应在答辩中如实说明

1. **高风险拒绝不稳定 + 拒绝原因不透出**：4 次"信用卡套现炒股"建案中 1 次未判高风险；其中一案最终停在 `ready_for_debate`，UI 显示「待辩论 / 启动辩论分析 / 信息已补齐」（`07-known-issue-highrisk-debatable.png`），与页面左下自我声明"不涉及医疗、投资、法律等高风险领域"直接矛盾。`reject_reason` 在 create/messages/debate 三个响应里均为空/null，消息路径 `reply=null`（会渲染成空气泡）。属 LLM 分类概率性问题（高风险本不在本轮范围，但涉及安全边界）。
2. **观察清单口径不一致**：`GET /api/watchlist` 只返回 `status=waiting`，复盘后提醒转 `reviewed` 即从清单消失，`WatchlistPage` 里的"已复盘"分支不可达。
3. **LLM 静默降级不可观测**：无效 Key 下正/反方输出固定 mock 模板（"…具备一定购买价值。"/"…需要谨慎。"）、法官用本地说明，而 trace 8 步全部 `completed`、正则搜 `fallback|mock` 无命中；parser 有 `_parser_used=local_fallback`，三个 agent 步骤没有对应标记。演示时 Key 失效会"看起来分析正常"。
4. **测试遗留（文档已记录，本次复现）**：`tests/` **317 passed / 5 failed**（5 个全部是 `tests/test_migrate.py` 的引擎隔离问题）；根目录 `pytest` 仍因 `backend/test/test_feedback_quick.py` 导入期查库报 1 error（该文件在 dev 上未改动，行为同基线 A）。
5. `GET /api/history?result=bogus` 不校验，静默返回空列表；与 docs「非法值按校验返回」不一致（POST 路径有 schema 校验）。
6. **`POST /api/cases` 传不存在的 `user_id` 返回 `INTEGRITY_ERROR`（400，外键失败）** —— 现场已复现并定位完整链条（用户界面表现：「数据冲突，请刷新后重试」，而刷新并不能解决）：
   - 触发：后端经 `start_all.bat` 启动、库为 `data/decisionjury.db`；该库 `users` 表 **0 行**，但浏览器 localStorage 仍保存着旧会话 `dj:auth={user_id:test123}` + 旧 `token`。
   - 链条：前端带 `user_id=test123` + Bearer token → 后端解 token 得 `sub=test123` → 查 `users` 无此人 → **兼容模式**返回 `None` → 回退用请求体 `user_id` → `INSERT INTO cases(user_id='test123')` 违反外键 `cases.user_id → users.id` → `IntegrityError` → 400 `INTEGRITY_ERROR` → `frontend/src/utils/errors.ts:17` 映射为「数据冲突，请刷新后重试」。
   - 之所以"看起来还登录着"：`Config.SECRET_KEY` 是**硬编码默认值**（跨库、跨重启都验签通过），且 `RequireAuth` 只检查"本地有 user 且有 token"，不验证后端是否认识该用户；同时 A-2 的尾随空格让严格模式没生效，因此这种陈旧会话不会被 401 拦下，而是一路走到外键报错。
   - 为什么会没有这个用户：该库最后写入时间为 2026-09-08 14:45 且 `users` 为空，符合 `ENV=development` 下 `check_database()` 检测到表结构不一致就 `drop_all + create_all` 的行为（README 已提醒"结构不一致可能重建数据库"，但用户不会预期到会话残留）。
   - 验证与清理：`POST /auth/register` 建一个探针用户后，同一路径 `POST /api/cases` 立即 `success=true`（证明只有用户存在性受阻）；探针用户与案件已删除，`data/decisionjury.db` 六张表恢复 0 行。
   - 建议修法见 §3.5。

### 3.4 P3 —— 上生产差距与打磨项

1. `Config.SECRET_KEY` 有硬编码默认值；`ENFORCE_JWT` 默认 `false`，手工命令启动（README 的三条命令、docs 测试计划）会落在兼容模式。
2. `main` 分支停在 2026-07-02，落后 dev 214 个提交，与 AGENTS.md「main 只保留稳定版本」不符；建议明确 `dev@9c907ca` 为本轮演示冻结版本。
3. 展示小瑕疵：判决书导语出现"。。"（`case_summary` 自带句号 + 模板再加句号）；trace 节点 `decision_score` 无中文标签（`TRACE_NAME_LABEL` 缺项）；`TraceLogView` 不响应 `Esc`（只有 × 和点遮罩）；RAG 第三条证据常语义无关（耳机案引用"人体工学椅"，BM25 词面匹配的固有现象，但会削弱观感）。
4. Vite 默认绑定 `localhost`→`::1`：本沙箱 IPv6 被屏蔽导致 127.0.0.1 访问被拒（真实浏览器正常）。若答辩机浏览器偏好 IPv4，可用 `npm run dev -- --host 127.0.0.1` 规避。
5. 部署维度未实测：3 个 Dockerfile + `docker-compose.yml` 静态检查自洽（上下文/健康检查/env 齐全），但本机无 Docker，容器路径与 deploy/screen 脚本未运行验证——仓库本身也未宣称已上线，口径一致。
6. 密钥卫生：`deepseek.local.ps1` 靠 `.git/info/exclude` 排除，**未入库**（`git ls-files` 与全仓正则扫描均无明文 Key）✓；但该排除规则不随仓库分发，换机器有误提交风险，建议写入 `.gitignore`。
7. 无 `Docker`/无 GitHub 网络凭据时，PR「已由组员 review」这一条只能靠 PR 记录判断，本报告未独立核验。

---

## 3.5 「数据冲突，请刷新后重试」的修复建议（现场问题，按优先级）

1. **后端先校验身份实体**：`POST /api/cases` 等在写库前确认 `users` 中存在该身份；不存在时返回 `401 UNAUTHORIZED` / `USER_NOT_FOUND`，不要落到外键 `INTEGRITY_ERROR`。或对 JWT 已签名的 `sub` 做可选的 upsert 补建用户行（签名可信，可安全补建）。
2. **前端把陈旧会话顶回登录页**：`INTEGRITY_ERROR` / `MISSING_USER_ID` / `USER_NOT_FOUND` 也应走 `handleUnauthorized()`（清 `dj:auth` + `token` 并跳 `/login`）；错误文案不要写"请刷新后重试"——刷新不解决，需重新登录。
3. **开发模式重建库要更安全**：`ENV=development` 的 `drop_all + create_all` 前自动备份（`data/decisionjury.<ts>.bak.db`）并打印醒目警告，或改为迁移优先；避免"库被清空而浏览器还登录着"的错配。
4. **去掉固定默认 `SECRET_KEY`**：否则任意历史 token 在新库/新机器上仍然验签通过，"假登录"永远无法被发现。
5. **修掉 A-2 的尾随空格**：严格模式下这类陈旧会话会直接 401 并跳登录页，故障表现从"数据冲突"变成"请重新登录"，可自助恢复。

> 现场恢复办法（30 秒）：右上角账户菜单 →「切换用户」/「登出」，再用 `test123` 重新注册（或登录）；也可手动清掉 localStorage 的 `dj:auth` 与 `token`。若该用户名下原有案件/复盘数据，它们随那次重建一并丢失，可从 `data/decisionjury.bak.20260709171822.db` 等 7/9 备份尝试恢复（恢复前先备份当前库）。

---

## 4. 关键证据摘要（原始输出片段）

**真实 API 与规则一致性（案例1）**

```text
POST /api/cases      -> collected_fields.price=1299.0, _parser_used="deepseek"
POST /messages       -> monthly_budget_left=3000.0, case_status="ready_for_debate"
POST /debate         -> success=true, wall=24.7~30.8s, final_decision="delay", confidence=0.85
trace: input_parser 5.6s | rag_search 60ms(3条) | cost_analyzer 0ms | decision_score 0ms
       pro_agent 8.9s | con_agent 8.4s | cooling_reminder 0ms | judge_agent 7.7s
cost_analyzer        -> "该商品占剩余预算约 43%，风险等级为 medium。"（= MVP §6.1 预期）
debate_events        -> 书记员/正方/反方/法官 共 4 条，order=1..4
提醒落库             -> r_xxxx status=waiting due_at=+3天
复盘                 -> history result=worth「实际行为 not_bought，满意度 4★」；提醒转 reviewed
```

**降级与安全**

```text
RAG 断连   : trace[2] rag_search status=failed err="<urlopen error [WinError 10061] …>"
             主流程继续，success=true, decision=delay, confidence=0.65, rag_evidence=0
             法官文案："…RAG 历史证据为空…因此不能编造历史证据"
无效 Key   : _parser_used=local_fallback；正/反方为 mock 模板；trace 8 步仍全 completed；
             trace 文本正则 fallback|mock -> 无命中
越权（dev）: B 用户持自己 token 访问 A 的 detail/report/trace/messages/debate -> 全部 FORBIDDEN
严格模式   : 无 token -> 401 UNAUTHORIZED；伪造 token -> 401 INVALID_TOKEN；合法 token -> 200
一键脚本   : 无 token GET /api/cases -> 200（证明 ENFORCE_JWT 未生效，见 A-2）
测试       : 317 passed, 5 failed in 5.90s（失败= test_migrate.py）；run_tests.bat 定向 23 passed
前端构建   : tsc -b && vite build -> dist 292.51 kB（gzip 98.45 kB），通过
```

**证据文件**（`docs/acceptance_evidence/`）

| 文件 | 内容 |
|---|---|
| `01-verdict-dev.png` | 判决书全页：8 步执行轨迹、正/反方、RAG 引用、三工具、裁决 0.85、后续动作 |
| `02-trace-modal-four-events.png` | 完整庭审笔录：4 条发言 + 工具 metrics（含 `budget_source: monthly_budget`） |
| `03-case2-price-correction.png` | 案例2 第三轮纠正已在界面可输入，进度面板"可先辩论，另有 4 项建议补充" |
| `04-history-after-feedback.png` | 复盘写入历史（购物/满意/not_bought/4★） |
| `05-watchlist.png` | 观察清单页 |
| `06-known-issue-messages-lost.png` | 已知问题：清缓存后会话 0 条（服务端有 2 条） |
| `07-known-issue-highrisk-debatable.png` | 已知问题：高风险"借钱炒股"显示为可辩论 |
| `08-strict-jwt-verdict.png` | 严格 JWT 模式（手工以 `ENFORCE_JWT=true` 启动）下完整主链路判决书 |

---

## 5. 结案条件（建议 checklist）

- [ ] `uv lock` 后提交 `uv.lock`，并用**全新目录**验证：`uv sync --frozen` → `uvicorn backend.main:app` 能起（A-1）
- [ ] `start_all.bat` 改为 `set "ENFORCE_JWT=true"`，并用 `curl` 证明无 token 请求返回 401（A-2）
- [ ] README/MVP 同步到 `dev@9c907ca`：基线号、JWT 现状、`ENFORCE_JWT`/`SECRET_KEY`、`run_tests.bat`、最新测试数字（A-3）
- [ ] `getCaseMessages` 切到 `GET /api/cases/{id}/messages`（分页/字段对齐），验证"清缓存后仍有会话"（A-4）
- [ ] `main` 合并 `dev`（或明确声明本轮交付版本为 `dev@9c907ca` 并冻结）
- [ ] 在 docs/05 §9 追加本次外部验收记录（基线、环境、命令、结果、未关闭项）
- [ ] 已列 P2 项至少在答辩材料中如实标注（高风险拒绝不稳定、降级不可观测、观察清单口径、迁移测试 5 例）

以上 4 项（A-1~A-4）+ 基线冻结完成即可结案；其余按已知问题管理。

---

## 6. 附录：C 模块（input_parser）三条反馈的定位结论

> 反馈来源：团队 C 模块问题反馈（建案字段解析不完整 / 多轮 `missing_fields` 不更新 / `next_question` 为空）。
> 定位方式：在**基线 A（工作区 2c68835）**与**最新 dev（9c907ca）**上分别直连真实 DeepSeek 复现，逐条对比 LLM 路径与本地规则兜底路径。

### 7.1 首要根因（可稳定复现）：金额带单位 → 整轮解析被判定非法 → 静默降级

模型对"单价/近似"表达会返回**带单位的字符串**，而校验器只接受纯数字：

```text
输入：水果价格是5元一斤，我的预算是2000元
模型原始输出：{"extracted_fields":{"product_name":"水果","price":"5元/斤","monthly_budget_left":2000}, ...}
llm_client._validate_parser_result -> float("5元/斤") -> ValueError: price must be numeric
parse_input 捕获该异常 -> local_result（parser_used="local_fallback"），整轮模型结果被丢弃
实测：直连模型 6/6 返回 "5元/斤"；6/6 校验失败；经 parse_input 调用 5 次中 4 次降级
```

关键点：**失败是"整轮作废"，不是"丢掉一个字段"** —— 模型已经正确识别的 `product_name`、`monthly_budget_left`、`purpose` 全部一起丢失，随后由本地正则接管，于是出现反馈中的"只解析出预算、missing 不动"。`llm_client.py` 在基线 A 与 dev **完全一致**，即该缺陷在最新代码上同样存在。

### 7.2 三条反馈的逐条结论

| 反馈 | 结论 | 证据（两版一致，除注明外） |
|---|---|---|
| 问题1 建案只解析出 `monthly_budget_left` | **仅在降级路径成立**。本地 `_extract_price` 要求"购买动词在金额前 / 价格·售价关键词 / `X元的Y`"三者之一，"预算 3000 元，芒果 4 元"都不满足；且金额歧义兜底分支的前提是"**既无预算又无价格**"，此处已识别预算 → 第二个金额被静默丢弃。`_extract_product` 同样要求动词，故"芒果"也抓不到。另：**建案只用 `description` 走 parser，标题"买芒果"完全不参与解析**（dev 仅在描述为空时才用标题兜底） | 本地路径复现：`merged={"monthly_budget_left":3000.0}`，`missing=[product_name, price, …]`；真实 LLM 路径 6/6 正确得到 `{"product_name":"芒果","price":4.0,"monthly_budget_left":3000.0}` |
| 问题2 `missing_fields` 未随补充更新 | **不是"没重算"**：两版都是每轮按最新 `merged_fields` 重算（`[f for f in REQUIRED_SHOPPING_FIELDS if _is_missing(merged.get(f))]`）。真正原因是该轮**什么都没抽出来**：兜底下"花4元买"（动词在金额之后、"花"不在动词表）抓不到 price；"想补充营养"（无线索词 `为了/用于/需要`）抓不到 purpose。另有字段错位：LLM 路径把"没有其他水果"写进了 `trigger_reason`（实测），而本地 `(没有\|无)` 分支只返回"没有"两字、丢掉"其他水果" | 本地路径：`花4元买` → price 仍缺失；`想补充营养，没有其他水果` → `owned_alternatives="没有"`、purpose 未提取。LLM 路径：`purpose="补充营养"` 正确，但 `trigger_reason="没有其他水果"` 错位 |
| 问题3 `next_question` 常为空 | **LLM 路径是刻意置空**：`next_question = None if is_complete else (…)`，而 `is_complete` 只由**三个最低字段**（product_name/price/monthly_budget_left）决定 → 三个字段一满足，即使 `missing_fields` 还剩 4 项增强字段，也返回 `None`。B 端因此拼兜底文案——`origin/dev` 的 `backend/routers/chat.py:150` 正是反馈里那句"核心信息已完整，可以进入分析；建议补充：…"。而**本地兜底路径反而会生成** `_next_question(missing[0])`，两条路径行为不一致 | LLM 路径：`missing=[purpose, owned_alternatives, expected_usage_frequency, trigger_reason]` 且 `next_question=None`（基线 A 与 dev 均如此） |

### 7.3 修复建议（按优先级）

1. **金额容错解析**（最高优先，直接消除静默降级）：`_validate_parser_result` 对 `price`/`monthly_budget_left` 做宽松解析——从字符串中抽取数值（`"5元/斤"→5`、`"约1000元"→1000`、`"¥1299"→1299`、`"一千二"→1200`），或在 prompt 中强约束"只输出数字"。**注意语义**：`5元/斤` 是单价而非总价，建议新增 `price_unit`/`unit_price` 并让 `cost_analyzer` 明确按单价还是总价计算占比，避免把单价当总价算成本。
2. **字段级降级代替整轮作废**：单个字段非法时只丢弃该字段并记录 `field_meta` 警告，保留其余合法字段——"宽进严出"能把此类问题的影响面从"整轮"缩到"一个字段"。
3. **降级可见**：`parser_used`/`agent_step.error` 目前只落在 DB 的 `_parser_used`，接口响应与 trace 都不体现；建议把降级标记透出到 messages 响应与 trace，避免"看起来正常实则本地正则"。
4. **补本地正则的洞**（兜底质量）：`_extract_price` 支持"花 X 元买 / X 元买"（动词在金额后）与"X 元/斤"；`_extract_alternatives` 捕获否定短语的完整宾语；`_extract_purpose` 增加"想/想要/打算 + 动词"类线索。
5. **建案解析并入标题**：如 `parse_input(f"{title} {description}")`，或至少在描述缺商品名时用标题兜底（当前 dev 仅在描述为空时兜底），否则"买芒果"填在标题里等于没填。
6. **统一 `next_question` 策略**：LLM 路径与本地路径应一致——要么都返回增强字段的可选追问（文案用"可选补充"），要么都由 B 生成；现在是"LLM 置空、本地发问"。

> 复现脚本（临时目录，本次已清理）：`c_probe.py`（本地 vs LLM 路径对比）、`fallback_rate.py`（降级率统计）、`why_fallback.py`（抓取模型原始输出与校验失败点）。

---

## 7. 声明与局限

- 本报告由外部验收方在 `origin/dev@9c907ca` 上独立执行，**未修改任何业务代码**；仅在 `docs/` 下新增本报告与截图证据（未提交，可自行取舍）。
- 未做：Docker/容器构建、Linux screen 部署、生产压测、JWT 过期与刷新流程、并发/幂等与事务、移动端适配、真实用户可用性访谈。
- 「PR 经组员 review」依赖 GitHub 侧记录，本地无法独立确认。
- 表内所有"通过/失败"均来自本次实际执行；未执行项已显式标注为"未取证"，不以推断代替证据。
