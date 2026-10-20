"""Add reviewed individual crops without replacing a source or progress row."""
import hashlib
import json
from pathlib import Path
import re

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionAsset
from drill.pdf_import import stable_source_id


class Command(BaseCommand):
    help = 'Render reviewed full-width EI question/answer regions; retain original assets and question IDs.'

    def add_arguments(self, parser):
        parser.add_argument('manifest', type=Path)
        parser.add_argument('--source-dir', action='append', type=Path, required=True)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--dpi', type=int, default=180)
        parser.add_argument('--asset-type', choices=['question_crop', 'answer_crop'], default='question_crop')
        parser.add_argument('--supersede-reviewed', action='store_true',
                            help='Retain explicitly allowlisted old crops as superseded assets; never delete their bytes or revision links.')

    def handle(self, *args, **options):
        try:
            asset_type = options['asset_type']
            region_key = 'solution_regions' if asset_type == 'answer_crop' else 'question_regions'
            manifest = json.loads(options['manifest'].read_text())
            if manifest.get('schema_version') != 1 or manifest.get('profile') != 'ei-full-width-whitespace-v1':
                raise ValueError('Unsupported region manifest')
            if not 150 <= options['dpi'] <= 240:
                raise ValueError('DPI must be 150..240')
            sources = {}
            for sha in {r['source'] for q in manifest['questions'] for r in q[region_key]}:
                if not re.fullmatch('[a-f0-9]{64}', sha):
                    raise ValueError('Invalid source identity')
                path = next((root / f'{sha}.pdf' for root in options['source_dir']
                             if (root / f'{sha}.pdf').is_file()), None)
                if path is None or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                    raise ValueError(f'Missing/corrupt PDF: {sha}')
                sources[sha] = path
            prepared = []; seen = set()
            def conflicting_assets(question, expected, item):
                conflicts = list(question.assets.filter(asset_type=asset_type).exclude(source_id__in=expected).only('pk', 'source_id', 'sha256'))
                if not conflicts:
                    return []
                approved = {entry['source_id']: entry['sha256'] for entry in item.get('supersedes_assets', [])}
                if (not options['supersede_reviewed'] or not item.get('supersede_reason')
                        or any(approved.get(asset.source_id) != asset.sha256 for asset in conflicts)):
                    raise ValueError('Existing individual images conflict; refusing overwrite without exact reviewed source IDs and hashes')
                return conflicts
            for item in manifest['questions']:
                if item['fingerprint'] in seen or not item[region_key] or item['confidence'] < .9:
                    raise ValueError('Duplicate, empty or low confidence question')
                seen.add(item['fingerprint'])
                question = Question.objects.select_related('document', 'source_anchor__source_question').get(fingerprint=item['fingerprint'])
                anchor = question.source_anchor
                if (question.document.workspace != 'ei' or question.document.parser_strategy != 'ucas-reviewed-manifest-v1'
                        or anchor.source_question.fingerprint != item['source_fingerprint'] or anchor.key != item['key']):
                    raise ValueError('Existing question/source mapping mismatch')
                expected = []
                for position, region in enumerate(item[region_key]):
                    with pymupdf.open(sources[region['source']]) as pdf:
                        if not 0 <= region['page_index'] < len(pdf):
                            raise ValueError('Invalid source page index')
                        page = pdf[region['page_index']]; rect = pymupdf.Rect(region['bbox'])
                        if (rect.is_empty or rect.height < 3 or not page.rect.contains(rect)
                                or rect.x0 != 0 or abs(rect.x1 - page.rect.width) > .01):
                            raise ValueError(f'Invalid region for {item["fingerprint"]}: {region}; page={list(page.rect)}; individual crops must preserve full page width')
                    namespace = 'ei-individual-answer-region-v1' if asset_type == 'answer_crop' else 'ei-individual-region-v1'
                    expected.append(stable_source_id(namespace, question.fingerprint,
                        json.dumps(region, sort_keys=True), position, options['dpi']))
                conflicting_assets(question, expected, item)
                prepared.append((question, item, expected))
            if options['dry_run']:
                self.stdout.write(json.dumps({'questions': len(prepared), 'dry_run': True,
                    'needs_review': len(manifest.get('review', []))}))
                return
            count = size = 0
            with transaction.atomic():
                # Lock only existing question rows. Do not change them or any
                # original images, anchors, revisions, attempts or user states.
                # PostgreSQL NO KEY UPDATE still serializes crop importers,
                # but lets attempts/states take FK KEY SHARE locks normally.
                list(Question.objects.select_for_update(no_key=True).filter(pk__in=[q.pk for q, _, _ in prepared]).values_list('pk', flat=True))
                for question, item, expected in prepared:
                    # Recheck the reviewed allowlist under the question lock.
                    # Keep immutable image bytes, PKs and historical revision links.
                    conflicts = conflicting_assets(question, expected, item)
                    if conflicts:
                        QuestionAsset.objects.filter(pk__in=[a.pk for a in conflicts]).update(asset_type=f'{asset_type}_superseded')
                    for position, (region, source_id) in enumerate(zip(item[region_key], expected)):
                        if QuestionAsset.objects.filter(source_id=source_id, question=question).exists():
                            continue
                        # Recheck under the row lock, too, against concurrent imports.
                        if question.assets.filter(asset_type=asset_type).exclude(source_id__in=expected).exists():
                            raise ValueError('Concurrent individual image conflict')
                        with pymupdf.open(sources[region['source']]) as pdf:
                            pix = pdf[region['page_index']].get_pixmap(clip=pymupdf.Rect(region['bbox']), dpi=options['dpi'], alpha=False)
                            binary = pix.tobytes('png')
                        x0, y0, x1, y1 = region['bbox']
                        QuestionAsset.objects.create(source_id=source_id, question=question, asset_type=asset_type,
                            position=position, image_data=binary, sha256=hashlib.sha256(binary).hexdigest(),
                            width=pix.width, height=pix.height, source_page_index=region['page_index'],
                            source_x0=x0, source_y0=y0, source_x1=x1, source_y1=y1, render_dpi=options['dpi'])
                        count += 1; size += len(binary)
            self.stdout.write(json.dumps({'questions': len(prepared), 'new_images': count, 'new_image_bytes': size,
                'needs_review': len(manifest.get('review', [])), 'original_images_unchanged': True}))
        except (ValueError, OSError, KeyError, IndexError, Question.DoesNotExist) as error:
            raise CommandError(str(error)) from error
