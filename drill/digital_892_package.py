"""Portable, checked 892 digital PDF crops and idempotent EI database import."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pymupdf
from django.db import connection, transaction

from drill.models import Question, QuestionAsset, QuestionDocument, QuestionTopic
from drill.pdf_import import stable_question_uuid, stable_source_id

SCHEMA_VERSION = 1
TOPICS = {
    'digital_math': '数字电路的数学基础',
    'cmos_gates': 'CMOS 门电路',
    'combinational_logic': '组合逻辑电路分析与设计',
    'semiconductor_storage': '半导体存储电路基础',
    'sequential_logic': '时序逻辑电路分析与设计',
}
COMMUNICATION_TOPICS = {
    'communication_basics': '通信系统基础',
    'analog_modulation': '模拟调制系统',
    'digital_baseband': '数字基带传输系统',
    'digital_passband': '数字带通传输系统',
    'optimal_reception': '数字信号的最佳接收',
}
CIRCUIT_TOPICS = {
    'circuit_laws': '电路模型和电路定律',
    'resistive_equivalence': '电阻电路等效变换',
    'resistive_networks': '电阻电路一般分析方法与网络定理',
    'dynamics_time': '动态电路的时域分析',
    'sinusoidal_steady_state': '正弦稳态电路分析',
}
SIGNAL_TOPICS = {
    'signal_overview': '信号与系统理论概述',
    'time_domain': '连续时间与离散时间系统的时域分析',
    'fourier': '傅里叶变换及其应用',
    'laplace': '拉氏变换与连续时间系统的 s 域分析',
    'z_transform': 'z 变换与离散时间系统的 z 域分析',
}
BANKS = {
    'digital_electronics': {
        'prefix': 'ei-digital-892', 'topics': TOPICS,
        'title': '892 · 数字电子技术课后题（考纲筛选）',
        'display_title': '892 · 数电课后题', 'relation_type': 'paired_pdf',
        'source_label_prefix': 'digital',
    },
    'communication_principles': {
        'prefix': 'ei-communication-892', 'topics': COMMUNICATION_TOPICS,
        'title': '892 · 通信原理课后题（考纲筛选）',
        'display_title': '892 · 通信课后题', 'relation_type': 'single_pdf',
        'source_label_prefix': 'communication',
    },
    'circuit_theory': {
        'prefix': 'ei-circuit-892-docx', 'topics': CIRCUIT_TOPICS,
        'title': '892 · 邱关源《电路》课后题（考纲筛选）',
        'display_title': '892 · 电路课后题', 'relation_type': 'docx_pdf',
        'source_label_prefix': 'circuit_docx',
    },
    'signals_and_systems': {
        'prefix': 'ei-signal-892-paired-v1', 'topics': SIGNAL_TOPICS,
        'title': '892 · 信号与系统课后题（考纲筛选）',
        'display_title': '892 · 信号课后题', 'relation_type': 'paired_pdf',
        'source_label_prefix': 'signal_paired',
    },
}


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def question_fingerprint(source_hash, label, subject='digital_electronics'):
    return hashlib.sha256(f'{BANKS[subject]["prefix"]}:{source_hash}:{label}'.encode()).hexdigest()


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def _safe_file(root, name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError(f'Unsafe package path: {name}')
    return root / relative


def build_package(manifest_path, target, package_version, dpi=150):
    if not 100 <= dpi <= 200:
        raise ValueError('DPI must be 100..200')
    manifest = json.loads(Path(manifest_path).read_text())
    if manifest['manifest_version'] != 1:
        raise ValueError('Unsupported source manifest version')
    subject = manifest.get('subject', 'digital_electronics')
    bank = BANKS.get(subject)
    if bank is None:
        raise ValueError(f'Unsupported subject: {subject}')
    source, answer = Path(manifest['source_pdf']), Path(manifest['answer_pdf'])
    if digest(source) != manifest['document_sha256'] or digest(answer) != manifest['answer_sha256']:
        raise ValueError('Source PDF checksum mismatch')
    if target.exists() and any(target.iterdir()):
        raise ValueError(f'Package directory is not empty: {target}')
    target.mkdir(parents=True, exist_ok=True)
    assets_root = target / 'assets'
    assets_root.mkdir()
    shutil.copyfile(source, target / 'source.pdf')
    shutil.copyfile(answer, target / 'answer.pdf')
    original_docx = manifest.get('original_docx')
    if original_docx:
        if digest(original_docx) != manifest['original_docx_sha256']:
            raise ValueError('Original DOCX checksum mismatch')
        shutil.copyfile(original_docx, target / 'source.docx')
    selected = [
        question for question in manifest['questions']
        if question['scope'] == 'IN_SCOPE' and not question['review_flags']
        and question['segmentation_confidence'] >= 0.8
        and question['question_regions'] and question['solution_regions']
    ]
    if not selected:
        raise ValueError('No reviewed, paired in-scope questions')
    records = []
    seen = set()
    with pymupdf.open(source) as source_doc, pymupdf.open(answer) as answer_doc:
        for question in selected:
            label = question['source_label']
            if label in seen or question['scope_topic'] not in bank['topics']:
                raise ValueError(f'Duplicate label or unknown topic: {label}')
            seen.add(label)
            fp = question_fingerprint(manifest['document_sha256'], label, subject)
            record = {
                'source_label': label,
                'chapter': question['chapter'],
                'scope_topic': question['scope_topic'],
                'scope': 'IN_SCOPE',
                'fingerprint': fp,
                'uuid': str(stable_question_uuid(fp)),
                'question_order': question['chapter'] * 1000 + int(re.split(r'[.-]', label)[1]),
                'regions': [],
            }
            for key, document, asset_type in (
                ('question_regions', source_doc, 'question_crop'),
                ('solution_regions', answer_doc, 'answer_crop'),
            ):
                for position, region in enumerate(question[key]):
                    page_index = region['page_index']
                    if page_index < 0 or page_index >= len(document):
                        raise ValueError(f'{label}: page index outside source')
                    page = document[page_index]
                    rect = pymupdf.Rect(region['bbox'])
                    if (rect.is_empty or rect.x0 < -0.01 or rect.y0 < -0.01
                            or rect.x1 > page.rect.width + 0.01 or rect.y1 > page.rect.height + 0.01
                            or rect.width < 12 or rect.height < 12):
                        raise ValueError(f'{label}: invalid region bbox')
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), clip=rect, alpha=False)
                    image = pix.tobytes('png')
                    asset_name = f'assets/{label}-{asset_type}-{position}.png'
                    (target / asset_name).write_bytes(image)
                    record['regions'].append({
                        'asset_type': asset_type, 'position': position,
                        'page_index': page_index, 'bbox': [round(value, 3) for value in rect],
                        'confidence': region['confidence'],
                        'image_file': asset_name, 'image_sha256': hashlib.sha256(image).hexdigest(),
                        'width': pix.width, 'height': pix.height, 'render_dpi': dpi,
                    })
            records.append(record)
    package_manifest = {
        'schema_version': SCHEMA_VERSION, 'package_version': package_version,
        'subject': subject, 'workspace': 'ei',
        'question_pdf_sha256': manifest['document_sha256'],
        'answer_pdf_sha256': manifest['answer_sha256'],
        'original_docx_sha256': manifest.get('original_docx_sha256', ''),
        'syllabus_sha256': manifest['syllabus_sha256'],
        'review_overrides_sha256': manifest.get('review_overrides_sha256', ''),
        'question_pdf_pages': manifest['source_pages'],
        'answer_pdf_pages': manifest['answer_pages'],
        'topics': bank['topics'], 'questions': records,
    }
    _write_json(target / 'manifest.json', package_manifest)
    _write_json(target / 'metadata.json', {
        'title': bank['title'],
        'question_count': len(records), 'asset_count': sum(len(r['regions']) for r in records),
        'selection': 'Only reviewed IN_SCOPE questions with complete question and solution crops',
    })
    _write_json(target / 'import_version.json', {'schema_version': SCHEMA_VERSION, 'package_version': package_version})
    files = sorted(path for path in target.rglob('*') if path.is_file() and path.name != 'checksums.txt')
    (target / 'checksums.txt').write_text(''.join(f'{digest(path)}  {path.relative_to(target)}\n' for path in files))
    validate_package(target)
    return package_manifest


def validate_package(root):
    root = Path(root)
    version = json.loads((root / 'import_version.json').read_text())
    manifest = json.loads((root / 'manifest.json').read_text())
    metadata = json.loads((root / 'metadata.json').read_text())
    if version != {'schema_version': SCHEMA_VERSION, 'package_version': manifest['package_version']}:
        raise ValueError('Package version mismatch')
    subject = manifest.get('subject')
    bank = BANKS.get(subject)
    if manifest['schema_version'] != SCHEMA_VERSION or manifest['workspace'] != 'ei' or bank is None:
        raise ValueError('Unsupported package schema or workspace')
    if manifest['topics'] != bank['topics']:
        raise ValueError('Package topics do not match subject')
    lines = (root / 'checksums.txt').read_text().splitlines()
    checksums = {}
    for line in lines:
        expected, name = line.split('  ', 1)
        if name in checksums:
            raise ValueError(f'Duplicate checksum entry: {name}')
        checksums[name] = expected
    actual_files = {str(path.relative_to(root)) for path in root.rglob('*') if path.is_file() and path.name != 'checksums.txt'}
    if actual_files != set(checksums):
        raise ValueError('Package file list differs from checksums.txt')
    for name, expected in checksums.items():
        if digest(_safe_file(root, name)) != expected:
            raise ValueError(f'Checksum mismatch: {name}')
    if digest(root / 'source.pdf') != manifest['question_pdf_sha256'] or digest(root / 'answer.pdf') != manifest['answer_pdf_sha256']:
        raise ValueError('PDF SHA256 mismatch')
    if manifest.get('original_docx_sha256') and digest(root / 'source.docx') != manifest['original_docx_sha256']:
        raise ValueError('DOCX SHA256 mismatch')
    if len(manifest['questions']) != metadata['question_count']:
        raise ValueError('Question count mismatch')
    labels = set()
    for question in manifest['questions']:
        label = question['source_label']
        if label in labels or question['scope'] != 'IN_SCOPE' or question['scope_topic'] not in bank['topics']:
            raise ValueError(f'Invalid or repeated question: {label}')
        labels.add(label)
        fp = question_fingerprint(manifest['question_pdf_sha256'], label, subject)
        if question['fingerprint'] != fp or question['uuid'] != str(stable_question_uuid(fp)):
            raise ValueError(f'Question identity mismatch: {label}')
        types = {region['asset_type'] for region in question['regions']}
        if types != {'question_crop', 'answer_crop'}:
            raise ValueError(f'Missing question or answer asset: {label}')
        for region in question['regions']:
            if digest(_safe_file(root, region['image_file'])) != region['image_sha256']:
                raise ValueError(f'Asset hash mismatch: {label}')
            x0, y0, x1, y1 = region['bbox']
            if not 0 <= x0 < x1 or not 0 <= y0 < y1 or region['width'] < 10 or region['height'] < 10:
                raise ValueError(f'Invalid asset geometry: {label}')
    return manifest


def inspect_db_conflicts(manifest):
    source_hash = manifest['question_pdf_sha256']
    prefix = BANKS[manifest['subject']]['prefix']
    document_id = stable_source_id(f'{prefix}-document', source_hash)
    existing_id = QuestionDocument.objects.filter(source_id=document_id).first()
    existing_hash = QuestionDocument.objects.filter(sha256=source_hash).first()
    if existing_id and existing_id.sha256 != source_hash:
        raise ValueError('QuestionDocument source_id collision')
    if existing_hash and (existing_hash.source_id != document_id or existing_hash.workspace != 'ei'):
        raise ValueError('QuestionDocument SHA256 belongs to another source')
    new = updated = 0
    for record in manifest['questions']:
        current = Question.objects.filter(fingerprint=record['fingerprint']).first()
        if current:
            if str(current.uuid) != record['uuid'] or current.document.sha256 != source_hash:
                raise ValueError(f"Question fingerprint/UUID conflict: {record['source_label']}")
            updated += 1
        else:
            if Question.objects.filter(uuid=record['uuid']).exists():
                raise ValueError(f"Question UUID collision: {record['source_label']}")
            new += 1
    return {'new': new, 'updated': updated}


def _legacy_scope_columns():
    """Detect scope columns left in databases by older EI deployments."""
    with connection.cursor() as cursor:
        columns = {
            column.name for column in connection.introspection.get_table_description(
                cursor, Question._meta.db_table,
            )
        }
    model_columns = {field.column for field in Question._meta.concrete_fields}
    extra = {'syllabus_scope', 'syllabus_scope_reason'} - model_columns
    present = extra & columns
    if present and present != extra:
        raise ValueError('Incomplete legacy syllabus scope columns')
    return bool(present)


def _create_question(record, defaults, legacy_scope):
    values = {
        **defaults, 'fingerprint': record['fingerprint'],
        'uuid': record['uuid'], 'subject': 'ei',
    }
    if not legacy_scope:
        return Question.objects.create(**values)
    # The VPS has two required scope columns absent from this checkout's model.
    # Supply them on INSERT without changing the production schema or other rows.
    question = Question(**values)
    fields = [field for field in Question._meta.concrete_fields if not field.primary_key]
    names = [field.column for field in fields] + ['syllabus_scope', 'syllabus_scope_reason']
    params = [
        field.get_db_prep_save(getattr(question, field.attname), connection)
        for field in fields
    ] + ['in_scope', 'Official 892 syllabus; locally reviewed crops.']
    quote = connection.ops.quote_name
    columns = ', '.join(quote(name) for name in names)
    placeholders = ', '.join(['%s'] * len(params))
    with connection.cursor() as cursor:
        cursor.execute(
            f'INSERT INTO {quote(Question._meta.db_table)} ({columns}) '
            f'VALUES ({placeholders}) RETURNING {quote(Question._meta.pk.column)}',
            params,
        )
        question.pk = cursor.fetchone()[0]
    question._state.adding = False
    question._state.db = connection.alias
    return question


def import_package(root, dry_run=False):
    root = Path(root).resolve()
    manifest = validate_package(root)
    summary = inspect_db_conflicts(manifest)
    legacy_scope = _legacy_scope_columns()
    if dry_run:
        return {**summary, 'assets': sum(len(q['regions']) for q in manifest['questions']), 'written': False}
    source_hash = manifest['question_pdf_sha256']
    bank = BANKS[manifest['subject']]
    prefix = bank['prefix']
    with transaction.atomic():
        document, _ = QuestionDocument.objects.get_or_create(
            sha256=source_hash,
            defaults={
                'source_id': stable_source_id(f'{prefix}-document', source_hash),
                'workspace': 'ei', 'filename': str(root / 'source.pdf'),
                'title': bank['title'],
                'display_title': bank['display_title'],
                'page_count': manifest['question_pdf_pages'],
                'parser_strategy': manifest['package_version'],
                'relation_type': bank['relation_type'],
            },
        )
        topic_cache = {}
        for order, (topic_key, title) in enumerate(bank['topics'].items(), 1):
            topic, _ = QuestionTopic.objects.update_or_create(
                source_id=stable_source_id(f'{prefix}-topic', source_hash, topic_key),
                defaults={
                    'document': document, 'parent': None, 'title': title,
                    'display_title': title, 'normalized_title': topic_key,
                    'level': 1, 'sort_order': order,
                },
            )
            topic_cache[topic_key] = topic
        for record in manifest['questions']:
            topic = topic_cache[record['scope_topic']]
            defaults = {
                'document': document, 'topic': topic, 'similarity_topic': topic,
                'subject': 'ei',
                'question_order': record['question_order'],
                'source_label': f"{bank['source_label_prefix']} · {record['source_label']}",
                'display_label': f"课后题 {record['source_label']}",
                'prompt_text': '', 'latex_text': '', 'content_mode': 'image',
                'confidence': 1.0, 'source_category': 'workbook',
                'record_kind': 'question', 'is_practiceable': True,
                'classification_reason': 'Official 892 syllabus; locally reviewed PDF crops.',
                'classification_confidence': 1.0,
                'topic_classification_source': 'human',
                'topic_classification_confidence': 1.0,
            }
            question = Question.objects.filter(fingerprint=record['fingerprint']).first()
            if question is None:
                question = _create_question(record, defaults, legacy_scope)
            else:
                for key, value in defaults.items():
                    setattr(question, key, value)
                question.save(update_fields=list(defaults))
            wanted_ids = []
            for region in record['regions']:
                kind = region['asset_type']
                position = region['position']
                asset_id = stable_source_id(f'{prefix}-asset', record['fingerprint'], kind, position)
                old = QuestionAsset.objects.filter(source_id=asset_id).first()
                if old and old.question_id != question.pk:
                    raise ValueError(f'QuestionAsset source_id collision: {asset_id}')
                if old and old.sha256 != region['image_sha256'] and old.revision_links.exists():
                    raise ValueError(f'Pinned asset cannot be changed: {asset_id}')
                rect = region['bbox']
                asset, _ = QuestionAsset.objects.update_or_create(
                    source_id=asset_id,
                    defaults={
                        'question': question, 'position': position, 'asset_type': kind,
                        'sha256': region['image_sha256'], 'mime_type': 'image/png',
                        'image_data': _safe_file(root, region['image_file']).read_bytes(),
                        'width': region['width'], 'height': region['height'],
                        'source_page_index': region['page_index'],
                        'source_x0': rect[0], 'source_y0': rect[1],
                        'source_x1': rect[2], 'source_y1': rect[3],
                        'render_dpi': region['render_dpi'],
                    },
                )
                wanted_ids.append(asset.pk)
            obsolete = QuestionAsset.objects.filter(question=question).exclude(pk__in=wanted_ids)
            if any(asset.revision_links.exists() for asset in obsolete):
                raise ValueError(f"Pinned obsolete asset cannot be removed: {record['source_label']}")
            obsolete.delete()
        document.parser_strategy = manifest['package_version']
        document.save(update_fields=['parser_strategy'])
    return {**summary, 'assets': sum(len(q['regions']) for q in manifest['questions']), 'written': True}
