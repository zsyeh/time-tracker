import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionAsset


SOURCE_UUID = uuid.UUID("4eb65554-631f-5cf6-9534-9173872b24b6")
SPLIT_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL,
    f"time-tracker:split:{SOURCE_UUID}:2024-improper-integral",
)
SPLIT_MARKER = "(2024 数二）"
FIRST_CROP_HEIGHT = 170


def _crop_png(raw, *, width, y0, y1):
    document = pymupdf.open(stream=raw, filetype="png")
    try:
        page = document[0]
        scale = width / page.rect.width
        clip = pymupdf.Rect(
            0,
            y0 / scale,
            page.rect.width,
            y1 / scale,
        )
        crop = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            clip=clip,
            alpha=False,
        )
        return crop.tobytes("png"), crop.width, crop.height
    finally:
        document.close()


def _source_id_for(digest):
    candidate = int(digest[:16], 16) & ((1 << 63) - 1)
    while QuestionAsset.objects.filter(source_id=candidate).exists():
        candidate = (candidate + 1) & ((1 << 63) - 1)
    return candidate


class Command(BaseCommand):
    help = (
        "Split the historical record that joined the 900 improper-integral "
        "question and the 2024 Math II proposition question."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the repair. Without this flag the command only validates it.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if Question.objects.filter(uuid=SPLIT_UUID).exists():
            self.stdout.write(
                self.style.SUCCESS(f"Repair already applied: {SPLIT_UUID}")
            )
            return

        try:
            question = (
                Question.objects.select_for_update()
                .get(uuid=SOURCE_UUID)
            )
        except Question.DoesNotExist as exc:
            raise CommandError(f"Source question is missing: {SOURCE_UUID}") from exc

        if SPLIT_MARKER not in question.prompt_text:
            raise CommandError("The expected 2024 split marker is missing.")

        assets = list(
            question.assets.select_for_update()
            .filter(asset_type="question_crop")
            .order_by("position", "id")
        )
        if len(assets) != 2:
            raise CommandError(f"Expected 2 question crops, found {len(assets)}.")
        first_asset, continuation_asset = assets
        if first_asset.height <= FIRST_CROP_HEIGHT:
            raise CommandError("The first crop has already been shortened.")

        original_prompt, split_prompt = question.prompt_text.split(SPLIT_MARKER, 1)
        split_prompt = f"{SPLIT_MARKER}{split_prompt}".strip()
        original_prompt = original_prompt.strip()
        raw = bytes(first_asset.image_data)
        first_png, first_width, first_height = _crop_png(
            raw,
            width=first_asset.width,
            y0=0,
            y1=FIRST_CROP_HEIGHT,
        )
        second_png, second_width, second_height = _crop_png(
            raw,
            width=first_asset.width,
            y0=FIRST_CROP_HEIGHT,
            y1=first_asset.height,
        )

        self.stdout.write(
            f"Validated split: {first_asset.width}x{first_asset.height} -> "
            f"{first_width}x{first_height} + {second_width}x{second_height}; "
            f"new UUID {SPLIT_UUID}"
        )
        if not options["apply"]:
            self.stdout.write("Dry run only; pass --apply to write the repair.")
            transaction.set_rollback(True)
            return

        later_questions = list(
            Question.objects.select_for_update()
            .filter(
                document=question.document,
                question_order__gt=question.question_order,
            )
            .order_by("-question_order")
        )
        for later in later_questions:
            later.question_order += 1
            later.save(update_fields=("question_order",))

        new_question = Question.objects.create(
            uuid=SPLIT_UUID,
            document=question.document,
            topic=question.topic,
            similarity_topic=question.similarity_topic,
            question_order=question.question_order + 1,
            source_label="(2024 数二) 非负连续函数与反常积分命题",
            display_label="2024 · Math II · Convergence propositions",
            prompt_text=split_prompt,
            latex_text="",
            content_mode="text",
            fingerprint=hashlib.sha256(
                f"split:{SOURCE_UUID}:2024-improper-integral".encode()
            ).hexdigest(),
            confidence=0.99,
            is_past_exam=True,
            source_category="past_exam",
            record_kind="question",
            is_practiceable=True,
            classification_reason="split from a historically joined 2024 past-exam record",
            classification_confidence=0.99,
            exam_year=2024,
            exam_variant="数二",
            topic_classification_source="record-split",
            topic_classification_confidence=0.99,
        )

        original_source_y0 = first_asset.source_y0
        original_source_y1 = first_asset.source_y1
        source_cut_y = None
        if original_source_y0 is not None and original_source_y1 is not None:
            source_cut_y = original_source_y0 + (
                (original_source_y1 - original_source_y0)
                * FIRST_CROP_HEIGHT
                / first_asset.height
            )

        first_digest = hashlib.sha256(first_png).hexdigest()
        first_asset.image_data = first_png
        first_asset.width = first_width
        first_asset.height = first_height
        first_asset.sha256 = first_digest
        if source_cut_y is not None:
            first_asset.source_y1 = source_cut_y
        first_asset.save(
            update_fields=(
                "image_data",
                "width",
                "height",
                "sha256",
                "source_y1",
            )
        )

        second_digest = hashlib.sha256(second_png).hexdigest()
        QuestionAsset.objects.create(
            source_id=_source_id_for(second_digest),
            question=new_question,
            position=0,
            asset_type="question_crop",
            sha256=second_digest,
            mime_type="image/png",
            image_data=second_png,
            width=second_width,
            height=second_height,
            source_page_index=first_asset.source_page_index,
            source_x0=first_asset.source_x0,
            source_y0=source_cut_y,
            source_x1=first_asset.source_x1,
            source_y1=original_source_y1,
            render_dpi=first_asset.render_dpi,
        )
        continuation_asset.question = new_question
        continuation_asset.position = 1
        continuation_asset.save(update_fields=("question", "position"))

        question.prompt_text = original_prompt
        question.confidence = 0.99
        question.save(update_fields=("prompt_text", "confidence"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Split {SOURCE_UUID} and created {SPLIT_UUID} at order "
                f"{new_question.question_order}."
            )
        )
