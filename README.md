# DecisionJury

DecisionJury 是一个面向日常购物决策的多 Agent 冷静决策助手，由 5 名计算机专业本科生在三周实训中协作开发。用户描述购买想法，系统收集关键字段，结合历史记录检索和规则工具，展示正反方独立陈述、判决说明及后续建议。

> 文档基线：`dev@53d70bc`。能力说明按代码核对，本轮隔离测试结果见 [测试记录](docs/05_TestPlan.md#9-本轮实际验证记录)，不代表真实 DeepSeek 或线上部署验收。当前只交付 `shopping`；`time` 已移出本次范围，保留代码和数据仅作后续扩展，不要求团队本轮实现。

## 当前能力与边界

| 能力 | 当前实现 |
|---|---|
| Web 交互 | React + TypeScript + Vite；注册登录、案件、多轮补充、报告、历史、观察清单页面 |
| API 与存储 | FastAPI + SQLAlchemy + SQLite；案件、消息、报告 JSON、trace、历史及提醒 |
| 输入解析 | DeepSeek 结构化解析 + 本地规则兜底，合并历史字段、处理纠正与金额歧义 |
| 简化模拟法庭 | 书记员摘要 → 正方独立陈述 → 反方独立陈述 → 法官判决；返回 `debate_events` |
| 法官 | 本地规则确定 `final_decision` 和置信度，DeepSeek 生成说明，失败时使用本地文本 |
| RAG | jieba + BM25，HTTP 检索静态种子和当前用户的后端历史；失败时不编造证据 |
| 工具 | C adapter 经 `call_tool` 调用成本分析、决策评分和条件触发的冷静期提醒 |
| 工程化 | Windows 一键脚本、Linux screen 脚本、Docker Compose 配置及自动化测试代码 |

不是多轮交叉辩论，不使用 SSE/WebSocket 实时输出；`decision_score` 是规则参考分，不是成功概率。当前没有向量检索，也不包含购物之外的完整决策流程。

### 已知问题

- B 的 `/debate` 已补齐 `Reminder` 导入（PR #89），本轮辩论路由测试通过；观察清单与复盘的浏览器闭环仍需实际验收。
- 注册登录接口已存在，但没有 JWT/统一会话鉴权。部分接口仅比较请求中的 `user_id`，不等于完善的访问控制，不应直接面向不受信任的公网用户开放。
- C 标记高风险主题，B 创建/消息/辩论路径仍有拒绝逻辑。本次仅面向低风险购物，不承诺专业医疗、法律或金融建议。
- 信息收集仍可能遇到歧义；最低字段是 `product_name / price / monthly_budget_left`，并要求无未解决冲突，不是“七项全部填满”，也没有跨轮最大次数熔断。
- PATCH 案件仍使用七字段完成条件，与创建/消息路径不同；迁移测试和根目录 pytest 收集还存在数据库隔离问题，详见测试记录。不要为让测试通过而改用日常数据库。

完整状态、责任与验收要求见 [里程碑与现状](docs/03_Milestones.md) 和 [测试计划](docs/05_TestPlan.md)。

## 主流程

```text
注册/登录 → 创建购物案件 → 多轮补充，B 保存 C 的 merged_fields
  → 达到最低字段要求 → POST /api/cases/{case_id}/debate
  → input_parser → RAG → cost_analyzer → decision_score
  → pro_agent → con_agent → cooling_reminder（条件触发）→ judge_agent
  → 报告与四条庭审事件 → B 保存结果/trace/成功提醒
  → GET report / trace → 用户复盘 → history → 后续 RAG 检索候选
```

`debate_events` 是四类发言；`trace` 是技术调用轨迹，两者不是同一份记录。C 完整结果含 trace，B 的 `/debate` HTTP 响应不直接返回 trace，需另查 `/trace`。

## 本地运行（Windows）

前提：安装 uv、满足 [pyproject.toml](pyproject.toml) 要求的 Python，以及 Node.js/npm。首次或拉取依赖更新后，在仓库根目录执行：

```powershell
uv sync --frozen
npm --prefix frontend install
```

真实模型演示：使用本机环境变量或项目根目录 `.env` 配置 `DEEPSEEK_API_KEY`。若本机已准备 `deepseek.local.ps1`，在启动后端的同一个 PowerShell 中执行：

```powershell
. .\deepseek.local.ps1
.\start_all.bat
```

该本地文件不是仓库交付物，也不能提交。双击 BAT 不会自动加载另一个终端里的临时环境变量。没有 Key 时也可运行：parser 用本地规则，正反方用 mock，法官用本地规则和说明；不能将其记作真实 API 验收。

脚本使用根目录 `.venv`；已有虚拟环境时不会自动同步新增依赖。脚本打印“已启动”不等于健康检查成功，应检查服务窗口与实际页面。

| 服务 | 默认地址 |
|---|---|
| 前端 | http://localhost:5173/ |
| 后端健康检查 | http://127.0.0.1:8000/api/health |
| Swagger | http://127.0.0.1:8000/docs |
| RAG Swagger | http://127.0.0.1:8001/docs |

手动启动时分别使用三个终端，以下命令均从仓库根目录执行：

```powershell
uv run --frozen uvicorn backend.main:app --host 127.0.0.1 --port 8000
uv run --frozen uvicorn retriever:app --app-dir rag --host 127.0.0.1 --port 8001
npm --prefix frontend run dev
```

这三条是独立服务命令，不是在一个被占用的终端里依次执行。端口冲突时先确认所属进程；Vite 实际端口以日志为准。停止脚本 `stop_all.bat` 会处理相关端口，运行前确认没有其他项目复用它们。

## 配置与部署

- LLM 默认地址 `https://api.deepseek.com`，模型 `deepseek-v4-flash`；`DEEPSEEK_TIMEOUT_SECONDS` 默认 30 秒。默认工厂未读取自定义模型/地址环境变量，不能仅增加 `.env` 字段就宣称切换第三方网关成功。
- `RAG_SEARCH_URL` 可配置 C 到 RAG 的 HTTP 地址；`BACKEND_HISTORY_URL` 配置 RAG 到后端历史接口；`RAG_LIVE_RECORDS=0` 可关闭实时历史拉取。
- `ENV=development` 为默认值，结构不一致可能重建数据库。保留数据的演示/部署应使用 `ENV=production`，升级前仍必须备份，迁移逻辑不等于任意 schema 变更均安全。
- Linux 快速演示见 [screen 部署](deploy/README.md)，容器构建、静态前端及数据卷见 [Docker 部署](deploy/DOCKER.md)。配置存在不等于已上线；本仓库不宣称任何未核验的公网地址。

## 测试与文档

测试应在隔离数据库中运行，避免 TestClient 启动检查改动本地数据。完整命令、手动场景和记录要求见 [测试计划](docs/05_TestPlan.md)。

| 文档 | 用途 |
|---|---|
| [AI 协作规矩](docs/00_AI_Collaboration_Rules.md) | 范围、协作、真实性与提交要求 |
| [MVP](docs/01_MVP.md) | 本次购物交付范围与完成定义 |
| [SPEC](docs/02_SPEC.md) | 实际架构、字段、调用顺序与边界 |
| [里程碑](docs/03_Milestones.md) | 五人职责、当前实现、待验收事项 |
| [API](docs/04_API.md) | HTTP 和 C 内部契约 |
| [测试计划](docs/05_TestPlan.md) | 购物验收、容错、真实 API 证据 |
| [D 模块进度](docs/06_Role_D_RAG_Progress.md) | 检索实现与历史评测记录 |
| [历史 UI 方案](docs/07_UI_Redesign_Options.md) | 设计候选，不作为已实现功能证明 |

团队 A/B/C/D/E 分别负责前端、后端、Agent、RAG、工具与工程化；代码目录为 `frontend/`、`backend/`、`rag/`、`mcp_tools/`、`tests/`、`data/`。从 `dev` 建功能分支，经组员 review 的 PR 合并，`main` 保留稳定版本；密钥、数据库、缓存和本地评测产物不提交。
