import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question


SOURCE_UUID = uuid.UUID("5fe1e201-102f-55ec-8337-7c61c4d41c68")
NEW_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL,
    f"time-tracker:split:{SOURCE_UUID}:sphere-full-differential",
)


def _crop(raw, *, width, y0, y1):
    document = pymupdf.open(stream=raw, filetype="png")
    try:
        page = document[0]
        scale = width / page.rect.width
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale),
            clip=pymupdf.Rect(0, y0 / scale, page.rect.width, y1 / scale),
            alpha=False,
        )
        return pixmap.tobytes("png"), pixmap.width, pixmap.height
    finally:
        document.close()


class Command(BaseCommand):
    help = "Split two full-differential exercises stored in one historical record."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if Question.objects.filter(uuid=NEW_UUID).exists():
            self.stdout.write(self.style.SUCCESS("Full-differential split is already applied."))
            return
        try:
            question = Question.objects.select_for_update().get(uuid=SOURCE_UUID)
        except Question.DoesNotExist as exc:
            raise CommandError(f"Missing source question {SOURCE_UUID}") from exc
        assets = list(
            question.assets.select_for_update()
            .filter(asset_type="question_crop")
            .order_by("position", "id")
        )
        if len(assets) != 2:
            raise CommandError(f"Expected two source crops, found {len(assets)}")
        first, second = assets
        first_png, first_width, first_height = _crop(
            bytes(first.image_data), width=first.width, y0=0, y1=92
        )
        second_png, second_width, second_height = _crop(
            bytes(second.image_data), width=second.width, y0=70, y1=second.height
        )
        self.stdout.write(
            f"Validated split: {first.width}x{first.height} and {second.width}x{second.height}"
        )
        if not options["apply"]:
            self.stdout.write("Dry run only; pass --apply to write the repair.")
            transaction.set_rollback(True)
            return

        for later in (
            Question.objects.select_for_update()
            .filter(document=question.document, question_order__gt=question.question_order)
            .order_by("-question_order")
        ):
            later.question_order += 1
            later.save(update_fields=("question_order",))
        new_question = Question.objects.create(
            uuid=NEW_UUID,
            document=question.document,
            topic=question.topic,
            similarity_topic=question.similarity_topic,
            question_order=question.question_order + 1,
            source_label="26 版 660 数一二三第 93 题",
            display_label="Sphere · full differential",
            prompt_text="The equation x^2+y^2+z^2=3 determines z=z(x,y). Find dz at (1,1,1).",
            content_mode="image",
            fingerprint=hashlib.sha256(f"split:{SOURCE_UUID}:sphere".encode()).hexdigest(),
            confidence=0.99,
            source_category="workbook",
            record_kind="question",
            is_practiceable=True,
            classification_reason="split from a historically joined question crop",
            classification_confidence=0.99,
            topic_classification_source="record-split",
            topic_classification_confidence=0.99,
        )
        first.image_data = first_png
        first.width = first_width
        first.height = first_height
        first.sha256 = hashlib.sha256(first_png).hexdigest()
        first.save(update_fields=("image_data", "width", "height", "sha256"))
        second.image_data = second_png
        second.width = second_width
        second.height = second_height
        second.sha256 = hashlib.sha256(second_png).hexdigest()
        second.question = new_question
        second.position = 0
        second.save(
            update_fields=("image_data", "width", "height", "sha256", "question", "position")
        )
        question.prompt_text = (
            "The equation e^(x-2y+3z)-2x e^(-y) cos(z)=1 determines z=z(x,y). "
            "Find dz at (0,0)."
        )
        question.save(update_fields=("prompt_text",))
        self.stdout.write(self.style.SUCCESS(f"Created split question {new_question.uuid}"))
