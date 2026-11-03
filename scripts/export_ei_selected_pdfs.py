#!/usr/bin/env python3
"""Export the five EI selected collections as durable, navigable PDFs.

The database is read-only for this command.  Question and answer crops are
embedded losslessly; source-page fallbacks are labelled and their anchor is
marked so a reader can find the selected question quickly.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time_server.settings")

import django  # noqa: E402

django.setup()

from drill import (  # noqa: E402
    analog_selected,
    circuit_selected,
    communication_selected,
    digital_selected,
    signal_selected,
)
from drill.models import Question, QuestionAsset  # noqa: E402
from drill_sources.models import SourceQuestionAnchor  # noqa: E402


A4 = pymupdf.paper_rect("a4")
PAGE_W, PAGE_H = A4.width, A4.height
MARGIN = 34
TOP = 48
BOTTOM = 36
CONTENT_W = PAGE_W - 2 * MARGIN
NAVY = (23 / 255, 50 / 255, 77 / 255)
TEAL = (24 / 255, 128 / 255, 122 / 255)
ORANGE = (229 / 255, 129 / 255, 49 / 255)
INK = (35 / 255, 43 / 255, 51 / 255)
MUTED = (94 / 255, 106 / 255, 118 / 255)
PALE = (241 / 255, 246 / 255, 248 / 255)
WHITE = (1, 1, 1)

COURSES = {
    "circuit": ("电路", circuit_selected, "01-电路严选题.pdf"),
    "signal": ("信号与系统", signal_selected, "02-信号与系统严选题.pdf"),
    "analog": ("模拟电子技术", analog_selected, "03-模拟电子技术严选题.pdf"),
    "digital": ("数字电子技术", digital_selected, "04-数字电子技术严选题.pdf"),
    "communication": ("通信原理", communication_selected, "05-通信原理严选题.pdf"),
}

TIER_NAMES = {
    "core": "核心",
    "advanced": "进阶",
    "foundation": "基础",
    "cross": "交叉选练",
}
KIND_NAMES = {
    "analysis": "分析",
    "design": "设计",
    "calculation": "计算",
    "concept": "概念",
}


def clean_markdown(value: str) -> str:
    text = re.sub(r"```(?:\w+)?\n(.*?)```", r"\1", value or "", flags=re.S)
    text = re.sub(r"!\[[^]]*]\([^)]*\)", "[图]", text)
    text = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"[*_~`]", "", text)
    # The source uses Markdown/TeX delimiters.  The PDF renderer deliberately
    # keeps formula source readable instead of pretending to typeset it; remove
    # bare delimiters and translate the common operators that otherwise look
    # like noise in a printed solution.
    text = re.sub(r"^\s*\$\$\s*$", "", text, flags=re.M)
    text = re.sub(r"\$([^$]+)\$", r"\1", text)
    text = text.replace("$$", "")
    text = re.sub(r"\\text\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", text)
    replacements = {
        r"\\qquad": "   ", r"\\quad": "  ", r"\\,": " ",
        r"\\ne": "≠", r"\\leq": "≤", r"\\le": "≤", r"\\geq": "≥", r"\\ge": "≥",
        r"\\times": "×", r"\\cdot": "·", r"\\pm": "±", r"\\infty": "∞",
        r"\\Omega": "Ω", r"\\omega": "ω", r"\\pi": "π", r"\\theta": "θ",
        r"\\alpha": "α", r"\\beta": "β", r"\\gamma": "γ", r"\\Delta": "Δ",
        r"\\sum": "Σ", r"\\sqrt": "√", r"\\rightarrow": "→", r"\\Rightarrow": "⇒",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = text.replace(r"\\", "\n").replace("&=", "=").replace("&", "")
    text = re.sub(r"\\(?:begin|end)\{[^{}]+\}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_text(text: str, limit: int | None = None) -> str:
    value = (text or "").replace("\x00", "").strip()
    if limit and len(value) > limit:
        return value[: limit - 1] + "…"
    return value


class SelectedPdf:
    def __init__(self, course_name: str, module, output: Path):
        self.course_name = course_name
        self.module = module
        self.output = output
        self.manifest = module.manifest()
        self.doc = pymupdf.open()
        self.toc: list[list] = []
        self.bucket_pages: list[tuple[str, int, int]] = []
        self.missing_answers = 0
        self.source_page_questions = 0
        self._image_xrefs: dict[str, int] = {}
        self._page_bucket = ""
        self._page_question = ""
        self.page_offset = 0
        self.chunk_questions = 0
        self.chunk_paths: list[Path] = []
        self.temp_dir: Path | None = None

        rows = self.manifest["questions"]
        uuids = [row["uuid"] for row in rows]
        questions = Question.objects.filter(
            uuid__in=uuids,
            document__workspace="ei",
            is_practiceable=True,
        ).exclude(syllabus_scope="out_of_scope").select_related(
            "document", "similarity_topic", "topic"
        )
        self.questions = {str(q.uuid): q for q in questions}
        self.anchors = {
            str(anchor.question.uuid): anchor
            for anchor in SourceQuestionAnchor.objects.filter(
                question__uuid__in=uuids
            ).select_related("question", "source_question", "asset")
        }

    def font(self, page):
        # PyMuPDF's built-in CJK font is embedded as a compact CID font.
        page.insert_font(fontname="china-s")

    def new_page(self, *, bucket="", question=""):
        page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.font(page)
        self._page_bucket = bucket
        self._page_question = question
        return page

    def text(self, page, rect, value, *, size=9, color=INK, align=0, bold=False, lineheight=1.25):
        if not value:
            return 0
        font = "china-s"
        # The built-in Chinese font has no bold face; a darker colour and size
        # hierarchy are more reliable than synthetic bold in PDF viewers.
        return page.insert_textbox(
            rect,
            safe_text(value),
            fontsize=size + (0.25 if bold else 0),
            fontname=font,
            color=color,
            align=align,
            lineheight=lineheight,
        )

    def cover(self, total: int):
        page = self.new_page()
        page.draw_rect(A4, color=NAVY, fill=NAVY)
        page.draw_rect(pymupdf.Rect(0, 0, 13, PAGE_H), color=TEAL, fill=TEAL)
        page.draw_circle((PAGE_W - 70, 78), 78, color=TEAL, fill=TEAL, overlay=True)
        self.text(page, pymupdf.Rect(58, 168, PAGE_W - 58, 215), "892 电子信息", size=13, color=(0.72, 0.86, 0.86))
        self.text(page, pymupdf.Rect(58, 220, PAGE_W - 58, 290), self.course_name, size=31, color=WHITE, bold=True)
        self.text(page, pymupdf.Rect(58, 292, PAGE_W - 58, 345), "严选题 · 答案解析合订版", size=19, color=WHITE)
        page.draw_line((58, 370), (PAGE_W - 58, 370), color=(0.55, 0.68, 0.73), width=0.8)
        self.text(page, pymupdf.Rect(58, 392, PAGE_W - 58, 460), f"共 {total} 题  ·  题目在上，答案与解析在下", size=11, color=(0.82, 0.89, 0.91))
        self.text(page, pymupdf.Rect(58, 710, PAGE_W - 58, 760), "可检索题签 · 分章书签 · 原图无损嵌入 · A4 打印优化", size=9.5, color=(0.73, 0.82, 0.85))
        self.text(page, pymupdf.Rect(58, 765, PAGE_W - 58, 790), "由 time-tracker 严选题库生成", size=8, color=(0.58, 0.7, 0.74))
        self.toc.append([1, f"{self.course_name}严选题", 1])

    def guide(self, total: int):
        page = self.new_page()
        self.section_title(page, "使用说明", "先做题，再向下核对答案与解析")
        y = 118
        cards = [
            ("01", "每道题独立起页", "题目与答案按阅读顺序连续排布；内容较长时自动续页。"),
            ("02", "保留权威原图", "电路图、波形、表格与公式不做 OCR 重排，避免符号失真。"),
            ("03", "原页定位标记", "橙色标记指出原卷中的题目位置；整页保留可防止误裁条件。"),
            ("04", "快速跳转", "PDF 书签按章节和题目组织；目录给出各章节起始页。"),
        ]
        for number, title, body in cards:
            page.draw_rect(pymupdf.Rect(MARGIN, y, PAGE_W - MARGIN, y + 82), color=(0.84, 0.89, 0.91), fill=PALE, width=0.6)
            self.text(page, pymupdf.Rect(MARGIN + 14, y + 16, MARGIN + 56, y + 52), number, size=16, color=TEAL, bold=True)
            self.text(page, pymupdf.Rect(MARGIN + 68, y + 13, PAGE_W - MARGIN - 14, y + 38), title, size=11, color=NAVY, bold=True)
            self.text(page, pymupdf.Rect(MARGIN + 68, y + 40, PAGE_W - MARGIN - 14, y + 70), body, size=8.7, color=MUTED)
            y += 94
        note = f"本册收录 {total} 道严选题。筛选依据为备考优先级，不代表历年命题概率。"
        self.text(page, pymupdf.Rect(MARGIN, 535, PAGE_W - MARGIN, 590), note, size=9.2, color=INK)
        self.text(page, pymupdf.Rect(MARGIN, 620, PAGE_W - MARGIN, 705), "说明：若原题库当前没有独立答案，页面会明确标注“暂无独立答案材料”，不会用模型猜答补齐。", size=9, color=ORANGE)
        self.toc.append([2, "使用说明", len(self.doc)])

    def contents(self, bucket_counts):
        page = self.new_page()
        self.section_title(page, "章节目录", f"{len(bucket_counts)} 个专题")
        y = 116
        for index, (bucket, count) in enumerate(bucket_counts, 1):
            if y > PAGE_H - 70:
                page = self.new_page()
                self.section_title(page, "章节目录（续）", "")
                y = 105
            page.draw_line((MARGIN, y + 29), (PAGE_W - MARGIN, y + 29), color=(0.87, 0.89, 0.9), width=0.5)
            self.text(page, pymupdf.Rect(MARGIN, y, MARGIN + 34, y + 26), f"{index:02d}", size=9, color=TEAL, bold=True)
            self.text(page, pymupdf.Rect(MARGIN + 40, y, PAGE_W - 125, y + 26), bucket["title"], size=9.3, color=INK)
            self.text(page, pymupdf.Rect(PAGE_W - 120, y, PAGE_W - MARGIN, y + 26), f"{count} 题", size=8.5, color=MUTED, align=2)
            y += 40
        self.toc.append([2, "章节目录", 3])

    def section_title(self, page, title, subtitle):
        page.draw_rect(pymupdf.Rect(0, 0, PAGE_W, 74), color=NAVY, fill=NAVY)
        self.text(page, pymupdf.Rect(MARGIN, 20, PAGE_W - MARGIN, 51), title, size=18, color=WHITE, bold=True)
        if subtitle:
            self.text(page, pymupdf.Rect(MARGIN, 78, PAGE_W - MARGIN, 104), subtitle, size=8.7, color=MUTED)

    def bucket_page(self, index, bucket, count):
        page = self.new_page(bucket=bucket["title"])
        page.draw_rect(A4, color=NAVY, fill=NAVY)
        page.draw_rect(pymupdf.Rect(0, 0, PAGE_W, 15), color=TEAL, fill=TEAL)
        self.text(page, pymupdf.Rect(55, 132, 150, 190), f"{index:02d}", size=37, color=(0.43, 0.72, 0.7), bold=True)
        self.text(page, pymupdf.Rect(55, 225, PAGE_W - 55, 320), bucket["title"], size=24, color=WHITE, bold=True)
        self.text(page, pymupdf.Rect(55, 337, PAGE_W - 55, 410), bucket.get("focus", ""), size=10.5, color=(0.82, 0.89, 0.91), lineheight=1.5)
        self.text(page, pymupdf.Rect(55, 470, PAGE_W - 55, 510), f"本章 {count} 题  ·  {TIER_NAMES.get(bucket.get('tier'), bucket.get('tier', ''))}", size=10, color=(0.65, 0.8, 0.81))
        return len(self.doc)

    def question_header(self, page, number, row, question, *, continued=""):
        label = safe_text(question.display_label or question.source_label or row.get("label") or f"第 {number} 题", 92)
        title = f"{number:03d}  {label}{continued}"
        page.draw_rect(pymupdf.Rect(0, 0, PAGE_W, 39), color=NAVY, fill=NAVY)
        self.text(page, pymupdf.Rect(MARGIN, 10, PAGE_W - MARGIN, 31), title, size=9.2, color=WHITE, bold=True)
        tier = TIER_NAMES.get(row.get("tier"), row.get("tier", ""))
        kind = KIND_NAMES.get(row.get("kind"), row.get("kind", ""))
        source = question.document.display_title or question.document.title
        meta = " · ".join(value for value in (tier, kind, safe_text(source, 45)) if value)
        self.text(page, pymupdf.Rect(MARGIN, 43, PAGE_W - MARGIN, 61), meta, size=7.2, color=MUTED)
        return 67.0

    def band(self, page, y, title, *, answer=False, note=""):
        color = TEAL if answer else NAVY
        page.draw_rect(pymupdf.Rect(MARGIN, y, PAGE_W - MARGIN, y + 25), color=color, fill=color)
        self.text(page, pymupdf.Rect(MARGIN + 10, y + 6, PAGE_W - MARGIN - 10, y + 21), title, size=8.5, color=WHITE, bold=True)
        if note:
            self.text(page, pymupdf.Rect(PAGE_W - 220, y + 6, PAGE_W - MARGIN - 10, y + 21), note, size=6.8, color=(0.88, 0.95, 0.95), align=2)
        return y + 32

    def get_material(self, question):
        own = list(QuestionAsset.objects.filter(question=question, asset_type__in=("question_crop", "answer_crop")).order_by("asset_type", "position", "pk"))
        q_assets = [asset for asset in own if asset.asset_type == "question_crop"]
        a_assets = [asset for asset in own if asset.asset_type == "answer_crop"]
        answer_text = question.answer_markdown
        anchor = self.anchors.get(str(question.uuid))
        fallback_q = False
        fallback_a = False
        if anchor and not q_assets:
            q_assets = [anchor.asset]
            fallback_q = True
        if anchor and not a_assets and not answer_text:
            source_assets = list(QuestionAsset.objects.filter(
                question=anchor.source_question,
                asset_type="answer_crop",
            ).order_by("position", "pk"))
            a_assets = source_assets
            answer_text = anchor.source_question.answer_markdown
            fallback_a = bool(a_assets or answer_text)
        return q_assets, a_assets, answer_text, anchor, fallback_q, fallback_a

    def add_asset(self, page, y, asset, *, number, row, question, anchor_y=None, continued_label=""):
        available = PAGE_H - BOTTOM - y
        natural_h = CONTENT_W * asset.height / asset.width
        if natural_h > available and y > 105:
            page = self.new_page(bucket=self._page_bucket, question=self._page_question)
            y = self.question_header(page, number, row, question, continued=continued_label)
            available = PAGE_H - BOTTOM - y
        scale = min(CONTENT_W / asset.width, available / asset.height, 1.0)
        width = asset.width * scale
        height = asset.height * scale
        x = MARGIN + (CONTENT_W - width) / 2
        rect = pymupdf.Rect(x, y, x + width, y + height)
        xref = self._image_xrefs.get(asset.sha256, 0)
        if xref:
            page.insert_image(rect, xref=xref, keep_proportion=True)
        else:
            xref = page.insert_image(rect, stream=bytes(asset.image_data), keep_proportion=True)
            self._image_xrefs[asset.sha256] = xref
        if anchor_y is not None:
            marker_y = rect.y0 + max(0.02, min(0.98, anchor_y)) * rect.height
            page.draw_line((rect.x0 - 5, marker_y), (rect.x0 + 12, marker_y), color=ORANGE, width=2.5, overlay=True)
            triangle = [(rect.x0 - 5, marker_y - 5), (rect.x0 + 2, marker_y), (rect.x0 - 5, marker_y + 5)]
            page.draw_polyline(triangle + [triangle[0]], color=ORANGE, fill=ORANGE, overlay=True)
        return page, rect.y1 + 9

    def add_text_block(self, page, y, value, *, number, row, question, continued_label="", size=9):
        text = clean_markdown(value)
        if not text:
            return page, y
        paragraphs = text.splitlines() or [text]
        for paragraph in paragraphs:
            paragraph = paragraph or " "
            estimated = max(26, (len(paragraph) // 38 + 1) * size * 1.55)
            if y + estimated > PAGE_H - BOTTOM:
                page = self.new_page(bucket=self._page_bucket, question=self._page_question)
                y = self.question_header(page, number, row, question, continued=continued_label)
            height = min(estimated + 8, PAGE_H - BOTTOM - y)
            self.text(page, pymupdf.Rect(MARGIN + 7, y, PAGE_W - MARGIN - 7, y + height), paragraph, size=size, color=INK, lineheight=1.4)
            y += height + 3
        return page, y

    def question(self, number, row, question, bucket_title):
        page = self.new_page(bucket=bucket_title, question=question.display_label or question.source_label)
        start_page = self.page_offset + len(self.doc)
        y = self.question_header(page, number, row, question)
        q_assets, a_assets, answer_text, anchor, fallback_q, fallback_a = self.get_material(question)
        q_note = "原卷定位" if fallback_q else "独立题图" if q_assets else "文字题"
        y = self.band(page, y, "题目", note=q_note)
        if q_assets:
            for index, asset in enumerate(q_assets):
                marker = anchor.y if fallback_q and index == 0 and anchor and asset.pk == anchor.asset_id else None
                page, y = self.add_asset(page, y, asset, number=number, row=row, question=question, anchor_y=marker, continued_label=" · 题目续")
            if fallback_q:
                self.source_page_questions += 1
        else:
            prompt = question.prompt_text or question.latex_text or row.get("evidence") or question.display_label or question.source_label
            page, y = self.add_text_block(page, y, prompt, number=number, row=row, question=question, continued_label=" · 题目续", size=9.5)

        if y + 95 > PAGE_H - BOTTOM:
            page = self.new_page(bucket=bucket_title, question=question.display_label or question.source_label)
            y = self.question_header(page, number, row, question, continued=" · 答案")
        answer_note = "原卷答案页" if fallback_a else "题库答案"
        y = self.band(page, y + 4, "答案与解析", answer=True, note=answer_note)
        if a_assets:
            for asset in a_assets:
                page, y = self.add_asset(page, y, asset, number=number, row=row, question=question, continued_label=" · 答案续")
        if answer_text:
            if a_assets:
                if y + 70 > PAGE_H - BOTTOM:
                    page = self.new_page(bucket=bucket_title, question=question.display_label or question.source_label)
                    y = self.question_header(page, number, row, question, continued=" · 文字解析")
                y = self.band(page, y + 2, "文字解析", answer=True)
            page, y = self.add_text_block(page, y, answer_text, number=number, row=row, question=question, continued_label=" · 解析续", size=8.8)
        if not a_assets and not answer_text:
            self.missing_answers += 1
            page.draw_rect(pymupdf.Rect(MARGIN, y, PAGE_W - MARGIN, y + 58), color=(0.93, 0.79, 0.62), fill=(1, 0.97, 0.92), width=0.7)
            self.text(page, pymupdf.Rect(MARGIN + 12, y + 13, PAGE_W - MARGIN - 12, y + 47), "暂无独立答案材料；为避免误导，本册不自动猜答。", size=9, color=(0.62, 0.32, 0.08))
        return start_page

    def add_footers(self):
        for local_index, page in enumerate(self.doc, 1):
            index = self.page_offset + local_index
            if index == 1:
                continue
            page.insert_font(fontname="china-s")
            page.draw_line((MARGIN, PAGE_H - 25), (PAGE_W - MARGIN, PAGE_H - 25), color=(0.87, 0.89, 0.9), width=0.4, overlay=True)
            label = self.course_name
            self.text(page, pymupdf.Rect(MARGIN, PAGE_H - 21, PAGE_W / 2, PAGE_H - 7), label, size=6.7, color=MUTED)
            self.text(page, pymupdf.Rect(PAGE_W / 2, PAGE_H - 21, PAGE_W - MARGIN, PAGE_H - 7), str(index), size=7, color=MUTED, align=2)

    def flush_chunk(self):
        """Persist a bounded part of the book to keep image memory predictable."""
        if not len(self.doc):
            return
        self.add_footers()
        path = self.temp_dir / f"chunk-{len(self.chunk_paths):03d}.pdf"
        page_count = len(self.doc)
        self.doc.save(path, garbage=4, deflate=True, clean=True)
        self.doc.close()
        self.chunk_paths.append(path)
        self.page_offset += page_count
        self.doc = pymupdf.open()
        self._image_xrefs.clear()
        self.chunk_questions = 0

    def render(self):
        ordered = []
        rows_by_bucket = defaultdict(list)
        for row in self.manifest["questions"]:
            if row["uuid"] in self.questions:
                rows_by_bucket[row["bucket"]].append(row)
        buckets = [b for b in self.manifest["buckets"] if rows_by_bucket[b["key"]]]
        for bucket in buckets:
            ordered.extend(rows_by_bucket[bucket["key"]])

        self.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ei-selected-pdf-") as temp_name:
            self.temp_dir = Path(temp_name)
            self.cover(len(ordered))
            self.guide(len(ordered))
            self.contents([(bucket, len(rows_by_bucket[bucket["key"]])) for bucket in buckets])
            number = 0
            for bucket_index, bucket in enumerate(buckets, 1):
                # Start a large chapter with a fresh bounded chunk when the
                # previous one is already substantial.
                if self.chunk_questions >= 70:
                    self.flush_chunk()
                rows = rows_by_bucket[bucket["key"]]
                bucket_page = self.page_offset + self.bucket_page(bucket_index, bucket, len(rows))
                self.toc.append([2, bucket["title"], bucket_page])
                first_question_page = None
                for row in rows:
                    if self.chunk_questions >= 70:
                        self.flush_chunk()
                    number += 1
                    question = self.questions[row["uuid"]]
                    page_number = self.question(number, row, question, bucket["title"])
                    self.chunk_questions += 1
                    first_question_page = first_question_page or page_number
                    label = safe_text(question.display_label or question.source_label or row.get("label") or f"第 {number} 题", 80)
                    self.toc.append([3, f"{number:03d} {label}", page_number])
                self.bucket_pages.append((bucket["title"], first_question_page or bucket_page, len(rows)))

            self.flush_chunk()
            subprocess.run(
                ["pdfunite", *map(str, self.chunk_paths), str(self.output)],
                check=True,
            )

            # Adding metadata and outlines does not decode image streams and is
            # therefore safe even for the largest merged book.
            merged = pymupdf.open(self.output)
            merged.set_toc(self.toc, collapse=2)
            metadata = {
                "title": f"{self.course_name}严选题·答案解析合订版",
                "author": "time-tracker",
                "subject": "892电子信息严选题；题目在上，答案与解析在下",
                "keywords": f"892, 电子信息, {self.course_name}, 严选题, 答案, 解析",
                "creator": "time-tracker EI selected PDF exporter",
            }
            merged.set_metadata(metadata)
            pages = len(merged)
            finalized = self.temp_dir / "finalized.pdf"
            merged.save(finalized, garbage=1, deflate=False)
            merged.close()
            os.replace(finalized, self.output)
        return {
            "course": self.course_name,
            "questions": number,
            "pages": pages,
            "missing_answers": self.missing_answers,
            "source_page_questions": self.source_page_questions,
            "output": str(self.output),
        }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "exports" / "ei-selected-pdfs-20261029",
    )
    parser.add_argument(
        "--courses",
        nargs="+",
        choices=list(COURSES),
        default=list(COURSES),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    for key in args.courses:
        name, module, filename = COURSES[key]
        print(f"[start] {name}", flush=True)
        result = SelectedPdf(name, module, args.output_dir / filename).render()
        print(
            "[done] {course}: {questions} questions, {pages} pages, "
            "{missing_answers} missing answers -> {output}".format(**result),
            flush=True,
        )


if __name__ == "__main__":
    main()
