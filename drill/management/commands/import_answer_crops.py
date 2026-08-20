import hashlib
import json
from pathlib import Path

import fitz
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionAsset


class Command(BaseCommand):
    help = 'Import verified per-question segments from official answer PDFs.'

    def add_arguments(self, parser):
        parser.add_argument('--mapping', required=True, help='JSONL answer mapping file.')
        parser.add_argument('--source-root', required=True, help='Directory containing source PDFs.')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--min-match-confidence', type=float, default=0.98)

    def handle(self, *args, **options):
        mapping_path = Path(options['mapping']).resolve()
        source_root = Path(options['source_root']).resolve()
        if not mapping_path.is_file():
            raise CommandError(f'Mapping file does not exist: {mapping_path}')
        if not source_root.is_dir():
            raise CommandError(f'Source root does not exist: {source_root}')
        rows = self._read_mapping(mapping_path, options['min_match_confidence'])
        questions = self._load_questions(rows)
        jobs = []
        page_counts = {}
        for row in rows:
            question = questions[row['question_uuid']]
            pdf_path = (source_root / row['source_pdf']).resolve()
            try:
                pdf_path.relative_to(source_root)
            except ValueError as exc:
                raise CommandError(f'Source PDF escapes source root: {row["source_pdf"]}') from exc
            if not pdf_path.is_file():
                raise CommandError(f'Source PDF does not exist: {pdf_path}')
            try:
                document = fitz.open(pdf_path)
                page_counts[pdf_path] = len(document)
                document.close()
            except (OSError, RuntimeError) as exc:
                raise CommandError(f'Cannot inspect source PDF {pdf_path}: {exc}') from exc
            for region in row['crop_regions']:
                page_index = region['page_index']
                if page_index < 1 or page_index > page_counts[pdf_path]:
                    raise CommandError(f'Page {page_index} out of range for {row["source_pdf"]}')
                jobs.append((question, pdf_path, region))

        report = {
            'mapping_rows': len(rows),
            'validated_segments': len(jobs),
            'rendered_assets': 0,
            'new_assets': None if options['dry_run'] else 0,
            'question_count': Question.objects.count(),
            'answer_questions_before': QuestionAsset.objects.filter(asset_type='answer_crop').values('question_id').distinct().count(),
            'dry_run': options['dry_run'],
        }
        if options['dry_run']:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return

        existing_hashes = set(QuestionAsset.objects.filter(asset_type='answer_crop').values_list('question_id', 'sha256'))
        new_count = 0
        with transaction.atomic():
            source_id = (QuestionAsset.objects.order_by('-source_id').values_list('source_id', flat=True).first() or 0) + 1
            documents = {}
            try:
                for question, pdf_path, region in jobs:
                    if pdf_path not in documents:
                        documents[pdf_path] = fitz.open(pdf_path)
                    document = documents[pdf_path]
                    page = document[region['page_index'] - 1]
                    clip = fitz.Rect(region['x0'], region['y0'], region['x1'], region['y1'])
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(180 / 72, 180 / 72), clip=clip, alpha=False)
                    image_data = pixmap.tobytes('png')
                    sha256 = hashlib.sha256(image_data).hexdigest()
                    if (question.pk, sha256) in existing_hashes:
                        continue
                    position = QuestionAsset.objects.filter(question=question, asset_type='answer_crop').count()
                    QuestionAsset.objects.create(
                        source_id=source_id,
                        question=question,
                        position=position,
                        asset_type='answer_crop',
                        sha256=sha256,
                        mime_type='image/png',
                        image_data=image_data,
                        width=pixmap.width,
                        height=pixmap.height,
                        source_page_index=region['page_index'] - 1,
                        source_x0=clip.x0,
                        source_y0=clip.y0,
                        source_x1=clip.x1,
                        source_y1=clip.y1,
                        render_dpi=180,
                    )
                    existing_hashes.add((question.pk, sha256))
                    source_id += 1
                    new_count += 1
            finally:
                for document in documents.values():
                    document.close()
        report.update({'rendered_assets': len(jobs), 'new_assets': new_count})
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS(f'Imported {new_count} segmented answer_crop assets.'))

    @staticmethod
    def _read_mapping(path, minimum_confidence):
        rows = []
        seen_questions = set()
        for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CommandError(f'Invalid JSON at {path}:{line_number}: {exc}') from exc
            required = {'question_uuid', 'source_pdf', 'crop_regions', 'match_confidence', 'review_required'}
            missing = required - row.keys()
            if missing:
                raise CommandError(f'Missing {sorted(missing)} at {path}:{line_number}')
            if row['review_required'] or float(row['match_confidence']) < minimum_confidence:
                raise CommandError(f'Unverified mapping at {path}:{line_number}; refusing to write.')
            if not isinstance(row['crop_regions'], list) or not row['crop_regions']:
                raise CommandError(f'crop_regions must be a non-empty list at {path}:{line_number}')
            uuid = str(row['question_uuid'])
            if uuid in seen_questions:
                raise CommandError(f'Duplicate question mapping at {path}:{line_number}: {uuid}')
            seen_questions.add(uuid)
            rows.append(row)
        return rows

    @staticmethod
    def _load_questions(rows):
        uuids = [row['question_uuid'] for row in rows]
        questions = {str(q.uuid): q for q in Question.objects.filter(uuid__in=uuids)}
        missing = sorted(set(uuids) - set(questions))
        if missing:
            raise CommandError(f'Mapping references unknown Question UUID(s): {missing[:5]}')
        return questions
