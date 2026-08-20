import hashlib
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question


SPLITS = (
    {
        "source_uuid": uuid.UUID("33feb823-c506-5114-bdd6-23212ddecf36"),
        "suffix": "curvature-initial-slope",
        "first_label": "Curvature · prescribed minimum",
        "first_prompt": "Find y(x) when y''>0, K=1/(2y^2 cos(alpha)), and the curve has a minimum at (1,1).",
        "second_label": "900 #27 · curvature initial value",
        "second_prompt": "Find the curve through (3,2) with tangent angle pi/4 and curvature K=1/(2y^2 cos(alpha)).",
    },
    {
        "source_uuid": uuid.UUID("05ee9bc5-6097-54fd-bfb5-fe72b0fbe795"),
        "suffix": "radial-volterra-505",
        "first_label": "Quarter-disk integral · piecewise kernel",
        "first_prompt": "Evaluate the stated quarter-disk integral F(t) and express it as a function of t.",
        "second_label": "660 #505 · radial Volterra equation",
        "second_prompt": "Solve f(t)=t^2+double-int_{x^2+y^2<=t^2} f(sqrt(x^2+y^2)) dxdy for t>=0.",
    },
)


class Command(BaseCommand):
    help = "Split differential-equation records whose two exercises already have separate crops."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        pending = []
        for spec in SPLITS:
            new_uuid = uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"time-tracker:split:{spec['source_uuid']}:{spec['suffix']}",
            )
            if not Question.objects.filter(uuid=new_uuid).exists():
                pending.append((spec, new_uuid))
        if not pending:
            self.stdout.write(self.style.SUCCESS("All asset-group splits are already applied."))
            return

        for spec, new_uuid in pending:
            try:
                question = Question.objects.select_for_update().get(uuid=spec["source_uuid"])
            except Question.DoesNotExist as exc:
                raise CommandError(f"Missing source question {spec['source_uuid']}") from exc
            assets = list(
                question.assets.select_for_update()
                .filter(asset_type="question_crop")
                .order_by("position", "id")
            )
            if len(assets) != 2:
                raise CommandError(f"Expected two source crops for {question.uuid}, found {len(assets)}")
            self.stdout.write(f"Validated two-asset split for {question.uuid}")
            if not options["apply"]:
                continue

            for later in (
                Question.objects.select_for_update()
                .filter(document=question.document, question_order__gt=question.question_order)
                .order_by("-question_order")
            ):
                later.question_order += 1
                later.save(update_fields=("question_order",))

            new_question = Question.objects.create(
                uuid=new_uuid,
                document=question.document,
                topic=question.topic,
                similarity_topic=question.similarity_topic,
                question_order=question.question_order + 1,
                source_label=spec["second_label"],
                display_label=spec["second_label"],
                prompt_text=spec["second_prompt"],
                content_mode="image",
                fingerprint=hashlib.sha256(
                    f"split:{question.uuid}:{spec['suffix']}".encode()
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
            assets[1].question = new_question
            assets[1].position = 0
            assets[1].save(update_fields=("question", "position"))
            question.display_label = spec["first_label"]
            question.prompt_text = spec["first_prompt"]
            question.content_mode = "image"
            question.confidence = 0.99
            question.save(
                update_fields=("display_label", "prompt_text", "content_mode", "confidence")
            )
            self.stdout.write(self.style.SUCCESS(f"Created split question {new_uuid}"))

        if not options["apply"]:
            self.stdout.write("Dry run only; pass --apply to write the repairs.")
            transaction.set_rollback(True)
