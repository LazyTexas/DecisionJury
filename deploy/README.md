# DecisionJury Ubuntu 服务器部署（screen 方案，华南/国内网络）

> 单台服务器、仅用 `screen` 保持服务运行；不考虑开机自启/重启自动拉起。
> 华南网络：GitHub / nodesource / astral 等境外站点常连不通，**请用国内镜像（Gitee、npmmirror、tuna/aliyun）**。
> Windows 本地启动仍用根目录 `start_all.bat` / `stop_all.bat`。

## 0. 重要：用 Gitee 拉代码（GitHub 连不上）

1. 在 Gitee 上新建仓库（或导入 GitHub 仓库：`https://gitee.com/<组织>/DecisionJury.git`）。
2. 服务器上用 Gitee 地址克隆：

```bash
git clone https://gitee.com/<组织>/DecisionJury.git DecisionJury
cd DecisionJury
```

3. 若你之后要把改动推回去，可把 `origin` 指向 Gitee：
```bash
git remote set-url origin https://gitee.com/<组织>/DecisionJury.git
```

## 1. 服务器环境（apt 部分用国内 apt 源更稳）

| 软件 | 用途 | 安装 | 验证 |
|---|---|---|---|
| git | 拉代码 | `sudo apt install -y git curl` | `git --version` |
| Python >= 3.11 | 后端/RAG | `sudo apt install -y python3 python3-venv python3-pip` | `python3 --version` |
| Node.js + npm | 前端 | 见下面（install.sh 会从 npmmirror 自动装，无 Node 时） | `node --version` / `npm --version` |
| screen | 进程托管 | `sudo apt install -y screen` | `screen --version` |
| psmisc (fuser) | stop 兜底杀端口 | `sudo apt install -y psmisc` | `fuser -k 8000/tcp 2>&1 \| head -1` |
| xz-utils | 解压 Node 包 | `sudo apt install -y xz-utils` | `xz --version` |

> Ubuntu 22.04 默认 Python 3.10，需 ≥3.11：如 24.04（默认 3.12）可直接用；22.04 请自行准备 3.11+（可用国内源/conda 等）。
> 可选：把 apt 源换成国内源（如 `https://mirrors.tuna.tsinghua.edu.cn/ubuntu/`）可加速 apt。

## 2. 拉代码并安装依赖

```bash
cd DecisionJury
bash deploy/install.sh
```

`install.sh` 会自动：
- 若没有 Node.js/npm，从 `npmmirror.com/mirrors/node` 下载安装（默认 Node 20.18.0）。
- 把 `npm` 源设为 `registry.npmmirror.com`。
- 用 `python3 -m venv .venv` + `pip` 通过 `pypi.tuna.tsinghua.edu.cn` 安装后端/RAG 依赖。
- `npm install`（走 npmmirror 源）安装前端依赖。
- 从 `deploy/.env.example` 生成根目录 `.env`。

> 可通过环境变量覆盖：`PIP_INDEX`、`NPM_REGISTRY`、`NODE_MIRROR`、`NODE_VERSION`。

## 3. 配置 .env

```bash
nano .env   # 或 vim .env
```

```env
ENV=production
DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_TIMEOUT_SECONDS=30
# RAG_SEARCH_URL=http://127.0.0.1:8001/api/rag/search   # 单机不用填，注释掉即可
```

- `DEEPSEEK_API_KEY`：必填，否则正反方/解析全走 mock（“不智能”）。DeepSeek 是境内服务，华南可正常访问 `api.deepseek.com`。
- `ENV=production`：避免后端在表结构不一致时删库重建。
- RAG 与后端同机，`RAG_SEARCH_URL` 保持注释（用默认 `127.0.0.1:8001`）。

## 4. 启动 / 停止

```bash
bash deploy/start.sh     # screen 起 后端(8000)/RAG(8001)/前端(5173)，前端绑 0.0.0.0
bash deploy/stop.sh      # 关闭三个 screen + 按端口兜底
```

日志：`logs/backend.log`、`logs/rag.log`、`logs/frontend.log`。

查看/进入 screen：
```bash
screen -ls
screen -r decisionjury-backend   # 回到对应会话，Ctrl+A D 退出
screen -S decisionjury-backend -X quit   # 直接关闭该会话
```

## 5. 访问与防火墙

浏览器访问 `http://<服务器IP>:5173`。放行端口：

```bash
sudo ufw allow 5173/tcp
```

> 说明：443/80 开放不代表境外站点能连——华南到 nodesource/GitHub 的链路常被网络屏蔽，所以必须用国内镜像。

## 6. 常见问题

- 前端 5173 打不开：确认 `start.sh` 里 vite 带 `--host 0.0.0.0`，且防火墙放行 5173。
- 后端 500：先看 `logs/backend.log`；多为 `.env` 未配好或 RAG 未启动。
- 下载/安装卡住：确认在用 Gitee(`git clone`)、npmmirror(npm/node)、tuna(pip) 等国内源。
- “不智能”：确认 `.env` 里 `DEEPSEEK_API_KEY` 已填，重启后端生效。
