# -*- coding: utf-8 -*-
"""
RAG 数据加载模块。

职责：
  1. 读取项目根目录 data/history_records.json 的静态历史种子数据（当前 500 条）。
  2. 通过 B 后端 GET /api/history 拉取「前端/后端新写入的历史记录」，与静态数据合并，
     实现“新输入的数据也作为一条历史记录进入 RAG 检索”的联动。
  3. 后端不可用时自动回退到静态 JSON，保证 RAG 服务不中断。

实现说明：
  - 使用 Python 标准库 urllib，避免为 D 模块额外引入 requests 依赖。
  - 静态数据在首次读取后缓存，后续每次检索只增量拉取后端实时数据，开销可控。
  - 以记录的 id 为主键合并，后端实时数据优先（同一 id 以后端为准）。

配置（环境变量可选）：
  BACKEND_HISTORY_URL  后端历史接口地址，默认 http://127.0.0.1:8000/api/history
  HISTORY_TIMEOUT      请求后端超时秒数，默认 3
"""

import json
import os
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DATA_PATH = os.path.join(BASE_DIR, "..", "data", "history_records.json")

DEFAULT_BACKEND_HISTORY_URL = "http://127.0.0.1:8000/api/history"
BACKEND_HISTORY_URL = os.getenv("BACKEND_HISTORY_URL", DEFAULT_BACKEND_HISTORY_URL)
HISTORY_TIMEOUT = float(os.getenv("HISTORY_TIMEOUT", "1.0"))
# B 后端 GET /api/history 的 page_size 上限为 1000
HISTORY_PAGE_SIZE = 1000

_STATIC_CACHE = None


def _read_static_records():
    """读取静态历史种子数据，带缓存。"""
    global _STATIC_CACHE
    if _STATIC_CACHE is not None:
        return _STATIC_CACHE
    try:
        with open(STATIC_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _STATIC_CACHE = data if isinstance(data, list) else []
    except Exception as e:  # noqa: BLE001
        print(f"读取静态历史数据失败: {e}")
        _STATIC_CACHE = []
    return _STATIC_CACHE


def _normalize_backend_item(item):
    """
    把 B 后端 GET /api/history 返回的 item 转成 RAG 检索需要的 record 结构。

    B 返回的最小字段：history_id/user_id/case_type/title/summary/result/tags/...
    RAG 检索需要：title/content/source/case_type/tags/created_at，因此做字段映射：
      - content   <- summary  （B 用 summary 表达正文）
      - id        <- history_id
      - source    <- 固定 decision_history
    """
    if not isinstance(item, dict):
        return None

    content = (item.get("summary") or "").strip()
    if not content:
        return None

    record = dict(item)
    record["id"] = item.get("history_id") or item.get("id")
    record["content"] = content
    record["source"] = item.get("source") or "decision_history"
    record.setdefault("case_type", item.get("case_type"))
    record.setdefault("title", item.get("title") or "历史决策记录")
    record.setdefault("tags", item.get("tags") or [])
    record.setdefault("created_at", item.get("created_at"))
    return record


def fetch_backend_history(user_id="local_user"):
    """从 B 后端拉取指定用户的实时历史记录；失败返回空列表。"""
    # 可通过环境变量关闭实时联动（例如单测/离线环境），默认开启。
    if os.getenv("RAG_LIVE_RECORDS", "1") != "1":
        return []
    query = urllib.parse.urlencode(
        {"user_id": user_id, "page": 1, "page_size": HISTORY_PAGE_SIZE}
    )
    url = f"{BACKEND_HISTORY_URL}?{query}"
    try:
        with urllib.request.urlopen(url, timeout=HISTORY_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"无法连接后端历史接口 ({e})，回退使用静态 JSON 数据。")
        return []

    if not isinstance(payload, dict) or payload.get("success") is not True:
        print("后端历史接口返回异常，回退使用静态 JSON 数据。")
        return []

    data = payload.get("data") or {}
    items = data.get("items")
    if not isinstance(items, list):
        return []

    records = []
    for item in items:
        normalized = _normalize_backend_item(item)
        if normalized is not None:
            records.append(normalized)
    return records


def load_history_data(user_id="local_user"):
    """
    返回 RAG 检索候选记录：静态种子 + 当前用户的实时历史记录。
    后端不可用时只返回静态数据，保证 RAG 服务可用且不编造历史。
    """
    static_records = list(_read_static_records())

    live_records = fetch_backend_history(user_id)
    if not live_records:
        return static_records

    merged = {}
    for record in static_records:
        rid = record.get("id")
        if rid:
            merged[rid] = record
    for record in live_records:
        rid = record.get("id")
        if rid:
            merged[rid] = record
    return list(merged.values())


if __name__ == "__main__":
    records = load_history_data()
    print(f"成功加载了 {len(records)} 条历史记录！")
    if records:
        print("第一条数据的标题是:", records[0].get("title"))
