import hashlib
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionAsset


SOURCE_UUID = uuid.UUID('5ad12323-b3f7-5427-a693-e1e71f7a3c88')
NEW_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL,
    'time-tracker:split:5ad12323-b3f7-5427-a693-e1e71f7a3c88:nilpotent-followup',
)


def _source_id(digest):
    candidate = int(digest[:16], 16) & ((1 << 63) - 1)
    while QuestionAsset.objects.filter(source_id=candidate).exists():
        candidate = (candidate + 1) & ((1 << 63) - 1)
    return candidate


class Command(BaseCommand):
    help = 'Split the two matrix-equation exercises joined in one imported crop.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        if Question.objects.filter(uuid=NEW_UUID).exists():
            self.stdout.write(self.style.SUCCESS('Joined matrix exercises are already split.'))
            return
        try:
            source = Question.objects.select_for_update().get(uuid=SOURCE_UUID)
            asset = source.assets.select_for_update().get(asset_type='question_crop')
        except (Question.DoesNotExist, QuestionAsset.DoesNotExist) as exc:
            raise CommandError('Expected joined matrix-equation record is missing.') from exc
        if source.attempts.exists():
            raise CommandError('Joined record already has attempts and cannot be split safely.')

        self.stdout.write(
            f'Validated joined record {source.uuid} and reusable {asset.width}x{asset.height} crop.'
        )
        if not options['apply']:
            transaction.set_rollback(True)
            return

        for later in (
            Question.objects.select_for_update()
            .filter(document=source.document, question_order__gt=source.question_order)
            .order_by('-question_order')
        ):
            later.question_order += 1
            later.save(update_fields=('question_order',))

        new_question = Question.objects.create(
            uuid=NEW_UUID,
            document=source.document,
            topic=source.topic,
            similarity_topic=source.similarity_topic,
            question_order=source.question_order + 1,
            source_label='15. 姜晓千强化例题',
            display_label='Matrix power equation · strengthened example',
            prompt_text=(
                'For A=[[-1,0,1],[1,0,-1],[-2,0,2]], solve '
                'AX+I=A^100+2X.'
            ),
            content_mode='image',
            fingerprint=hashlib.sha256(f'split:{SOURCE_UUID}:{NEW_UUID}'.encode()).hexdigest(),
            confidence=0.99,
            is_past_exam=False,
            source_category='workbook',
            record_kind='question',
            is_practiceable=True,
            classification_reason='split from two exercises joined in one source crop',
            classification_confidence=0.99,
            topic_classification_source='record-split',
            topic_classification_confidence=0.99,
        )
        raw = bytes(asset.image_data)
        digest = hashlib.sha256(raw).hexdigest()
        QuestionAsset.objects.create(
            source_id=_source_id(digest),
            question=new_question,
            position=0,
            asset_type='question_crop',
            sha256=digest,
            mime_type=asset.mime_type,
            image_data=raw,
            width=asset.width,
            height=asset.height,
            source_page_index=asset.source_page_index,
            source_x0=asset.source_x0,
            source_y0=asset.source_y0,
            source_x1=asset.source_x1,
            source_y1=asset.source_y1,
            render_dpi=asset.render_dpi,
        )
        source.prompt_text = (
            'For A=[[a,1,0],[1,a,-1],[0,1,a]] with A^3=0, find a and solve '
            'X-XA^2-AX+AXA^2=I.'
        )
        source.display_label = '2015 Math II/III · nilpotent matrix equation'
        source.confidence = 0.99
        source.save(update_fields=('prompt_text', 'display_label', 'confidence'))
        self.stdout.write(self.style.SUCCESS(f'Created split question {new_question.uuid}.'))
