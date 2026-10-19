"""Import reviewed UCAS past papers without replacing any existing EI records."""
import hashlib
import json
from pathlib import Path

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models, transaction

from drill.models import Question, QuestionAsset, QuestionDocument, QuestionTopic
from drill.pdf_import import stable_question_uuid, stable_source_id


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(path):
    data = json.loads(path.read_text())
    if data.get('schema_version') != 1 or data.get('workspace') != 'ei':
        raise ValueError('Unsupported manifest')
    root = path.parent.resolve()
    sources = {}
    for key, source in data['sources'].items():
        file = (root / source['file']).resolve()
        if not file.is_relative_to(root) or not file.is_file() or digest(file) != key:
            raise ValueError(f'Unsafe or corrupt source: {source["file"]}')
        sources[key] = file
    seen = set()
    docs = {key: pymupdf.open(file) for key, file in sources.items()}
    try:
        for book in data['books']:
            for q in book['questions']:
                identity = (book['key'], q['year'], q['variant'], q['key'])
                if identity in seen or not q['question_regions']:
                    raise ValueError(f'Duplicate or empty question: {identity}')
                seen.add(identity)
                for region in q['question_regions'] + q['answer_regions']:
                    page = docs[region['source']][region['page_index']]
                    rect = pymupdf.Rect(region['bbox'])
                    if rect.is_empty or rect.width < 20 or rect.height < 10 or not page.rect.contains(rect):
                        raise ValueError(f'Invalid region: {identity}')
                    if 'render_dpi' in region and not 120 <= int(region['render_dpi']) <= 360:
                        raise ValueError(f'Invalid render DPI: {identity}')
    finally:
        for doc in docs.values():
            doc.close()
    return data, sources


def fingerprint(book, question):
    identity = f'ucas-past-exams:v1:{book}:{question["year"]}:{question["variant"]}:{question["key"]}'
    return hashlib.sha256(identity.encode()).hexdigest()


def bind_existing_scope_columns():
    """Support older Docker code against the already-upgraded PostgreSQL schema.

    This only binds fields in this management-command process. It neither alters
    the schema nor changes any running web process.
    """
    definitions = {
        'syllabus_scope': lambda: models.CharField(max_length=16, default='unclassified'),
        'syllabus_scope_confidence': lambda: models.FloatField(null=True, blank=True),
        'syllabus_scope_reason': lambda: models.CharField(max_length=240, blank=True, default=''),
    }
    present = {f.name for f in Question._meta.fields}
    if set(definitions).issubset(present):
        return
    with connection.cursor() as cursor:
        columns = {c.name for c in connection.introspection.get_table_description(cursor, Question._meta.db_table)}
    for name, definition in definitions.items():
        if name in columns and name not in present:
            Question.add_to_class(name, definition())


