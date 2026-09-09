# DecisionJury RAG 检索服务（FastAPI + jieba + rank_bm25）
# 构建上下文：项目根目录（需要 rag/ 与 data/history_records.json）
#   docker build -f rag/Dockerfile -t decisionjury-rag .

FROM python:3.12-slim

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

WORKDIR /app

COPY rag/requirements.txt /app/rag/requirements.txt
RUN pip install --no-cache-dir -r /app/rag/requirements.txt

COPY rag /app/rag
# data_loader.py 读取 ../data/history_records.json（相对 rag/ 目录）
COPY data/history_records.json /app/data/history_records.json

# retriever.py 使用扁平导入 from data_loader import ...，
# 因此工作目录必须是 /app/rag，否则会 ImportError
WORKDIR /app/rag

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "retriever:app", "--host", "0.0.0.0", "--port", "8001"]
