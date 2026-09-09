# DecisionJury 后端镜像（FastAPI + SQLite）
# 构建上下文：项目根目录（需要同时拿到 backend/ 与 mcp_tools/）
#   docker build -f backend/Dockerfile -t decisionjury-backend .

FROM python:3.12-slim

# 国内 pip 镜像，可用 --build-arg PIP_INDEX_URL=... 覆盖
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

WORKDIR /app

# 依赖单独一层，代码改动时不用重装依赖
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 业务代码：backend 包 + mcp_tools 包（backend 通过 import mcp_tools 调用工具）
COPY backend /app/backend
COPY mcp_tools /app/mcp_tools

# SQLite 数据目录，由 docker-compose 挂载 named volume
RUN mkdir -p /data

EXPOSE 8000

# 注意：ENV=production 必须由 compose 注入。
# 若为 development，backend/main.py 的 check_database() 在检测到表结构不一致时会
# drop_all + create_all 重建数据库，容器里等于每次启动删库。
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
