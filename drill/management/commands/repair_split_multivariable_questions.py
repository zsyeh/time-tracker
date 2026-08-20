import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionAsset


SPLITS = (
    {
        "source_uuid": uuid.UUID("09fde066-325a-5b05-b918-35bcd67f6292"),
        "new_uuid": uuid.uuid5(
            uuid.NAMESPACE_URL,
            "time-tracker:split:09fde066-325a-5b05-b918-35bcd67f6292:euler-homogeneous",
        ),
        "marker": "vii)26 版660",
        "first_y1": 72,
        "second_y0": 72,
        "second_y1": 202,
        "first_prompt": "9. Let f(x,y)=sqrt(|xy|). Find the partial derivative with respect to x.",
        "second_prompt": "Let z=ln(sqrt(x)+sqrt(y)). Find x z_x + y z_y.",
        "source_label": "26 版 660 数一二三第 88 题",
        "display_label": "Euler homogeneous-function identity",
    },
    {
        "source_uuid": uuid.UUID("443d7d23-f4d1-5be7-99f7-45e350df384c"),
        "new_uuid": uuid.uuid5(
            uuid.NAMESPACE_URL,
            "time-tracker:split:443d7d23-f4d1-5be7-99f7-45e350df384c:660-230",
        ),
        "marker": "vii)26 版660",
        "first_y1": 230,
        "second_y0": 230,
        "second_y1": 458,
        "first_prompt": (
            "Given f(x+y,x-y)=sin(x)cos(x)+sin(y)cos(y), find "
            "f_u(0,0)+f_v(0,0)."
        ),
        "second_prompt": (
            "Given f(x+y,x-y)=x^2-y^2 for all x,y, find f_x(x,y)+f_y(x,y)."
        ),
        "source_label": "26 版 660 数一二三第 230 题",
        "display_label": "Variable substitution · 660 #230",
    },
    {
        "source_uuid": uuid.UUID("ee54098d-a60b-5726-9167-d8f5f7bc1fa1"),
        "new_uuid": uuid.uuid5(
            uuid.NAMESPACE_URL,
            "time-tracker:split:ee54098d-a60b-5726-9167-d8f5f7bc1fa1:900-a12",
        ),
        "marker": "(i)900",
        "first_y1": 220,
        "second_y0": 220,
        "second_y1": 560,
        "expected_assets": 2,
        "first_prompt": (
            "The equation F(x/z,yz)=0 determines z=z(x,y). Find x z_x-y z_y."
        ),
        "second_prompt": (
            "The equation f(y e^x/z, ln z)=1 determines z=z(x,y). "
            "Determine the relation between z_x and z_y."
        ),
        "source_label": "900 第四章数二 A 类 12",
        "display_label": "Implicit differentiation · 900 A12",
    },
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


def _source_id(digest):
    candidate = int(digest[:16], 16) & ((1 << 63) - 1)
    while QuestionAsset.objects.filter(source_id=candidate).exists():
        candidate = (candidate + 1) & ((1 << 63) - 1)
    return candidate


class Command(BaseCommand):
    help = "Split two historically joined multivariable-differentiation records."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        pending = [item for item in SPLITS if not Question.objects.filter(uuid=item["new_uuid"]).exists()]
        if not pending:
            self.stdout.write(self.style.SUCCESS("All multivariable record splits are already applied."))
            return

        for item in pending:
            try:
                question = Question.objects.select_for_update().get(uuid=item["source_uuid"])
            except Question.DoesNotExist as exc:
                raise CommandError(f"Missing source question {item['source_uuid']}") from exc
            if item["marker"] not in question.prompt_text:
                raise CommandError(f"Expected split marker is missing for {question.uuid}")
            assets = list(
                question.assets.select_for_update()
                .filter(asset_type="question_crop")
                .order_by("position", "id")
            )
            expected_assets = item.get("expected_assets", 1)
            if len(assets) != expected_assets:
                raise CommandError(
                    f"Expected {expected_assets} source crop(s) for {question.uuid}, found {len(assets)}"
                )
            asset = assets[0]
            if asset.height < item["second_y1"]:
                raise CommandError(f"Source crop for {question.uuid} is shorter than expected")

            raw = bytes(asset.image_data)
            first_png, first_width, first_height = _crop(
                raw, width=asset.width, y0=0, y1=item["first_y1"]
            )
            second_png, second_width, second_height = _crop(
                raw,
                width=asset.width,
                y0=item["second_y0"],
                y1=item["second_y1"],
            )
            self.stdout.write(
                f"Validated {question.uuid}: {asset.width}x{asset.height} -> "
                f"{first_width}x{first_height} + {second_width}x{second_height}"
            )
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
                uuid=item["new_uuid"],
                document=question.document,
                topic=question.topic,
                similarity_topic=question.similarity_topic,
                question_order=question.question_order + 1,
                source_label=item["source_label"],
                display_label=item["display_label"],
                prompt_text=item["second_prompt"],
                content_mode="image",
                fingerprint=hashlib.sha256(
                    f"split:{question.uuid}:{item['new_uuid']}".encode()
                ).hexdigest(),
                confidence=0.99,
                is_past_exam=False,
                source_category="workbook",
                record_kind="question",
                is_practiceable=True,
                classification_reason="split from a historically joined question crop",
                classification_confidence=0.99,
                topic_classification_source="record-split",
                topic_classification_confidence=0.99,
            )

            old_y0, old_y1 = asset.source_y0, asset.source_y1
            first_source_y1 = second_source_y0 = second_source_y1 = None
            if old_y0 is not None and old_y1 is not None:
                span = old_y1 - old_y0
                first_source_y1 = old_y0 + span * item["first_y1"] / asset.height
                second_source_y0 = old_y0 + span * item["second_y0"] / asset.height
                second_source_y1 = old_y0 + span * item["second_y1"] / asset.height

            first_digest = hashlib.sha256(first_png).hexdigest()
            asset.image_data = first_png
            asset.width = first_width
            asset.height = first_height
            asset.sha256 = first_digest
            asset.source_y1 = first_source_y1
            asset.save(update_fields=("image_data", "width", "height", "sha256", "source_y1"))

            second_digest = hashlib.sha256(second_png).hexdigest()
            QuestionAsset.objects.create(
                source_id=_source_id(second_digest),
                question=new_question,
                position=0,
                asset_type="question_crop",
                sha256=second_digest,
                mime_type="image/png",
                image_data=second_png,
                width=second_width,
                height=second_height,
                source_page_index=asset.source_page_index,
                source_x0=asset.source_x0,
                source_y0=second_source_y0,
                source_x1=asset.source_x1,
                source_y1=second_source_y1,
                render_dpi=asset.render_dpi,
            )
            question.prompt_text = item["first_prompt"]
            question.confidence = 0.99
            question.save(update_fields=("prompt_text", "confidence"))
            for redundant_asset in assets[1:]:
                redundant_asset.delete()
            self.stdout.write(self.style.SUCCESS(f"Created split question {new_question.uuid}"))

        if not options["apply"]:
            self.stdout.write("Dry run only; pass --apply to write the repairs.")
            transaction.set_rollback(True)
