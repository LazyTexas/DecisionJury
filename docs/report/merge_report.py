#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DecisionJury 小学期实验报告章节合并脚本

用法:
    python docs/report/merge_report.py
    python docs/report/merge_report.py --out docs/report/DecisionJury_小学期实验报告.md

说明:
    按 sections/ 目录下的文件顺序合并成一份 Markdown 报告。
    成员只需修改 sections/ 下自己负责的文件，再运行本脚本生成合并版。
    合并版文件头部会标记“由脚本生成”，请勿直接编辑合并版。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

SECTIONS: list[str] = [
    "00_封面_摘要_引言.md",
    "01_项目概述.md",
    "02_需求分析.md",
    "03_设计方案.md",
    "04_项目实现.md",
    "05_项目测试.md",
    "06_项目总结.md",
    "07_参考文献与附录.md",
]

PLACEHOLDER_RE = re.compile(r"【待填写|【截图|【表格|【代码|TODO")


def load_section(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"缺少章节文件: {path}")
    text = path.read_text(encoding="utf-8").rstrip("\n")
    return text


def extract_headings(sections_dir: Path) -> list[tuple[int, str]]:
    """从章节文件中提取分级标题，用于生成目录。"""
    headings: list[tuple[int, str]] = []
    in_code = False
    for name in SECTIONS:
        text = load_section(sections_dir / name)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code or not stripped.startswith("#"):
                continue
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped.lstrip("#").strip()
            if title and "封面信息" not in title:
                headings.append((level, title))
    return headings


def build_toc(headings: list[tuple[int, str]]) -> str:
    """生成 Markdown 分级目录；Word 版会用 TOC 域生成带页码目录。"""
    lines = ["# 目录", "", "> 以下为分级目录；Word 版会通过目录域自动生成带页码的目录。", ""]
    for level, title in headings:
        indent = "  " * max(0, level - 1)
        lines.append(f"{indent}- {title}")
    lines.append("")
    return "\n".join(lines)


def build_report(sections_dir: Path) -> str:
    parts: list[str] = [
        "<!-- 本文件由 docs/report/merge_report.py 自动生成，请勿直接编辑；修改请编辑 sections/ 下的对应文件。 -->",
        "",
        "# DecisionJury 小学期实验报告",
        "",
        "> 项目名称：DecisionJury——基于多 Agent 协作的日常冷静决策助手",
        "> 课程名称：综合能力实训",
        "> 本文档为章节合并版，最终排版请使用学校 Word 模板 `小学期实验报告模板(1).docx`。",
        "",
        "---",
        "",
        build_toc(extract_headings(sections_dir)),
        "---",
        "",
    ]
    for name in SECTIONS:
        section = load_section(sections_dir / name)
        parts.append(section)
        parts.append("")
        parts.append("---")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="合并 DecisionJury 实验报告章节")
    parser.add_argument(
        "--out",
        default="docs/report/DecisionJury_小学期实验报告.md",
        help="输出文件路径（默认 docs/report/DecisionJury_小学期实验报告.md）",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    sections_dir = script_dir / "sections"
    out_path = (script_dir.parent.parent / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out).resolve()

    report = build_report(sections_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    placeholders = PLACEHOLDER_RE.findall(report)
    print(f"已生成: {out_path}")
    print(f"章节数: {len(SECTIONS)}")
    print(f"待填占位符数量: {len(placeholders)}（请成员完成后清零）")


if __name__ == "__main__":
    main()
