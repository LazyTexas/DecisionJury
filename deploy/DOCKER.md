# DecisionJury Docker 部署

> 实现基线：dev@53d70bc。本次只交付购物决策，time 延期。本轮同步配置说明，不代表重新执行构建、部署或真实 API 验收。限制与联调说明见 §10。

> 与 `deploy/README.md`（screen 方案）并列的第二套部署方式。
> screen 方案适合单台 Linux 服务器裸机跑；Docker 方案适合需要"环境可复现、一键起停"的场景。
> 两套方案共用源码，但变量注入和地址不同；Docker 以 docker-compose.yml 的 environment/build args 为准。当前应用没有统一 JWT/会话鉴权，不应直接向不受信任的公网用户开放。

## 1. 服务拓扑

```
浏览器
  │  http://<宿主机IP>:8088
  ▼
frontend (nginx:80)  ──/api/*──►  backend (uvicorn:8000)  ──HTTP──►  rag (uvicorn:8001)
                     ──/auth/*──►
```

| 服务 | 镜像 | 容器内端口 | 对宿主机暴露 | 说明 |
|---|---|:---:|:---:|---|
| frontend | nginx:1.27-alpine | 80 | ✅ 8088 | 托管前端静态资源 + 反向代理后端 |
| backend | python:3.12-slim | 8000 | ❌ | FastAPI，SQLite 落在 named volume |
| rag | python:3.12-slim | 8001 | ❌ | BM25 检索服务 |

backend 与 rag 只在 compose 内网互通，不对宿主机发布端口，减少暴露面。

## 2. 前置条件

| 软件 | 版本 | 验证 |
|---|---|---|
| Docker Engine | >= 24 | `docker --version` |
| Docker Compose | >= v2.20（需支持 `depends_on.condition`） | `docker compose version` |

无需在宿主机装 Python / Node，镜像内自带。

## 3. 快速开始

```bash
# 1. 仅当 .env 不存在时从示例准备；已有文件请编辑，勿覆盖私有配置
if [ ! -f .env ]; then
  cp deploy/.env.docker.example .env
fi
vim .env            # 真实模型演示需要 DEEPSEEK_API_KEY；不提交此文件

# 2. 构建并启动
docker compose up -d --build

# 3. 看状态（等三个服务都 healthy）
docker compose ps

# 4. 浏览器访问
#    http://<宿主机IP>:8088
```

首次构建需要拉取基础镜像并安装依赖，耗时取决于网络和机器，本轮没有测量构建时长。
后续只改代码不依赖时，重建会快很多（依赖层有缓存）。

## 4. 常用命令速查

> 前提：Docker Engine / Docker Desktop 已正常运行。以下命令都在项目根目录执行。

### 4.1 启动 / 停止

```bash
docker compose up -d              # 启动（后台运行）
docker compose up -d --build      # 代码改动后重建再启动
docker compose ps                 # healthy 只代表探活成功，业务链路另行验收

docker compose stop               # 暂停（容器与数据都保留）
docker compose start              # 恢复运行
docker compose restart backend    # 只重启单个服务

docker compose down               # 停止并删除容器（数据库 volume 保留）
docker compose down -v            # 停止并删除容器 + 数据库 volume（清库，慎用）
```

修改 .env 注入变量后使用 `docker compose up -d --force-recreate backend` 重新创建服务；单纯 restart 不重新读取容器环境配置。不要为生效而使用 down -v 清空数据库。

### 4.2 日志

```bash
docker compose logs -f                  # 实时看全部
docker compose logs -f backend          # 只看后端
docker compose logs --tail=100 rag      # 看最后 100 行
```

### 4.3 进入容器

各镜像自带的 shell 不同，用错会报 `stat /bin/bash: no such file or directory`：

| 服务 | 基础镜像 | 发行版 | 可用 shell |
|---|---|---|---|
| backend | python:3.12-slim | Debian 系，具体随镜像标签 | `bash`、`sh` |
| rag | python:3.12-slim | Debian 系，具体随镜像标签 | `bash`、`sh` |
| frontend | nginx:1.27-alpine | Alpine | **只有 `sh`** |

```bash
docker compose exec backend bash     # 后端
docker compose exec rag bash         # RAG
docker compose exec frontend sh      # 前端（Alpine 无 bash）
exit                                 # 退出容器
```

> `-it` 是进交互式终端必须的：`-i` 保持标准输入，`-t` 分配伪终端。
> 用 `docker exec -it <容器ID> sh` 时要自己写；用 `docker compose exec` 则不需要。

### 4.4 不进容器、只执行一条命令

