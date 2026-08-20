import hashlib
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question


SOURCE_UUID = uuid.UUID("4fb74ecb-449d-5a87-962e-3293f01c5f2b")
NEW_UUID = uuid.uuid5(
    uuid.NAMESPACE_URL,
    f"time-tracker:split:{SOURCE_UUID}:inverse-second-derivative",
)


class Command(BaseCommand):
    help = "Split two differential-equation derivative exercises stored as one record."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if Question.objects.filter(uuid=NEW_UUID).exists():
            self.stdout.write(self.style.SUCCESS("Derivative split is already applied."))
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

        self.stdout.write(
            f"Validated split: {assets[0].width}x{assets[0].height} and "
            f"{assets[1].width}x{assets[1].height}"
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
            source_label="26 edition 660 · Question 224",
            display_label="Inverse function · second derivative",
            prompt_text=(
                "Let y(x) solve y''-2y'+y=0 with y(0)=1 and y'(0)=2. "
                "Find the second derivative of the inverse function."
            ),
            content_mode="image",
            fingerprint=hashlib.sha256(
                f"split:{SOURCE_UUID}:inverse-second-derivative".encode()
            ).hexdigest(),
            confidence=0.99,
            is_past_exam=question.is_past_exam,
            source_category=question.source_category,
            record_kind="question",
            is_practiceable=True,
            classification_reason="split from a historically joined question record",
            classification_confidence=0.99,
            topic_classification_source="record-split",
            topic_classification_confidence=0.99,
        )
        second = assets[1]
        second.question = new_question
        second.position = 0
        second.save(update_fields=("question", "position"))

        question.display_label = "Parametric solution · second derivative"
        question.prompt_text = (
            "The function y=y(t) satisfies e^y=t+1/y' and y(0)=0. "
            "For x=sqrt(1+t^2), find d^2y/dx^2 at t=1."
        )
        question.content_mode = "image"
        question.confidence = 0.99
        question.save(
            update_fields=("display_label", "prompt_text", "content_mode", "confidence")
        )
        self.stdout.write(self.style.SUCCESS(f"Created split question {new_question.uuid}"))
