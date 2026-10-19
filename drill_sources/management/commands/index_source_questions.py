"""Index question locations without copying any full-page image binaries."""
import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.management.commands.import_ei_past_exam_manifest import bind_existing_scope_columns
from drill.models import Question, QuestionAsset
from drill.pdf_import import stable_question_uuid
from drill_sources.models import SourceQuestionAnchor


def child_fingerprint(source_fingerprint, key):
    return hashlib.sha256(f'ucas-source-index:v1:{source_fingerprint}:{key}'.encode()).hexdigest()


class Command(BaseCommand):
    help = 'Idempotently add independent question progress targets to existing full-paper images.'

    def add_arguments(self, parser):
        parser.add_argument('manifest', type=Path)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            data = json.loads(options['manifest'].read_text())
            if data.get('schema_version') != 1:
                raise ValueError('Unsupported source-index manifest')
            bind_existing_scope_columns()
            prepared = []; seen = set(); orders = set()
            for paper in data['papers']:
                source = Question.objects.select_related('document').get(fingerprint=paper['source_fingerprint'])
                if source.document.workspace != 'ei' or source.document.parser_strategy != 'ucas-reviewed-manifest-v1':
                    raise ValueError('Only the newly imported EI past papers may be indexed')
                assets = {a.source_id: a for a in source.assets.filter(asset_type='question_crop').defer('image_data')}
                keys = set(); positions = set()
                if not paper['items']:
                    raise ValueError('Cannot archive an empty paper index')
                for item in paper['items']:
                    fp = child_fingerprint(source.fingerprint, item['key'])
                    order = (source.document_id, item['question_order'])
                    if (fp in seen or item['key'] in keys or item['position'] in positions or order in orders
                            or item['asset_source_id'] not in assets or not 0 <= item['y'] <= 1
                            or not 0.8 <= item['confidence'] <= 1 or not item['label'].strip()):
                        raise ValueError(f'Invalid/duplicate source question: {item}')
                    seen.add(fp); keys.add(item['key']); positions.add(item['position']); orders.add(order)
                    conflicting = Question.objects.filter(document=source.document, question_order=item['question_order']).exclude(fingerprint=fp).exists()
                    if conflicting:
                        raise ValueError(f'Question order conflict: {item["question_order"]}')
                prepared.append((paper, source, assets))
            existing = set(Question.objects.filter(fingerprint__in=seen).values_list('fingerprint', flat=True))
            self.stdout.write(json.dumps({'papers': len(prepared), 'questions': len(seen), 'new': len(seen-existing), 'dry_run': options['dry_run']}))
            if options['dry_run']:
                return
            created = updated = 0
            with transaction.atomic():
                for paper, source, assets in prepared:
                    for item in paper['items']:
                        fp = child_fingerprint(source.fingerprint, item['key'])
                        legacy_label = f'{source.exam_year}年 · {item["label"]}'
                        display_label = f'{source.exam_year}年 · ' + (f'{source.exam_variant} · ' if source.exam_variant else '') + item['label']
                        defaults = {
                            'uuid': stable_question_uuid(fp), 'document': source.document,
                            'topic_id': source.topic_id, 'similarity_topic_id': source.similarity_topic_id,
                            'question_order': item['question_order'], 'subject': 'ei',
                            'source_label': f'ucas-index:{source.fingerprint}:{item["key"]}',
                            'display_label': display_label,
                            'content_mode': 'image', 'confidence': item['confidence'],
                            'source_category': 'past_exam', 'is_past_exam': True,
                            'record_kind': 'question', 'is_practiceable': True,
                            'exam_year': source.exam_year, 'exam_variant': source.exam_variant,
                            'classification_reason': 'Independent source question; full-page images shared with original paper',
                            'classification_confidence': 1,
                            'answer_source': 'source_paper_reference',
                            'question_type': item.get('question_type', 'solution'),
                            'question_type_source': 'import', 'question_type_confidence': .95,
                        }
                        if any(f.name == 'syllabus_scope' for f in Question._meta.fields):
                            defaults.update(syllabus_scope=getattr(source, 'syllabus_scope', 'uncertain'),
                                            syllabus_scope_reason=getattr(source, 'syllabus_scope_reason', '本书部分超纲。'))
                        question, new = Question.objects.get_or_create(fingerprint=fp, defaults=defaults)
                        if not new and question.display_label == legacy_label and display_label != legacy_label:
                            Question.objects.filter(pk=question.pk).update(display_label=display_label)
                        if question.document_id != source.document_id:
                            raise ValueError('Existing indexed question belongs to another document')
                        existing_anchor = SourceQuestionAnchor.objects.filter(question=question).first()
                        if existing_anchor and existing_anchor.source_question_id != source.pk:
                            raise ValueError('Existing anchor refers to a different source')
                        SourceQuestionAnchor.objects.update_or_create(question=question, defaults={
                            'source_question': source, 'asset': assets[item['asset_source_id']],
                            'key': item['key'], 'label': item['label'], 'y': item['y'],
                            'position': item['position'], 'confidence': item['confidence'],
                        })
                        created += int(new); updated += int(not new)
                    if paper.get('complete', False):
                        # Retain original images, attempts and bookmarks, but count
                        # only the independent question cells in the active bank.
                        Question.objects.filter(pk=source.pk).update(is_practiceable=False)
            self.stdout.write(json.dumps({'created': created, 'existing': updated, 'new_image_bytes': 0}))
        except (ValueError, KeyError, OSError, Question.DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
