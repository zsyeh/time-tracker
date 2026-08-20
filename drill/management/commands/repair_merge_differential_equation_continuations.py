import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question


MERGES = (
    {
        "parent_uuid": uuid.UUID("c3c9f095-ed21-59b9-a00d-71a02486ddc6"),
        "continuation_uuid": uuid.UUID("666ac80b-23a0-5de7-b48d-a81ebc200308"),
        "label": "2001 Math II · curve and minimum-area tangent",
        "prompt": (
            "A plane curve L passes through (1/2,0). At each P(x,y), x>0, the distance "
            "OP equals the y-intercept of the tangent. Find L, then find the first-quadrant "
            "tangent for which the area enclosed with L and the coordinate axes is minimal."
        ),
    },
    {
        "parent_uuid": uuid.UUID("c89f5c9d-1bbe-5fdc-8117-a5ca957e9692"),
        "continuation_uuid": uuid.UUID("84471366-f37a-58e8-b087-cda9580d3160"),
        "label": "2017 Math II · intercept locus and minimum triangle",
        "prompt": (
            "For a differentiable curve y=y(x), y(1)=0, the tangent and normal at P meet "
            "the axes at (0,Y_P) and (X_P,0). Given X_P=Y_P, find the locus L, then find "
            "the point whose tangent forms the minimum-area triangle with the axes."
        ),
    },
    {
        "parent_uuid": uuid.UUID("58c1760f-16a1-5ad5-b20c-c631892206d8"),
        "continuation_uuid": uuid.UUID("ce776ec2-9107-53f6-9010-9d6058c42dcc"),
        "label": "2003 Math II · vessel profile",
        "prompt": (
            "A vessel has radial profile x=phi(y), bottom radius 2 m, inflow 3 m^3/min, "
            "and liquid surface area increasing uniformly at pi m^2/min. Find phi(y)."
        ),
    },
)


class Command(BaseCommand):
    help = "Merge page-break continuation records into their complete differential-equation question."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        changed = 0
        for spec in MERGES:
            try:
                parent = Question.objects.select_for_update().get(uuid=spec["parent_uuid"])
                continuation = Question.objects.select_for_update().get(
                    uuid=spec["continuation_uuid"]
                )
            except Question.DoesNotExist as exc:
                raise CommandError(f"Missing continuation pair: {spec}") from exc
            if not continuation.is_practiceable and not continuation.assets.exists():
                continue
            if continuation.attempts.exists():
                raise CommandError(
                    f"Continuation {continuation.uuid} has attempts and cannot be merged safely"
                )
            self.stdout.write(f"Validated continuation {continuation.uuid} -> {parent.uuid}")
            if not options["apply"]:
                changed += 1
                continue

            start = parent.assets.count()
            for offset, asset in enumerate(
                continuation.assets.select_for_update().order_by("position", "id")
            ):
                asset.question = parent
                asset.position = start + offset
                asset.save(update_fields=("question", "position"))
            parent.display_label = spec["label"]
            parent.prompt_text = spec["prompt"]
            parent.content_mode = "image"
            parent.confidence = 0.99
            parent.save(
                update_fields=("display_label", "prompt_text", "content_mode", "confidence")
            )
            continuation.is_practiceable = False
            continuation.record_kind = "grouped"
            continuation.classification_reason = (
                f"page-break continuation merged into question {parent.uuid}"
            )
            continuation.classification_confidence = 1.0
            continuation.save(
                update_fields=(
                    "is_practiceable",
                    "record_kind",
                    "classification_reason",
                    "classification_confidence",
                )
            )
            changed += 1

        if not options["apply"]:
            self.stdout.write(f"Dry run only; {changed} continuation merge(s) are pending.")
            transaction.set_rollback(True)
        else:
            self.stdout.write(self.style.SUCCESS(f"Applied {changed} continuation merge(s)."))
