# DecisionJury

DecisionJury 是一个面向日常购物决策和时间决策的多 Agent 冷静决策助手。

项目目标是在三周内完成一个可运行的 Web Demo：用户提交一个纠结中的决策，系统通过多轮对话补全信息，结合历史案例 RAG 检索、MCP 工具调用和正反方法庭式辩论，输出一份可解释的“决策判决书”。

## 核心能力

- LLM API：调用大语言模型完成意图识别、辩论和裁决生成。
- RAG：检索用户历史决策、反思记录和冷静期案例。
- MCP 工具：至少实现成本分析工具和冷静期提醒工具。
- 多轮状态：保存用户目标、预算、时间压力、偏好和补充信息。
- 工作流编排：输入解析 Agent、正方 Agent、反方 Agent、法官 Agent 协作完成决策。
- 可观测性：记录 Agent 调用链路、工具调用结果和关键中间状态。

## 项目结构

```text
DecisionJury/
  backend/        后端 API、Agent 编排、状态管理
  frontend/       Web 前端界面
  mcp_tools/      MCP 工具实现
  rag/            RAG 检索、知识库、向量索引相关代码
  data/           示例数据和演示数据
  tests/          自动化测试和验收测试
  docs/           项目文档
```

## 必读文档

- `docs/00_AI_Collaboration_Rules.md`：AI 协作开发规矩。
- `docs/01_MVP.md`：MVP 范围和功能优先级。
- `docs/02_SPEC.md`：系统设计、Agent 流程、RAG 和 MCP 方案。
- `docs/03_Milestones.md`：三周开发计划和 5 人分工。
- `docs/04_API.md`：接口设计。
- `docs/05_TestPlan.md`：测试计划和验收标准。

## 协作流程

1. 从 `dev` 创建自己的功能分支，例如 `feature/backend-agent-flow`。
2. 每次只做一个清晰功能，提交前本地自测。
3. 提交 Pull Request 合并到 `dev`，由至少一名组员 Review。
4. 阶段测试通过后再由负责人将 `dev` 合并到 `main`，避免直接向 `main` 推送未检查代码。

## 当前阶段

当前仓库处于项目初始化阶段，已完成文档框架和目录结构。后续开发应优先完成 MVP 主链路：

```text
用户输入 -> 多轮补全 -> RAG 检索 -> MCP 工具调用 -> 多 Agent 辩论 -> 判决书
```
## 启动方式

### 一键启动（推荐）
双击项目根目录下的 `start_all.bat` 脚本，自动启动前后端服务。

### 手动启动
- 后端：`uvicorn backend.main:app --reload`
- 前端：`npm run dev`