class Command(BaseCommand):
    help = 'Add reviewed past-exam manifest; dry-run validates every source and region.'

    def add_arguments(self, parser):
        parser.add_argument('manifest', type=Path)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--dpi', type=int, default=150)

    def handle(self, *args, **options):
        try:
            data, sources = validate_manifest(options['manifest'].resolve())
            dpi = options['dpi']
            if not 120 <= dpi <= 180:
                raise ValueError('DPI must be 120..180')
            bind_existing_scope_columns()
            existing = set(Question.objects.filter(document__workspace='ei').values_list('fingerprint', flat=True))
            total = sum(len(b['questions']) for b in data['books'])
            duplicate = sum(fingerprint(b['key'], q) in existing for b in data['books'] for q in b['questions'])
            self.stdout.write(json.dumps({'total': total, 'new': total-duplicate, 'existing': duplicate,
                                          'dry_run': options['dry_run']}))
            if options['dry_run']:
                return
            docs = {key: pymupdf.open(path) for key, path in sources.items()}
            written = assets = image_bytes = 0
            try:
                with transaction.atomic():
                    for book in data['books']:
                        namespace = 'ucas-past-exams:v1:' + book['key']
                        book_hash = hashlib.sha256(namespace.encode()).hexdigest()
                        document, _ = QuestionDocument.objects.get_or_create(
                            sha256=book_hash,
                            defaults={'source_id': stable_source_id(namespace), 'workspace': 'ei',
                                      'title': book['title'], 'display_title': book['title'],
                                      'filename': str(options['manifest']),
                                      'author': '中国科学院大学',
                                      'attribution': '用户百度网盘历年真题与参考答案；原扫描件为准。部分内容超出892考纲。',
                                      'page_count': len({(r['source'], r['page_index']) for item in book['questions']
                                                         for r in item['question_regions'] + item['answer_regions']}),
                                      'parser_strategy': 'ucas-reviewed-manifest-v1', 'relation_type': 'past_exam'},
                        )
                        if document.workspace != 'ei' or document.source_id != stable_source_id(namespace):
                            raise ValueError('Existing document identity conflict')
                        for q in book['questions']:
                            fp = fingerprint(book['key'], q)
                            if fp in existing:
                                continue
                            # Fail on legacy label/order conflicts instead of overwriting user data.
                            source_label = f'ucas:{book["key"]}:{q["year"]}:{q["variant"]}:{q["key"]}'
                            if Question.objects.filter(source_label=source_label).exists():
                                raise ValueError(f'Existing question identity conflict: {source_label}')
                            topic_name = f'{q["year"]}年真题' + (f' · {q["variant"]}' if q['variant'] else '')
                            topic, _ = QuestionTopic.objects.get_or_create(
                                source_id=stable_source_id(namespace, topic_name),
                                defaults={'document': document, 'title': topic_name, 'display_title': topic_name,
                                          'normalized_title': topic_name, 'level': 1, 'sort_order': q['topic_order']},
                            )
                            fields = {'uuid': stable_question_uuid(fp), 'document': document,
                                      'topic': topic, 'similarity_topic': topic, 'question_order': q['order'],
                                      'source_label': source_label, 'display_label': q['display_label'],
                                      'subject': 'ei', 'content_mode': 'image', 'confidence': q['confidence'],
                                      'source_category': 'past_exam', 'is_past_exam': True,
                                      'record_kind': q['record_kind'], 'is_practiceable': True,
                                      'classification_reason': 'UCAS original past exam; may exceed 892 syllabus',
                                      'classification_confidence': 1, 'exam_year': q['year'],
                                      'exam_variant': q['variant'][:16],
                                      'answer_source': 'original_pdf' if q['answer_regions'] else '',
                                      'answer_markdown': q.get('answer_note', ''),
                                      'answer_confidence': q['confidence'] if q['answer_regions'] else None,
                                      'question_type': q.get('question_type', 'solution'),
                                      'question_type_source': 'import', 'question_type_confidence': .95}
                            if any(f.name == 'syllabus_scope' for f in Question._meta.fields):
                                fields.update(syllabus_scope=q.get('syllabus_scope', 'uncertain'),
                                              syllabus_scope_confidence=q.get('scope_confidence'),
                                              syllabus_scope_reason=q.get('scope_reason', '完整收录真题；本书部分超纲，未逐题核定。'))
                            question = Question.objects.create(fingerprint=fp, **fields)
                            for asset_type, regions in [('question_crop', q['question_regions']), ('answer_crop', q['answer_regions'])]:
                                for position, region in enumerate(regions):
                                    page = docs[region['source']][region['page_index']]
                                    rect = pymupdf.Rect(region['bbox'])
                                    region_dpi = int(region.get('render_dpi', dpi))
                                    pix = page.get_pixmap(dpi=region_dpi, clip=rect, colorspace=pymupdf.csGRAY, alpha=False)
                                    png = pix.tobytes('png')
                                    image_hash = hashlib.sha256(png).hexdigest()
                                    _, created = QuestionAsset.objects.get_or_create(
                                        question=question, sha256=image_hash,
                                        defaults={'source_id': stable_source_id(fp, asset_type, position),
                                                  'asset_type': asset_type, 'position': position,
                                                  'image_data': png, 'width': pix.width, 'height': pix.height,
                                                  'source_page_index': region['page_index'],
                                                  'source_x0': rect.x0, 'source_y0': rect.y0,
                                                  'source_x1': rect.x1, 'source_y1': rect.y1, 'render_dpi': region_dpi},
                                    )
                                    if created:
                                        assets += 1
                                        image_bytes += len(png)
                            written += 1
                            existing.add(fp)
            finally:
                for doc in docs.values():
                    doc.close()
            self.stdout.write(json.dumps({'written': written, 'assets': assets, 'image_bytes': image_bytes}))
        except (ValueError, KeyError, OSError, IndexError) as exc:
            raise CommandError(str(exc)) from exc
