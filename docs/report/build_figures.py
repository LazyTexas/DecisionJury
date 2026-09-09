#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成实验报告需要的示意图（架构图、流程图、测试与 RAG 指标图）。

运行：
    python docs/report/build_figures.py
输出：
    docs/report/assets/*.png
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    if bold:
        candidates = [r"C:\Windows\Fonts\msyhbd.ttc"] + FONT_CANDIDATES
    else:
        candidates = FONT_CANDIDATES
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        candidate = current + ch
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def draw_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str = "#ffffff",
    outline: str = "#333333",
    text_fill: str = "#111111",
    radius: int = 14,
    width: int = 3,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    x1, y1, x2, y2 = box
    lines = _wrap(draw, text, font, max(40, (x2 - x1) - 24))
    line_h = font.size + 8
    total_h = line_h * len(lines)
    start_y = y1 + ((y2 - y1) - total_h) // 2
    for idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        draw.text((x1 + ((x2 - x1) - w) // 2, start_y + idx * line_h), line, font=font, fill=text_fill)


def draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = "#333333", width: int = 4) -> None:
    draw.line([start, end], fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    head = 14
    p1 = (x2 - ux * head + px * head * 0.55, y2 - uy * head + py * head * 0.55)
    p2 = (x2 - ux * head - px * head * 0.55, y2 - uy * head - py * head * 0.55)
    draw.polygon([end, p1, p2], fill=color)


def build_architecture() -> None:
    w, h = 1500, 1050
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    title_font = _font(40, bold=True)
    layer_font = _font(28, bold=True)
    box_font = _font(24)
    small_font = _font(22)

    d.text((w // 2 - d.textbbox((0, 0), "DecisionJury 系统总体架构", font=title_font)[2] // 2, 20), "DecisionJury 系统总体架构", font=title_font, fill="#111111")

    layers = [
        ("用户层", "#eaf3ff", [("浏览器 / 用户", 500)]),
        ("前端层（React + Vite，:5173）", "#eef8ee", [("登录注册", 220), ("案件创建", 220), ("多轮对话", 220), ("庭审回放 / 报告", 260), ("历史 / 观察清单", 260)]),
        ("后端层（FastAPI，:8000）", "#fff7e6", [("认证 / 案件 / 消息", 300), ("辩论 / 报告 / 轨迹", 300), ("历史 / 观察清单 / 反馈", 340), ("SQLite 持久化", 260)]),
        ("Agent 编排层（C）", "#f6eefc", [("input_parser", 220), ("RAG adapter", 220), ("MCP adapter", 220), ("pro / con / judge", 300)]),
        ("服务与数据层", "#fdeeee", [("RAG 服务 :8001\njieba + BM25", 320), ("MCP 工具\ncost / score / reminder", 360), ("DeepSeek / mock", 260), ("SQLite + 历史 JSON", 320)]),
    ]

    y = 110
    for layer_name, color, boxes in layers:
        d.rounded_rectangle((40, y, w - 40, y + 150), radius=18, fill=color, outline="#888888", width=2)
        d.text((60, y + 16), layer_name, font=layer_font, fill="#222222")
        total_w = sum(b[1] for b in boxes) + 30 * (len(boxes) - 1)
        x = (w - total_w) // 2
        for label, bw in boxes:
            draw_box(d, (x, y + 58, x + bw, y + 132), label, box_font, fill="white", outline="#444444", radius=12, width=2)
            x += bw + 30
        y += 180

    # 竖向箭头
    for ay in (262, 442, 622, 802):
        draw_arrow(d, (w // 2, ay), (w // 2, ay + 25), width=5)

    d.text((w // 2 - d.textbbox((0, 0), "说明：前端只调用后端 REST API；Agent 编排层负责按顺序调用 RAG、工具和 LLM。", font=small_font)[2] // 2, h - 48),
           "说明：前端只调用后端 REST API；Agent 编排层负责按顺序调用 RAG、工具和 LLM。", font=small_font, fill="#555555")
    img.save(OUT_DIR / "fig_3_1_architecture.png")


def build_agent_flow() -> None:
    w, h = 1700, 1000
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    title_font = _font(40, bold=True)
    box_font = _font(24)
    note_font = _font(22)

    d.text((w // 2 - d.textbbox((0, 0), "多 Agent 编排流程", font=title_font)[2] // 2, 24), "多 Agent 编排流程", font=title_font, fill="#111111")

    row1 = [
        ("input_parser\n识别 / 提取 / 合并", "#eaf3ff"),
        ("rag_search\nBM25 历史检索", "#eef8ee"),
        ("cost_analyzer\n预算占比 / 风险", "#fff7e6"),
        ("decision_score\n0~100 综合评分", "#fff7e6"),
    ]
    row2 = [
        ("pro_agent\n正方独立陈述", "#f6eefc"),
        ("con_agent\n反方独立陈述", "#f6eefc"),
        ("cooling_reminder\n条件触发提醒", "#fdeeee"),
        ("judge_agent\n规则裁决 + 模型说明", "#fdeeee"),
    ]

    bw, bh = 340, 160
    gap = 45
    total = len(row1) * bw + (len(row1) - 1) * gap
    x0 = (w - total) // 2
    y1 = 160
    y2 = 520

    row1_boxes = []
    x = x0
    for idx, (label, color) in enumerate(row1):
        draw_box(d, (x, y1, x + bw, y1 + bh), label, box_font, fill=color, outline="#444444", radius=16, width=2)
        row1_boxes.append((x, x + bw))
        if idx < len(row1) - 1:
            draw_arrow(d, (x + bw, y1 + bh // 2), (x + bw + gap, y1 + bh // 2), width=5)
        x += bw + gap

    # 换行箭头：从第一行最后一个盒子底部绕到第二行第一个盒子顶部
    draw_arrow(d, (row1_boxes[-1][1] - bw // 2, y1 + bh), (row1_boxes[-1][1] - bw // 2, y2 - 30), width=5)
    draw_arrow(d, (row1_boxes[-1][1] - bw // 2, y2 - 30), (x0 + bw // 2, y2 - 30), width=5)
    draw_arrow(d, (x0 + bw // 2, y2 - 30), (x0 + bw // 2, y2), width=5)

    x = x0
    for idx, (label, color) in enumerate(row2):
        draw_box(d, (x, y2, x + bw, y2 + bh), label, box_font, fill=color, outline="#444444", radius=16, width=2)
        if idx < len(row2) - 1:
            draw_arrow(d, (x + bw, y2 + bh // 2), (x + bw + gap, y2 + bh // 2), width=5)
        x += bw + gap

    d.text((w // 2 - 560, y2 + bh + 60), "条件触发：成本风险为 medium/high，或触发原因为促销 / 种草 / 情绪。", font=note_font, fill="#555555")
    d.text((w // 2 - 560, y2 + bh + 104), "每一步都记录 TraceItem：步骤、类型、名称、输入摘要、输出摘要、耗时、状态、错误。", font=note_font, fill="#555555")
    img.save(OUT_DIR / "fig_3_2_agent_flow.png")


def build_rag_metrics() -> None:
    w, h = 1400, 900
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    title_font = _font(40, bold=True)
    label_font = _font(24)
    small_font = _font(20)

    d.text((w // 2 - d.textbbox((0, 0), "RAG 检索指标（top_k=5）", font=title_font)[2] // 2, 24), "RAG 检索指标（top_k=5）", font=title_font, fill="#111111")

    queries = ["降噪耳机", "学习用品", "社团活动", "技术分享"]
    metrics = {
        "precision@k": [0.40, 0.80, 0.60, 0.40],
        "recall@k": [0.3333, 0.1429, 0.2500, 0.2500],
        "MRR": [1.00, 1.00, 0.50, 1.00],
        "NDCG@k": [0.5531, 0.8539, 0.5296, 0.5531],
    }
    colors = ["#4c78a8", "#f58518", "#54a24b", "#e45756"]

    left, right, top, bottom = 140, w - 80, 150, h - 170
    d.line([(left, bottom), (right, bottom)], fill="#333333", width=3)
    d.line([(left, top), (left, bottom)], fill="#333333", width=3)

    for i in range(6):
        val = i / 5
        y = bottom - int((bottom - top) * val)
        d.line([(left, y), (right, y)], fill="#dddddd", width=1)
        d.text((60, y - 14), f"{val:.1f}", font=small_font, fill="#555555")

    group_w = (right - left) / len(queries)
    bar_w = group_w / (len(metrics) + 1)
    for qi, query in enumerate(queries):
        gx = left + qi * group_w + group_w * 0.1
        for mi, (name, values) in enumerate(metrics.items()):
            value = values[qi]
            bar_h = int((bottom - top) * value)
            x1 = gx + mi * bar_w
            x2 = x1 + bar_w * 0.8
            y1 = bottom - bar_h
            d.rectangle((x1, y1, x2, bottom), fill=colors[mi], outline="#333333")
            d.text((x1 + 4, y1 - 28), f"{value:.2f}", font=small_font, fill="#333333")
        label_w = d.textbbox((0, 0), query, font=label_font)[2]
        d.text((left + qi * group_w + group_w / 2 - label_w / 2, bottom + 14), query, font=label_font, fill="#222222")

    legend_x = left
    legend_y = h - 90
    for mi, name in enumerate(metrics):
        d.rectangle((legend_x, legend_y, legend_x + 24, legend_y + 24), fill=colors[mi], outline="#333333")
        d.text((legend_x + 34, legend_y - 2), name, font=small_font, fill="#333333")
        legend_x += 220

    img.save(OUT_DIR / "fig_5_1_rag_metrics.png")


def build_test_results() -> None:
    w, h = 1300, 820
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    title_font = _font(40, bold=True)
    label_font = _font(24)
    small_font = _font(22)

    d.text((w // 2 - d.textbbox((0, 0), "测试结果统计", font=title_font)[2] // 2, 24), "测试结果统计", font=title_font, fill="#111111")

    groups = [
        ("C Agent/LLM/adapter", 139, 0),
        ("D RAG 检索/评测", 18, 0),
        ("E MCP 工具/评分/提醒", 59, 0),
        ("B 后端路由/迁移", 58, 18),
        ("全量 tests/（汇总）", 279, 18),
    ]
    max_val = max(p + f for _, p, f in groups)
    left, right, top, bottom = 260, w - 80, 150, h - 150
    d.line([(left, bottom), (right, bottom)], fill="#333333", width=3)
    d.line([(left, top), (left, bottom)], fill="#333333", width=3)

    for i in range(6):
        val = max_val * i / 5
        y = bottom - int((bottom - top) * (i / 5))
        d.line([(left, y), (right, y)], fill="#dddddd", width=1)
        d.text((100, y - 14), f"{int(val)}", font=small_font, fill="#555555")

    row_h = (bottom - top) / len(groups)
    for gi, (name, passed, failed) in enumerate(groups):
        y_center = top + gi * row_h + row_h / 2
        bar_h = row_h * 0.45
        passed_w = int((right - left) * passed / max_val)
        failed_w = int((right - left) * failed / max_val)
        d.rectangle((left, y_center - bar_h / 2, left + passed_w, y_center + bar_h / 2), fill="#54a24b", outline="#333333")
        d.rectangle((left + passed_w, y_center - bar_h / 2, left + passed_w + failed_w, y_center + bar_h / 2), fill="#e45756", outline="#333333")
        d.text((left + passed_w + failed_w + 12, y_center - 14), f"{passed} passed / {failed} failed", font=small_font, fill="#333333")
        d.text((20, y_center - 14), name, font=label_font, fill="#222222")

    legend_x = left
    legend_y = h - 80
    d.rectangle((legend_x, legend_y, legend_x + 24, legend_y + 24), fill="#54a24b", outline="#333333")
    d.text((legend_x + 34, legend_y - 2), "passed", font=small_font, fill="#333333")
    d.rectangle((legend_x + 200, legend_y, legend_x + 224, legend_y + 24), fill="#e45756", outline="#333333")
    d.text((legend_x + 234, legend_y - 2), "failed", font=small_font, fill="#333333")

    img.save(OUT_DIR / "fig_5_2_test_results.png")


def _wire_base(title: str):
    w, h = 1300, 900
    img = Image.new("RGB", (w, h), "#f2f2f2")
    d = ImageDraw.Draw(img)
    title_font = _font(34, bold=True)
    body_font = _font(23)
    small_font = _font(20)
    d.rounded_rectangle((40, 40, w - 40, h - 40), radius=18, fill="white", outline="#999999", width=3)
    d.rectangle((40, 40, w - 40, 118), fill="#e8eef7", outline="#999999")
    d.text((70, 62), title, font=title_font, fill="#222222")
    return img, d, body_font, small_font


def _wire_box(d, xy, text, font, fill="#f7f7f7", outline="#bbbbbb", text_fill="#333333"):
    draw_box(d, xy, text, font, fill=fill, outline=outline, text_fill=text_fill, radius=10, width=2)


def build_wireframes() -> None:
    # 登录 / 注册
    img, d, body_font, small_font = _wire_base("登录 / 注册页面原型")
    _wire_box(d, (100, 180, 600, 760), "登录\n\n账号输入框\n\n密码输入框\n\n[ 登录 ]\n\n提示：登录成功后保存 Token", body_font)
    _wire_box(d, (700, 180, 1200, 760), "注册\n\n账号输入框\n\n昵称输入框\n\n密码输入框\n\n[ 注册 ]\n\n提示：注册成功后可返回登录", body_font)
    img.save(OUT_DIR / "fig_3_4_login.png")

    # 案件创建
    img, d, body_font, small_font = _wire_base("案件创建页面原型")
    _wire_box(d, (100, 180, 1200, 480), "输入框：我想买一副 1299 元的降噪耳机，最近学习需要安静……", body_font)
    _wire_box(d, (100, 520, 420, 610), "[ 创建案件 ]", body_font, fill="#4c78a8", outline="#4c78a8", text_fill="white")
    _wire_box(d, (100, 660, 1200, 780), "提示：仅支持低风险购物决策；系统会追问价格、本月剩余预算和已有替代品。", small_font)
    img.save(OUT_DIR / "fig_3_4_create_case.png")

    # 多轮对话
    img, d, body_font, small_font = _wire_base("多轮对话页面原型")
    _wire_box(d, (80, 160, 850, 760), "对话区\n\n用户：我想买一副 1299 元的降噪耳机\n\n系统：你本月预算还剩多少？是否已有类似耳机？\n\n用户：本月预算还剩 3000 元，已有普通耳机\n\n系统：信息已满足最低要求，可以开始分析", body_font)
    _wire_box(d, (900, 160, 1220, 420), "已收集字段\nproduct_name\nprice=1299\nmonthly_budget_left=3000", small_font)
    _wire_box(d, (900, 460, 1220, 760), "缺失字段\npurpose\nowned_alternatives\nexpected_usage_frequency\ntrigger_reason", small_font)
    img.save(OUT_DIR / "fig_3_4_chat.png")

    # 庭审 / 判决书
    img, d, body_font, small_font = _wire_base("庭审回放 / 判决书页面原型")
    _wire_box(d, (80, 160, 760, 280), "① 书记员：案件摘要（商品、价格、预算、替代品）", body_font)
    _wire_box(d, (80, 300, 760, 420), "② 正方：购买价值、使用频率、学习场景收益", body_font)
    _wire_box(d, (80, 440, 760, 560), "③ 反方：预算压力、闲置风险、替代方案", body_font)
    _wire_box(d, (80, 580, 760, 760), "④ 法官：最终建议（buy / delay / reject / alternative）与后续动作", body_font)
    _wire_box(d, (800, 160, 1220, 440), "RAG 证据\n历史闲置记录\n预算相关记录", small_font)
    _wire_box(d, (800, 480, 1220, 760), "工具结果\ncost_analyzer：占比 / 风险\nscore：综合分 / 维度", small_font)
    img.save(OUT_DIR / "fig_3_4_verdict.png")

    # 历史 / 观察清单
    img, d, body_font, small_font = _wire_base("历史记录 / 观察清单页面原型")
    _wire_box(d, (80, 160, 720, 760), "历史记录\n\n降噪耳机 消费复盘 | delay | 2026-09\n学习平板 消费复盘 | buy | 2026-08\n机械键盘 消费复盘 | regret | 2026-07", body_font)
    _wire_box(d, (760, 160, 1220, 760), "观察清单\n\n降噪耳机冷静期复盘\n到期：3 天后\n状态：waiting\n\n[ 取消提醒 ]", body_font)
    img.save(OUT_DIR / "fig_3_4_history.png")


if __name__ == "__main__":
    build_architecture()
    build_agent_flow()
    build_rag_metrics()
    build_test_results()
    build_wireframes()
    print(f"已生成示意图到 {OUT_DIR}")