```bash
# 查看容器内数据库文件
docker compose exec backend ls -l /data

# 统计案件数量
docker compose exec backend python -c "import sqlite3; print(sqlite3.connect('/data/decisionjury.db').execute('select count(*) from cases').fetchone())"

# 容器内自测后端健康检查
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').read().decode())"
```

### 4.5 Windows 专属坑：Git Bash 会改写绝对路径

在 **Git Bash** 里执行带 `/data` 这类绝对路径的命令时，路径会被自动改写成 Windows 路径
（变成 `D:/.../data`），报 `no such file or directory`。加环境变量即可：

```bash
MSYS_NO_PATHCONV=1 docker compose exec backend ls -l /data
```

**PowerShell / CMD 没有这个问题**，日常用 PowerShell 即可。

### 4.6 清理与排障

```bash
docker compose ps -a                       # 含已停止的容器
docker compose build --no-cache backend    # 不使用缓存重建
docker compose down --rmi local            # 连镜像一起清掉
docker system df                           # 查看 Docker 磁盘占用
```

## 5. 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 空 | 真实模型演示必需；无 Key 时 parser 本地规则、正反方 mock、法官本地规则与说明 |
| `DEEPSEEK_TIMEOUT_SECONDS` | 30 | 单次 LLM 请求超时，支持 1～120 秒，非法值使用默认 |
| `FRONTEND_PORT` | 8088 | 宿主机暴露端口 |
| `PIP_INDEX_URL` | 清华源 | 构建时 pip 源 |
| `NPM_REGISTRY` | npmmirror | 构建时 npm 源 |

以下变量由 compose 在容器内注入，**不要手动改**：

| 服务 | 变量 | 值 | 为什么 |
|---|---|---|---|
| backend | `ENV` | `production` | **关键**。development 下检测到表结构不一致会 `drop_all` + `create_all` 删库重建 |
| backend | `DATABASE_URL` | `sqlite:////data/decisionjury.db` | 指向挂载的 volume（注意是 4 个斜杠） |
| backend | `RAG_SEARCH_URL` | `http://rag:8001/api/rag/search` | 容器间用服务名，不是 127.0.0.1 |
| rag | `BACKEND_HISTORY_URL` | `http://backend:8000/api/history` | 同上 |
| rag | `RAG_LIVE_RECORDS` | `1` | 尝试加载用户历史 |
| rag | `HISTORY_TIMEOUT` | `3` | Compose 显式覆盖秒数，模块本身默认1秒 |

> RAG_SEARCH_URL 和 BACKEND_HISTORY_URL 是跨服务地址，不能在容器里仍指向自身 127.0.0.1。DATABASE_URL 是挂载目录，不是服务地址。
> DeepSeek 默认地址 https://api.deepseek.com、模型 deepseek-v4-flash。当前工厂未从环境读取模型/网关地址，compose 也未暴露它们；不要把上面的 RAG 地址配置能力等同于可随意切换第三方 LLM 网关。

## 6. 数据持久化

- SQLite 数据库位于 named volume `decisionjury-data`，挂载到 backend 容器的 `/data`。
- `docker compose down` 不会删除数据；只有 `down -v` 才会删。
- 备份（先停止后端写入；下列主机目录语法按 Bash 使用，PowerShell 请使用正确的本机挂载路径）：

```bash
docker compose stop backend
docker run --rm -v decisionjury-data:/data -v "$PWD:/backup" alpine \
  tar czf /backup/decisionjury-db-$(date +%F).tar.gz -C /data .
docker compose start backend
```

- 恢复：先核对备份、另存当前数据并停止服务。以下是覆盖数据的人工恢复操作，不属于日常重启流程；只能在确认恢复目标后执行。

```bash
docker compose down
docker run --rm -v decisionjury-data:/data -v "$PWD:/backup" alpine \
  sh -c "rm -f /data/*.db && tar xzf /backup/decisionjury-db-YYYY-MM-DD.tar.gz -C /data"
docker compose up -d
```

- 把本地已有数据库迁入 volume 时，先停止后端写入并备份两侧数据；不要对正在运行的 SQLite 数据库执行覆盖复制。数据结构必须与部署版本相容。不要使用下述常见但不安全的“运行中 docker cp”方式；具体迁移由部署负责人确认后执行。

> 注意：镜像**不包含** `data/*.db`（`.dockerignore` 已排除），
> 所以容器首次启动是空库，由后端启动时自动建表。

## 7. 验证部署是否成功

```bash
# 1. 三个服务都 healthy
docker compose ps

# 2. 后端健康检查（走 nginx 反代）
curl http://127.0.0.1:8088/api/health
# 期望：{"success":true,"data":{"status":"ok","version":"1.0.0"},"message":""}

# 3. 认证接口（验证 /auth 这条 location 配对了）
curl -X POST http://127.0.0.1:8088/auth/register \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo","name":"演示用户","password":"demo123456"}'

# 4. 浏览器打开 http://<宿主机IP>:8088，走完
#    注册 → 建案 → 多轮补全 → 启动辩论 → 判决书 → 复盘
```

