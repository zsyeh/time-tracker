import hashlib
import uuid

import pymupdf
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question, QuestionAsset


SPLITS = (
    {
        "source_uuid": uuid.UUID("aa66510a-2080-5f3f-a0f2-0d4e085231f3"),
        "parts": (
            (0, 70, "Inflection-point initial condition", "Solve y'-2 sqrt(2) x sqrt(y)=0 when an integral curve has an inflection at x=-2."),
            (70, 164, "660 #73 · separable equation", "Find the general solution of y'=(1+x)(1+y^2)."),
        ),
    },
    {
        "source_uuid": uuid.UUID("8536c873-aae0-5e62-9b8a-c79c66b6177c"),
        "parts": (
            (0, 170, "Linear ODE · extrema and inflection", "Given f'-f=2xe^x, select solutions with no extrema but with an inflection point."),
            (170, 292, "660 #76 · linear ODE", "Find the general solution of y'+y tan(x)=cos(x)."),
            (292, 520, "660 #500 · parameterized IVP", "Solve y'+lambda y=1, y(0)=0 for every real lambda."),
        ),
    },
    {
        "source_uuid": uuid.UUID("62700b8a-0854-53b9-9d14-10f7ad31fc68"),
        "parts": (
            (0, 218, "Second-order IVP · perpendicular tangent", "Solve y''+2y'+y=0 through (0,4), with tangent perpendicular to x-2y+5=0."),
            (218, 452, "660 #216 · second-order IVP", "Solve y''+9y=0 through (pi,-1), tangent there to y+1=x-pi."),
        ),
    },
    {
        "source_uuid": uuid.UUID("02e59a11-8adb-569d-a961-28f22098108c"),
        "expected_assets": 2,
        "parts": (
            (0, 230, "Undetermined coefficients · repeated resonance", "Choose a particular-solution form for 4y''-12y'+9y=e^(3x/2)(3x^2+2)."),
            (230, 510, "660 #215 · trigonometric resonance", "Choose a particular-solution form for y''-2y'+5y=e^x cos(2x)."),
        ),
    },
    {
        "source_uuid": uuid.UUID("af8e99e4-d954-5b35-ab06-143033e02f63"),
        "parts": (
            (0, 90, "Second-order equation with polynomial forcing", "Solve y''+2y'+y=(3x+2)e^(-x)."),
            (90, 405, "660 #214 · resonant IVP", "Solve y''-6y'+9y=e^(3x), through the origin with tangent slope 2."),
            (405, 651, "660 #223 · higher-order infinitesimal", "Select the solution of y''-y=x^2 that is a higher-order infinitesimal than x^2 at zero."),
        ),
    },
    {
        "source_uuid": uuid.UUID("2989854e-0bcb-5221-97bc-5b3db77fd08b"),
        "parts": (
            (0, 98, "Order reduction · nonlinear IVP", "Solve 2y''=3y^2 with y(-2)=1 and y'(-2)=1."),
            (98, 350, "660 #217 · nonlinear IVP", "Solve 1+(y')^2=2yy'' with y(1)=1 and y'(1)=-1."),
        ),
    },
    {
        "source_uuid": uuid.UUID("d2ac5707-e055-5f4d-9431-7701e2d6a782"),
        "parts": (
            (0, 245, "Radial harmonic-function reduction", "For z=(x^2+y^2)f(x^2+y^2), solve z_xx+z_yy=0 with f(1)=0 and f'(1)=1."),
            (245, 430, "660 #222 · Euler equation", "Solve x^2y''+2xy'-2y=0."),
        ),
    },
    {
        "source_uuid": uuid.UUID("2d02ffd0-021e-50d3-8ccc-d77147d74e0d"),
        "parts": (
            (0, 92, "Fourth-order asymptotic IVP", "Solve y^(4)-y''=0 subject to y(x)~x^3 as x approaches zero."),
            (92, 229, "660 #502 · third-order IVP", "Solve y'''+y''-y'-y=0 with y(0)=4, y'(0)=4, and y''(0)=0."),
        ),
    },
    {
        "source_uuid": uuid.UUID("815a4ec7-aecc-5b52-81ad-6762d3c28ca3"),
        "parts": (
            (0, 212, "Bounded forcing · explicit estimate", "Solve y'+y=phi(x), y(0)=0, and prove |y(x)|<=k(1-e^(-x)) when |phi|<=k and x>=0."),
            (212, 428, "660 #606 · periodic solution criterion", "For T-periodic P and Q, classify whether y(0)=y(T) is necessary and/or sufficient for a solution of y'+P(x)y=Q(x) to be T-periodic."),
        ),
    },
    {
        "source_uuid": uuid.UUID("733b8c91-beb1-55ab-a1cf-ca96b96d01c5"),
        "parts": (
            (0, 238, "Root count for an ODE solution", "Solve xf'-f=a(1-ln x)+x^2 with f(1)=1-a, then determine a when f=0 has exactly one positive root."),
            (238, 429, "660 #217 · definite integral", "For (1+x^2)y'-2xy=x, y(0)=1, compute the integral of y from 0 to 1."),
        ),
    },
    {
        "source_uuid": uuid.UUID("66f4d703-aaf2-5410-aa25-5cba54a5ab0c"),
        "parts": (
            (0, 198, "Average value of an ODE solution", "Solve 2xy'-4y=2 ln x-1 with y(1)=1/4 and find its average value on [1,e]."),
            (198, 397, "660 #219 · minimum solid of revolution", "Given xf'-2f=-4x, identify f when the solid formed by the curve, x=1, and the x-axis has minimum volume about the x-axis."),
        ),
    },
    {
        "source_uuid": uuid.UUID("fac7d3a0-248e-5d45-ad28-983b4b9eef25"),
        "parts": (
            (0, 154, "Tangent x-intercept condition", "Find the decreasing curve through (a,1) whose tangent's x-intercept remains distance a from the point's abscissa."),
            (154, 311, "660 #78 · homogeneous first-order ODE", "Solve y'=1+y/x+(y/x)^2 for the curve through (1,0)."),
        ),
    },
    {
        "source_uuid": uuid.UUID("54c6180a-e574-5012-a2a3-7bd6b18713af"),
        "parts": (
            (0, 142, "Integral equation · convolution", "Solve x=int_0^x f(t)dt+int_0^x t f(t-x)dt."),
            (142, 280, "660 #82 · integral equation", "Solve int_0^x f(t)dt=x+sin x+int_0^x t f(x-t)dt."),
            (280, 407, "Nonzero integral-equation solution", "For continuous nonzero f, solve f(x)=int_0^x f(x-t)dt+int_0^1 f(t)^2dt."),
            (407, 543, "1000 #66 · convolution equation", "Solve int_0^x f(t)dt+int_0^x t f(x-t)dt=(x-e^(-x)sin x)/2."),
        ),
    },
    {
        "source_uuid": uuid.UUID("eb05f303-c584-54df-9e54-648c918d62b9"),
        "parts": (
            (0, 154, "Composite-function initial derivative", "If f_u(u,v)+f_v(u,v)=uv, find the solution y=e^(-2x)f(x,x) with y(0)=1."),
            (154, 333, "660 #592 · radial PDE reduction", "For radial u=u(r), solve u_xx+u_yy-(1/x)u_x+u=x^2+y^2."),
        ),
    },
    {
        "source_uuid": uuid.UUID("90d0dfc2-03ce-50bb-b211-665b06d14921"),
        "parts": (
            (0, 190, "Double-integral identity for f'',", "On [0,1], solve the stated triangular-domain integral identity with f(0)=1 and right derivative f'_+(0)=1."),
            (190, 339, "Radial integral equation", "Solve f(t)=2 double-int_{x^2+y^2<=t^2}(x^2+y^2)f(sqrt(x^2+y^2))dxdy+t^4."),
        ),
    },
    {
        "source_uuid": uuid.UUID("f3724216-895a-538e-b8ba-298f9b26834c"),
        "parts": (
            (0, 474, "Pursuit curve · aircraft and missile", "An aircraft moves from the origin at speed v; a missile starts at (16,0), always points at the aircraft, and moves at speed 2v. Find its trajectory and interception time."),
            (474, 709, "660 #610 · linear drag", "A projectile enters sand at speed v0 and experiences drag kv. Find its penetration depth."),
        ),
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
    help = "Split historically joined differential-equation question crops."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        pending = []
        for spec in SPLITS:
            new_uuids = [
                uuid.uuid5(uuid.NAMESPACE_URL, f"time-tracker:split:{spec['source_uuid']}:{index}")
                for index in range(1, len(spec["parts"]))
            ]
            if not all(Question.objects.filter(uuid=value).exists() for value in new_uuids):
                pending.append((spec, new_uuids))
        if not pending:
            self.stdout.write(self.style.SUCCESS("All differential-equation splits are already applied."))
            return

        for spec, new_uuids in pending:
            question = Question.objects.select_for_update().filter(uuid=spec["source_uuid"]).first()
            if question is None:
                raise CommandError(f"Missing source question {spec['source_uuid']}")
            assets = list(
                question.assets.select_for_update()
                .filter(asset_type="question_crop")
                .order_by("position", "id")
            )
            expected_assets = spec.get("expected_assets", 1)
            if len(assets) != expected_assets:
                raise CommandError(
                    f"Expected {expected_assets} crop(s) for {question.uuid}, found {len(assets)}"
                )
            asset = assets[0]
            if asset.height < max(part[1] for part in spec["parts"]):
                raise CommandError(f"Crop for {question.uuid} is shorter than the split boundary")
            rendered = [
                _crop(bytes(asset.image_data), width=asset.width, y0=part[0], y1=part[1])
                for part in spec["parts"]
            ]
            self.stdout.write(f"Validated {question.uuid} into {len(rendered)} questions")
            if not options["apply"]:
                continue

            shift = len(rendered) - 1
            for later in (
                Question.objects.select_for_update()
                .filter(document=question.document, question_order__gt=question.question_order)
                .order_by("-question_order")
            ):
                later.question_order += shift
                later.save(update_fields=("question_order",))

            original_y0, original_y1 = asset.source_y0, asset.source_y1
            created = []
            for index, ((y0, y1, label, prompt), (png, width, height)) in enumerate(
                zip(spec["parts"], rendered)
            ):
                source_y0 = source_y1 = None
                if original_y0 is not None and original_y1 is not None:
                    span = original_y1 - original_y0
                    source_y0 = original_y0 + span * y0 / asset.height
                    source_y1 = original_y0 + span * y1 / asset.height
                digest = hashlib.sha256(png).hexdigest()
                if index == 0:
                    target = question
                    target.prompt_text = prompt
                    target.display_label = label
                    target.confidence = 0.99
                    target.save(update_fields=("prompt_text", "display_label", "confidence"))
                    asset.image_data = png
                    asset.width = width
                    asset.height = height
                    asset.sha256 = digest
                    asset.source_y0 = source_y0
                    asset.source_y1 = source_y1
                    asset.save(update_fields=("image_data", "width", "height", "sha256", "source_y0", "source_y1"))
                    continue
                target = Question.objects.create(
                    uuid=new_uuids[index - 1],
                    document=question.document,
                    topic=question.topic,
                    similarity_topic=question.similarity_topic,
                    question_order=question.question_order + index,
                    source_label=label,
                    display_label=label,
                    prompt_text=prompt,
                    content_mode="image",
                    fingerprint=hashlib.sha256(f"split:{question.uuid}:{index}".encode()).hexdigest(),
                    confidence=0.99,
                    source_category="workbook",
                    record_kind="question",
                    is_practiceable=True,
                    classification_reason="split from a historically joined question crop",
                    classification_confidence=0.99,
                    topic_classification_source="record-split",
                    topic_classification_confidence=0.99,
                )
                QuestionAsset.objects.create(
                    source_id=_source_id(digest), question=target, position=0,
                    asset_type="question_crop", sha256=digest, mime_type="image/png",
                    image_data=png, width=width, height=height,
                    source_page_index=asset.source_page_index, source_x0=asset.source_x0,
                    source_y0=source_y0, source_x1=asset.source_x1, source_y1=source_y1,
                    render_dpi=asset.render_dpi,
                )
                created.append(str(target.uuid))
            for redundant_asset in assets[1:]:
                redundant_asset.delete()
            self.stdout.write(self.style.SUCCESS(f"Created {', '.join(created)}"))

        if not options["apply"]:
            self.stdout.write("Dry run only; pass --apply to write the repairs.")
            transaction.set_rollback(True)
