import hashlib
import json
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.cleaning import classify_source_with_context
from drill.linear_selected import RELATION, STRATEGY, TITLE, parse_selected_book
from drill.models import Question, QuestionAsset, QuestionDocument, QuestionTopic
from drill.pdf_import import stable_question_uuid, stable_source_id
from drill_sources.models import SourceQuestionAnchor


def fingerprint(sha256, kind, number):
    return hashlib.sha256(f'linear-selected:v1:{sha256}:{kind}:{number}'.encode()).hexdigest()


class Command(BaseCommand):
    help = 'Import bookmarked A4 linear selected questions, sharing full-page images without tight crops.'

    def add_arguments(self, parser):
        parser.add_argument('pdf', type=Path)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--manifest-output', type=Path)
        parser.add_argument('--dpi', type=int, default=150)

    def handle(self, *args, **options):
        if not 120 <= options['dpi'] <= 200:
            raise CommandError('DPI must be between 120 and 200')
        try:
            book = parse_selected_book(options['pdf'])
        except (OSError, ValueError, pymupdf.FileDataError) as error:
            raise CommandError(str(error)) from error
        manifest = book.manifest()
        if options['manifest_output']:
            options['manifest_output'].write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        self.stdout.write(json.dumps({key: value for key, value in manifest.items()
                                     if key not in ('topics', 'questions')}, ensure_ascii=False))
        if options['dry_run']:
            self.stdout.write('Dry run: no database writes.')
            return
        created_questions = created_assets = image_bytes = 0
        with transaction.atomic(), pymupdf.open(book.path) as pdf:
            document, _ = QuestionDocument.objects.get_or_create(sha256=book.sha256, defaults={
                'source_id': stable_source_id('linear-selected-document', book.sha256),
                'workspace': 'drill', 'filename': book.path.name,
                'title': TITLE, 'display_title': TITLE,
                'attribution': 'Owner-supplied 大观线代臻选题；保留原始 PDF 题号、题源和完整页面。',
                'page_count': book.page_count, 'parser_strategy': STRATEGY, 'relation_type': RELATION,
            })
            if document.workspace != 'drill' or document.parser_strategy != STRATEGY:
                raise CommandError('Existing document belongs to another import profile; refusing to overwrite it')
            topics = {}
            for item in book.topics:
                topic, _ = QuestionTopic.objects.get_or_create(
                    source_id=stable_source_id('linear-selected-topic', book.sha256, item.order),
                    defaults={'document': document, 'parent': topics.get(item.parent_order),
                              'title': item.title, 'display_title': item.title,
                              'normalized_title': item.title, 'level': item.level, 'sort_order': item.order})
                if topic.document_id != document.pk:
                    raise CommandError('Topic source ID collision')
                topics[item.order] = topic
            parents = {}; assets = {}
            for item in book.questions:
                if item.page_index not in parents:
                    page = pdf[item.page_index]
                    source_fp = fingerprint(book.sha256, 'page', item.page_index)
                    parent, _ = Question.objects.get_or_create(fingerprint=source_fp, defaults={
                        'uuid': stable_question_uuid(source_fp), 'document': document,
                        'topic': topics[item.topic_order], 'subject': 'math2',
                        'question_order': 1_000_000 + item.page_index,
                        'source_label': f'linear-selected-page:{book.sha256[:12]}:{item.page_index + 1}',
                        'display_label': f'臻选原页 · PDF {item.page_index + 1}',
                        'content_mode': 'image', 'source_category': 'workbook',
                        'record_kind': 'grouped', 'is_practiceable': False,
                    })
                    source_id = stable_source_id('linear-selected-page-asset', book.sha256, item.page_index)
                    asset = QuestionAsset.objects.filter(source_id=source_id).defer('image_data').first()
                    if asset is None:
                        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(options['dpi'] / 72, options['dpi'] / 72), alpha=False)
                        binary = pixmap.tobytes('png')
                        asset = QuestionAsset.objects.create(source_id=source_id, question=parent,
                            position=0, asset_type='question_crop', sha256=hashlib.sha256(binary).hexdigest(),
                            image_data=binary, width=pixmap.width, height=pixmap.height,
                            source_page_index=item.page_index, source_x0=page.rect.x0, source_y0=page.rect.y0,
                            source_x1=page.rect.x1, source_y1=page.rect.y1, render_dpi=options['dpi'])
                        created_assets += 1; image_bytes += len(binary)
                    if asset.question_id != parent.pk or asset.render_dpi != options['dpi']:
                        raise CommandError('Existing page asset/profile conflict; use rerender tooling rather than overwriting')
                    parents[item.page_index] = parent; assets[item.page_index] = asset
                fp = fingerprint(book.sha256, 'question', item.number)
                source = classify_source_with_context(item.source, topics[item.topic_order].title)
                question, new = Question.objects.get_or_create(fingerprint=fp, defaults={
                    'uuid': stable_question_uuid(fp), 'document': document,
                    'topic': topics[item.topic_order], 'similarity_topic': topics[item.topic_order],
                    'subject': 'math2', 'question_order': item.number,
                    'source_label': f'linear-selected:{item.number:03d} · {item.source}',
                    'display_label': f'臻选 #{item.number:03d} · {item.source}',
                    'prompt_text': '', 'content_mode': 'image', 'confidence': 1,
                    'source_category': source.category, 'is_past_exam': source.is_past_exam,
                    'classification_reason': source.reason, 'classification_confidence': source.confidence,
                    'exam_year': source.year, 'exam_variant': source.variant,
                    'record_kind': 'question', 'is_practiceable': True,
                    'question_type': item.question_type, 'question_type_source': 'rule',
                    'question_type_confidence': .9 if item.question_type != 'unknown' else None,
                })
                if question.document_id != document.pk:
                    raise CommandError('Question fingerprint collision')
                anchor, _ = SourceQuestionAnchor.objects.get_or_create(question=question, defaults={
                    'source_question': parents[item.page_index], 'asset': assets[item.page_index],
                    'key': f'question-{item.number}', 'label': f'#{item.number:03d}',
                    'position': item.number, 'y': item.y, 'confidence': 1,
                })
                if anchor.source_question_id != parents[item.page_index].pk:
                    raise CommandError('Existing question anchor belongs to another source page')
                created_questions += int(new)
        self.stdout.write(json.dumps({'document_id': document.pk, 'created_questions': created_questions,
            'created_page_images': created_assets, 'new_image_bytes': image_bytes,
            'questions': len(book.questions), 'answers_imported': 0}, ensure_ascii=False))