辅助购物验证脚本为 `rag/e2e_verify.py`。后端镜像只复制 backend/ 和 mcp_tools/，没有 rag/ 脚本，不能直接运行 `python -m rag.e2e_verify`。可在宿主机仓库目录用 Bash 将脚本传入后端容器标准输入（前一步注册的 demo 用户必须存在）：

```bash
docker compose exec -T -e E2E_USER_ID=demo -e RAG_URL=http://rag:8001 backend python - < rag/e2e_verify.py
```

PowerShell 不支持这条 Bash 输入重定向语法。该脚本会创建测试数据，使用隔离演示库；它不替代四事件、消息恢复、提醒落库和浏览器验收。真实模型可能超过脚本的请求超时，需区分服务慢、降级与业务失败。

## 8. 与 screen 方案的差异

| 项 | screen 方案 | Docker 方案 |
|---|---|---|
| 前端 | Vite dev server（默认5173，以日志为准） | nginx 托管静态构建产物（80 → 宿主机 8088） |
| 进程托管 | screen | Docker restart policy |
| 环境依赖 | 宿主机装 Python/Node/screen | 只需 Docker |
| 数据库 | 宿主机 `data/decisionjury.db` | named volume `decisionjury-data` |
| 适合 | 单机快速演示 | 环境可复现 / 交付 / 多次重建 |

## 9. 常见问题

**Q1：`docker compose up` 卡在 backend 不 healthy？**
先看 `docker compose ps -a` 和 `docker compose logs backend rag`：区分后端未启动、启动异常和探活失败。RAG 未 healthy 时 backend 会等待；缺依赖或数据库检查异常需看具体日志。`.env` 不存在或 Key 为空本身不导致后端健康检查失败，但会使用本地/mock 模式。

**Q2：前端能打开但接口全 404 / 登录失败？**
先查请求路径、服务日志和代理。本项目后端有两条前缀：业务是 `/api`，认证是 `/auth`（**没有** `/api` 前缀），`frontend/nginx.conf` 里两条都要有；不能仅凭登录失败就断定代理缺失。

**Q3：辩论特别慢或超时？**
辩论链路串行调用 LLM（解析 → 正反方 → 法官），耗时与 `DEEPSEEK_TIMEOUT_SECONDS` 有关。nginx 已把 `/api/` 的 `proxy_read_timeout` 放宽到 300s。

**Q4：数据丢了？**
检查是否误用了 `docker compose down -v`（`-v` 会删 volume）。或者 `ENV` 被改成了 `development`，导致后端启动时重建数据库。

**Q5：构建时 pip/npm 卡住？**
在 `.env` 里显式指定国内源：

```
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
NPM_REGISTRY=https://registry.npmmirror.com
```

**Q6：`docker compose up` 报 `ports are not available ... bind: An attempt was made to access a socket in a way forbidden by its access permissions`？**
可能是 Windows 的端口保留问题，也需排查占用和权限。Hyper-V/WSL 可能预留 TCP 段，先查保留段与当前监听：
先查保留段：

```bash
netsh interface ipv4 show excludedportrange protocol=tcp
```

如果 `FRONTEND_PORT` 落在里面（例如本机 5141-5240 覆盖了 5173），换一个端口即可：

```bash
# .env
FRONTEND_PORT=8088
```

**Q7：想临时看后端/RAG 的接口？**
给对应服务临时加端口映射：

```bash
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').status)"
# 或在 docker-compose.yml 的 backend 下加：
#   ports: ["8000:8000"]
```

## 10. 已知限制（与容器化无关，是当前代码状态）

- `/debate` 的 `Reminder` 导入已在 PR #89 修复；旧镜像需重建，实际观察清单闭环仍需页面验收。
- `GET /api/cases/{case_id}/messages` 已实现，要求 user_id 并返回分页 id/session_id/type 字段；前端恢复与缓存兼容仍需真实页面验证。
- time 已移出本次交付范围，不再列为需要 C 本轮补齐的缺陷；前端若保留入口，不用于本次验收。
- PATCH 案件仍按七项字段判断完成度，与 parser 最低三项策略不同，见 [API](../docs/04_API.md)。
- 无统一 JWT/会话鉴权；Docker 网络隔离不解决应用权限问题。公开部署前需另行安全评审。

同步后重新构建并记录 commit，按 [测试计划](../docs/05_TestPlan.md) 验收，不以容器 healthy 代替真实 API 和购物流程证明。
