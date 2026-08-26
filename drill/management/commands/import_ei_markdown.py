import hashlib
import re
import uuid
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionDocument, QuestionTopic


DOCUMENT_SOURCE_ID = 892_000_000
SOURCE_ID_BASE = 892_000_000_000
HEADING_RE = re.compile(r'^(#{2,4})\s+(.+?)\s*$', re.MULTILINE)


def stable_uuid(problem_id):
    return uuid.uuid5(uuid.NAMESPACE_URL, f'https://ei.ehzsy.site/questions/{problem_id}')


def field(block, name):
    match = re.search(rf'^-\s+`{re.escape(name)}`:\s+`([^`]+)`', block, re.MULTILINE)
    return match.group(1).strip() if match else ''


def section(block, start, end=None):
    marker = f'**{start}**'
    if marker not in block:
        return ''
    value = block.split(marker, 1)[1]
    if end and f'**{end}**' in value:
        value = value.split(f'**{end}**', 1)[0]
    return value.strip().strip('-').strip()


def short_label(code, prompt):
    plain = re.sub(r'\s+', ' ', prompt).strip()
    return f'{code}｜{plain[:72]}{"…" if len(plain) > 72 else ""}'


class Command(BaseCommand):
    help = 'Idempotently import the 892 electronic-information Markdown question bank.'

    def add_arguments(self, parser):
        parser.add_argument('markdown_path', type=Path)

    def handle(self, *args, **options):
        path = options['markdown_path'].expanduser().resolve()
        try:
            source = path.read_text(encoding='utf-8')
        except OSError as exc:
            raise CommandError(f'Cannot read {path}: {exc}') from exc
        records = self.parse(source)
        base_count = sum(item['kind'] == 'base' for item in records)
        short_count = sum(item['kind'] == 'short' for item in records)
        if (base_count, short_count) != (156, 60):
            raise CommandError(
                f'Expected 156 base and 60 short-answer questions; found {base_count} and {short_count}.'
            )
        with transaction.atomic():
            document, _ = QuestionDocument.objects.update_or_create(
                source_id=DOCUMENT_SOURCE_ID,
                defaults={
                    'workspace': 'ei',
                    'filename': path.name,
                    'title': '892 电子信息专业综合',
                    'display_title': '892 电子信息专业综合基础题库',
                    'author': '',
                    'attribution': 'Imported from the owner-provided Markdown question bank.',
                    'sha256': hashlib.sha256(source.encode('utf-8')).hexdigest(),
                    'page_count': 0,
                    'parser_strategy': 'structured_markdown_v1',
                    'relation_type': 'question_answer_pairs',
                },
            )
            topics = self.import_topics(document, records)
            imported = self.import_questions(document, records, topics)
        self.stdout.write(self.style.SUCCESS(
            f'EI question bank ready: {len(topics)} topics and {imported} questions '
            f'({base_count} base, {short_count} short-answer).'
        ))

    def parse(self, source):
        headings = list(HEADING_RE.finditer(source))
        major = ''
        group = ''
        short_mode = False
        records = []
        for index, match in enumerate(headings):
            level = len(match.group(1))
            title = match.group(2).strip()
            end = headings[index + 1].start() if index + 1 < len(headings) else len(source)
            block = source[match.end():end].strip()
            if level == 2:
                if title.startswith('简答题扩充题库'):
                    short_mode = True
                    major = ''
                    group = ''
                elif re.match(r'^\d+\.\s+', title):
                    major = re.sub(r'^\d+\.\s*', '', title).strip()
                    group = ''
                    short_mode = False
                continue
            if level == 3:
                if short_mode and re.match(r'^\d+\.\s+', title):
                    major = re.sub(r'^\d+\.\s*', '', title)
                    major = re.sub(r'简答题(?:（.*?）)?$', '', major).strip()
                    group = f'{major} · 简答题'
                elif not title.startswith('Agent '):
                    group = title
                continue
            if level != 4 or not major:
                continue
            if short_mode:
                code = field(block, 'short_id') or title.split('｜', 1)[0].strip()
                prompt = section(block, '简答题', '参考答案')
                answer = section(block, '参考答案', '建议评分点')
                kp_ids = [item.strip() for item in field(block, 'kp_ids').split(',') if item.strip()]
                if not code or not prompt or not answer:
                    raise CommandError(f'Incomplete short-answer record: {title}')
                records.append({
                    'kind': 'short', 'code': code, 'kp_id': kp_ids[0] if kp_ids else '',
                    'major': major, 'group': group, 'title': short_label(code, prompt),
                    'prompt': prompt, 'answer': answer,
                })
            else:
                kp_id = field(block, 'kp_id') or title.split('｜', 1)[0].strip()
                problem_id = field(block, 'problem_id') or f'{kp_id}-P01'
                prompt = section(block, '基础例题', '参考答案')
                answer = section(block, '参考答案')
                display_title = title.split('｜', 1)[1].strip() if '｜' in title else title
                if not kp_id or not prompt or not answer:
                    raise CommandError(f'Incomplete base record: {title}')
                records.append({
                    'kind': 'base', 'code': problem_id, 'kp_id': kp_id,
                    'major': major, 'group': group, 'title': display_title,
                    'prompt': prompt, 'answer': answer,
                })
        return records

    def import_topics(self, document, records):
        ordered = []
        seen = set()
        for record in records:
            for key, title, level, parent_key in (
                (f'major:{record["major"]}', record['major'], 1, None),
                (f'group:{record["group"]}', record['group'], 2, f'major:{record["major"]}'),
            ):
                if key not in seen:
                    seen.add(key)
                    ordered.append((key, title, level, parent_key))
            if record['kind'] == 'base':
                key = f'kp:{record["kp_id"]}'
                if key not in seen:
                    seen.add(key)
                    ordered.append((key, record['title'], 3, f'group:{record["group"]}'))
        result = {}
        for order, (key, title, level, parent_key) in enumerate(ordered, 1):
            source_id = SOURCE_ID_BASE + order
            topic, _ = QuestionTopic.objects.update_or_create(
                source_id=source_id,
                defaults={
                    'document': document,
                    'parent': result.get(parent_key),
                    'title': title,
                    'display_title': title,
                    'normalized_title': key,
                    'level': level,
                    'sort_order': order,
                },
            )
            result[key] = topic
        return result

    def import_questions(self, document, records, topics):
        for order, record in enumerate(records, 1):
            fingerprint = hashlib.sha256(f'ei-892:{record["code"]}'.encode()).hexdigest()
            topic = topics.get(f'kp:{record["kp_id"]}') or topics[f'group:{record["group"]}']
            Question.objects.update_or_create(
                fingerprint=fingerprint,
                defaults={
                    'uuid': stable_uuid(record['code']),
                    'document': document,
                    'topic': topic,
                    'similarity_topic': topic,
                    'question_order': order,
                    'source_label': record['code'],
                    'display_label': record['title'],
                    'prompt_text': record['prompt'],
                    'latex_text': '',
                    'content_mode': 'markdown',
                    'confidence': 1.0,
                    'is_past_exam': False,
                    'source_category': 'workbook',
                    'record_kind': 'question',
                    'is_practiceable': True,
                    'classification_reason': 'Owner-provided 892 foundational bank',
                    'classification_confidence': 1.0,
                    'answer_markdown': record['answer'],
                    'answer_source': 'provided-reference',
                    'answer_confidence': 1.0,
                    'topic_classification_source': 'provided-kp-id',
                    'topic_classification_confidence': 1.0,
                },
            )
        return len(records)
