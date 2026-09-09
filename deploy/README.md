# DecisionJury Linux 演示部署（screen）

> 基线：`dev@53d70bc`。本次仅交付购物决策；time延期。本文说明仓库现有脚本，不表示本次已重新部署或有可用公网地址。screen方案使用Vite开发服务器，适合受控实训演示，不是生产安全方案。

## 1. 前提与代码来源

需要git、Python≥3.11、Node.js/npm、screen；安装脚本还使用curl、xz等。Ubuntu版本默认Python可能不同，先检查。端口8000/8001/5173不得与其他项目冲突。

从团队已确认的仓库获取代码，记录commit：

```bash
git clone https://github.com/LazyTexas/DecisionJury.git
cd DecisionJury
git switch dev
git rev-parse HEAD
```

若网络不可达，可使用团队认可的镜像，但必须核对提交是否一致。不要为了部署擅自改团队origin地址，也不保证任何地区能访问特定下载源或模型服务。

## 2. 安装依赖

仓库根目录：

```bash
bash deploy/install.sh
```

脚本使用根目录 `.venv`、backend/requirements.txt和rag/requirements.txt，安装前端依赖；缺少Node时按脚本逻辑下载，缺少.env时从示例生成。镜像源相关选项有PIP_INDEX、NPM_REGISTRY、NODE_MIRROR、NODE_VERSION，具体默认以脚本为准。

拉取新增依赖后重新安装，不仅仅重启旧虚拟环境。Windows则按 [根README](../README.md) 使用uv和根目录.venv。

## 3. 配置与密钥

编辑本机项目根目录.env，不提交或把明文放进截图：

```dotenv
ENV=production
DEEPSEEK_API_KEY=<your-private-key>
DEEPSEEK_TIMEOUT_SECONDS=30
RAG_SEARCH_URL=http://127.0.0.1:8001/api/rag/search
```

- 真正的模型演示需要有效Key；无Key也能运行：parser本地规则、正反方mock、法官本地判决与说明。
- 默认DeepSeek模型为deepseek-v4-flash、地址为https://api.deepseek.com；当前工厂没有从环境读取自定义Base URL/model，不能添加变量后声称网关切换生效。
- ENV=production避免开发模式的结构检查删库重建；升级前仍先停止写入并备份数据库，不承诺任意结构变更自动安全迁移。
- RAG的BACKEND_HISTORY_URL/RAG_LIVE_RECORDS/HISTORY_TIMEOUT在RAG进程环境中配置；不要假设根.env的每个字段都会自动传到独立RAG进程。
- Windows的deepseek.local.ps1是本机辅助文件，Linux脚本不执行它。

## 4. 启停与日志

```bash
bash deploy/start.sh
screen -ls
tail -n 50 logs/backend.log
tail -n 50 logs/rag.log
tail -n 50 logs/frontend.log
```

backend/RAG绑定127.0.0.1:8000/8001；Vite绑定0.0.0.0，配置端口5173，实际以日志为准。前端代理/api和/auth到后端。

```bash
bash deploy/stop.sh
```

停止脚本会按会话和端口处理进程，先确认这些端口没有被别的项目使用。start会跳过已存在的screen会话，更新.env或代码后需要停掉对应旧服务再启动，不能只看到“SKIP”就以为加载了新版本。screen脚本没有开机自动恢复配置。

## 5. 访问与验收

在受控网络访问 `http://<服务器IP>:5173/`。按实际网络策略放行演示入口，不直接暴露数据库和RAG；当前应用缺少统一身份鉴权，不能只凭“已部署”宣称可安全服务公网用户。需要nginx静态构建的方案见 [Docker部署](DOCKER.md)。

验收步骤：

1. 核对commit，检查日志与GET /api/health，确认不是旧服务占用端口。
2. 通过/auth/register创建测试用户，再登录。不要使用users表不存在的ID创建案件。
3. 确认前端VITE_USE_MOCK没有设为true；否则页面是纯前端mock，不证明后端或DeepSeek可用。
4. 按 [测试计划](../docs/05_TestPlan.md) 完成两个购物案例、报告、四事件、trace与复盘。
5. B已修复Reminder导入；部署后仍要验收触发提醒的/debate、观察清单和复盘，不能跳过后宣布完整通过。
6. 模型网络成功与fallback分别取证，记录真实耗时；健康检查不会验证模型是否真实调用。

## 6. 排障

- 页面打不开：检查Vite实际端口、代理配置、监听地址、防火墙和服务日志。
- 缺依赖：核对实际解释器是否根目录.venv，重新安装已记录依赖，不依赖未纳入配置的手装包。
- 建案外键失败：注册的user_id必须存在，切换数据库后旧浏览器登录信息可能失效，重新注册/登录。
- 辩论500：看后端错误，不一概归因于RAG；如果仍报Reminder未导入，检查是否运行了PR #89合入前的旧代码。
- RAG断开：C应记录rag_search failed并降级，不编造历史；是否持久化成功还取决于B。
- 真实模型未调用：检查后端进程是否加载Key、请求/校验是否失败；不要输出Key排查。

生产级鉴权、HTTPS、资源限制与运维监控不由这些启动脚本自动提供。正式开放前需要另行安全评审。
