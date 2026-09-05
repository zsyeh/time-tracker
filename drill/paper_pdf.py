"""Regenerable PDF presentation for persisted exam papers."""

import io
import re

import pymupdf


A4 = (595, 842)
MARGIN = 42
CONTENT_WIDTH = A4[0] - MARGIN * 2


def plain_markdown(value):
    """Keep TeX source readable while removing Markdown-only decoration."""
    text = re.sub(r'```(?:\w+)?\n(.*?)```', r'\1', value or '', flags=re.S)
    text = re.sub(r'!\[[^]]*]\([^)]*\)', '[image]', text)
    text = re.sub(r'\[([^]]+)]\([^)]+\)', r'\1', text)
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.M)
    text = re.sub(r'[*_~`]+', '', text)
    return text.strip()


class PaperPdfRenderer:
    def __init__(self, paper, *, solutions=False):
        self.paper = paper
        self.solutions = solutions
        self.document = pymupdf.open()

    def render(self):
        self.cover_page()
        for item in self.paper.items.all():
            self.question_pages(item)
            if self.solutions:
                self.solution_pages(item)
        output = io.BytesIO()
        self.document.save(output, garbage=3, deflate=True)
        self.document.close()
        return output.getvalue()

    def cover_page(self):
        page = self.document.new_page(width=A4[0], height=A4[1])
        page.insert_text((MARGIN, 120), self.paper.blueprint.title, fontsize=20, fontname='helv')
        subtitle = (
            f'{self.paper.blueprint.duration_minutes} minutes  |  '
            f'{self.paper.blueprint.total_score} points  |  '
            f'{self.paper.items.count()} questions'
        )
        page.insert_text((MARGIN, 148), subtitle, fontsize=10, color=(0.3, 0.3, 0.3))
        kind = 'Solutions and review' if self.solutions else 'Question paper'
        page.insert_text((MARGIN, 180), kind, fontsize=12, color=(0.15, 0.15, 0.15))
        page.insert_text((MARGIN, 780), f'Paper {self.paper.uuid}', fontsize=7, color=(0.5, 0.5, 0.5))

    def new_content_page(self, item, label):
        page = self.document.new_page(width=A4[0], height=A4[1])
        page.insert_text(
            (MARGIN, 34),
            f'{item.position}. {label}  [{item.score} pts]',
            fontsize=9, fontname='helv', color=(0.25, 0.25, 0.25),
        )
        page.draw_line((MARGIN, 43), (A4[0] - MARGIN, 43), color=(0.8, 0.8, 0.8), width=0.5)
        return page, 56.0

    def add_text(self, page, y, text, *, fontsize=9.5):
        if not text:
            return y
        lines = max(1, len(text) // 48 + text.count('\n') + 1)
        height = min(A4[1] - MARGIN - y, max(42, lines * fontsize * 1.55))
        page.insert_textbox(
            pymupdf.Rect(MARGIN, y, A4[0] - MARGIN, y + height),
            text, fontsize=fontsize, fontname='china-s', lineheight=1.35,
            color=(0.08, 0.08, 0.08),
        )
        return y + height + 10

    def add_assets(self, item, assets, label):
        page, y = self.new_content_page(item, label)
        if not assets:
            return page, y
        for index, asset in enumerate(assets):
            available_height = A4[1] - MARGIN - y
            ratio = min(CONTENT_WIDTH / asset.width, available_height / asset.height, 1.0)
            if ratio * asset.height < 100 and y > 80:
                page, y = self.new_content_page(item, f'{label} · continued')
                available_height = A4[1] - MARGIN - y
                ratio = min(CONTENT_WIDTH / asset.width, available_height / asset.height, 1.0)
            width = asset.width * ratio
            height = asset.height * ratio
            x = MARGIN + (CONTENT_WIDTH - width) / 2
            page.insert_image(
                pymupdf.Rect(x, y, x + width, y + height),
                stream=bytes(asset.image_data), keep_proportion=True,
            )
            y += height + 8
            if index < len(assets) - 1 and A4[1] - MARGIN - y < 100:
                page, y = self.new_content_page(item, f'{label} · continued')
        return page, y

    def question_pages(self, item):
        revision = item.question_revision
        assets = [
            link.asset for link in revision.revision_assets.all()
            if link.asset_type == 'question_crop'
        ]
        page, y = self.add_assets(item, assets, 'Question')
        if not assets:
            y = self.add_text(page, y, revision.prompt_text or revision.source_label)
        if not self.solutions:
            answer_height = 34 if revision.question_type == 'single_choice' else (
                60 if revision.question_type == 'fill_blank' else 150
            )
            if y + answer_height > A4[1] - MARGIN:
                page, y = self.new_content_page(item, 'Answer space')
            for line_y in range(round(y + 20), round(min(A4[1] - MARGIN, y + answer_height)), 24):
                page.draw_line(
                    (MARGIN, line_y), (A4[0] - MARGIN, line_y),
                    color=(0.88, 0.88, 0.88), width=0.4,
                )

    def solution_pages(self, item):
        revision = item.question_revision
        assets = [
            link.asset for link in revision.revision_assets.all()
            if link.asset_type == 'answer_crop'
        ]
        page, y = self.add_assets(item, assets, 'Answer / explanation')
        if revision.answer_markdown:
            if y > A4[1] - 180:
                page, y = self.new_content_page(item, 'Explanation · continued')
            self.add_text(page, y, plain_markdown(revision.answer_markdown), fontsize=8.5)
        elif not assets:
            self.add_text(page, y, 'No source answer is currently available.')


def render_paper_pdf(paper, *, solutions=False):
    return PaperPdfRenderer(paper, solutions=solutions).render()
