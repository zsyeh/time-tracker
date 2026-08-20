import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drill.models import Question


MERGES = (
    {
        'parent_uuid': uuid.UUID('1a4916e2-32d6-5042-8d9b-7e61311959b7'),
        'continuation_uuid': uuid.UUID('465ec07e-9563-536b-a7cb-5a67c298af84'),
        'label': '1999 Math II · parameterized linear dependence',
        'prompt': (
            'Let alpha_1=(1,1,1,3)^T, alpha_2=(-1,-3,5,1)^T, '
            'alpha_3=(3,2,-1,p+2)^T, and alpha_4=(-2,-6,10,p)^T. '
            'Determine when the vectors are independent and represent (4,1,6,10)^T; '
            'when dependent, find their rank and a maximal independent subset.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('58d909e7-2f21-5aca-8c5e-9d9b6b1b221b'),
        'continuation_uuid': uuid.UUID('76716d65-abc5-58cf-87de-2f0e7e424351'),
        'label': '1990 Math III · five-variable nonhomogeneous system',
        'prompt': (
            'For the displayed four-equation system in five unknowns, determine the '
            'values of a and b for consistency, find a fundamental solution set of '
            'the associated homogeneous system, and give all solutions.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('8a1e0303-5abe-5db0-970d-886ff307f4bb'),
        'continuation_uuid': uuid.UUID('55dfc48f-a805-5ed2-9a82-d12efc7d17d3'),
        'label': '1994 Math III · Vandermonde-type nonhomogeneous system',
        'prompt': (
            'Analyze the displayed Vandermonde-type system. Prove that it is '
            'inconsistent when a_1,a_2,a_3,a_4 are pairwise distinct; then, for '
            'a_1=a_3=k and a_2=a_4=-k, use the two given solutions to write the '
            'general solution.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('c4099e35-66ff-5fbd-b956-94cac5c029df'),
        'continuation_uuid': uuid.UUID('25f29a98-257a-5564-8204-8d97f33e754f'),
        'label': '1994 Math I · common solutions of two homogeneous systems',
        'prompt': (
            'Find whether the displayed four-variable homogeneous systems I and II '
            'have nonzero common solutions, and give all such common solutions.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('5876a6cf-ef78-5a60-b430-0df9bcc88ffc'),
        'continuation_uuid': uuid.UUID('af4e9e05-5d3a-5578-a203-0b62a01999d0'),
        'label': 'Common solutions from a parameterized fundamental solution set',
        'prompt': (
            'The two displayed vectors form a fundamental solution set of system II. '
            'Determine a, then find every nonzero common solution of systems I and II.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('6f6f616a-f921-5707-a63e-79fa0380d898'),
        'continuation_uuid': uuid.UUID('cd699a7d-7de1-5932-84c7-4942c8224f57'),
        'label': '2002 Math II · inverse matrix equation',
        'prompt': 'Prove A-2I is invertible, then solve for A from the displayed B.',
    },
    {
        'parent_uuid': uuid.UUID('6f6f616a-f921-5707-a63e-79fa0380d898'),
        'continuation_uuid': uuid.UUID('d73a7340-785c-5123-94af-fc4d7953d265'),
        'label': '2002 Math II · inverse matrix equation',
        'prompt': 'Prove A-2I is invertible, then solve for A from the displayed B.',
    },
    {
        'parent_uuid': uuid.UUID('c78b98b6-230e-5195-8703-0f3609a2e46d'),
        'continuation_uuid': uuid.UUID('56dc7d7d-1eca-524a-a460-ef0939fcf244'),
        'label': 'Parameterized vector-group representation',
        'prompt': (
            'Determine a and b such that vector group II can be represented by vector '
            'group I, and give the representation coefficients.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('e346967e-521b-59c2-b212-32053353e0b2'),
        'continuation_uuid': uuid.UUID('152403d2-4f4f-532c-bd37-6ed98f501e3a'),
        'label': '1989 Math III · eigenvalues and inverse transform',
        'prompt': 'Find the eigenvalues of A, then find the eigenvalues of I+A^{-1}.',
    },
    {
        'parent_uuid': uuid.UUID('e346967e-521b-59c2-b212-32053353e0b2'),
        'continuation_uuid': uuid.UUID('4f7c9a99-366d-5969-943f-aaf651a65c82'),
        'label': '1989 Math III · eigenvalues and inverse transform',
        'prompt': 'Find the eigenvalues of A, then find the eigenvalues of I+A^{-1}.',
    },
    {
        'parent_uuid': uuid.UUID('f6f73e45-56f5-53e7-a25c-283928c362e5'),
        'continuation_uuid': uuid.UUID('577bc319-8665-5f30-a53c-babaa376e998'),
        'label': '1998 Math III · rank-one nilpotent matrix',
        'prompt': (
            'For nonzero vectors alpha and beta with alpha^T beta=0 and '
            'A=alpha beta^T, find A^2 and all eigenvalues and eigenvectors of A.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('bdb4c67b-c5ad-5386-94b6-b45dacc49252'),
        'continuation_uuid': uuid.UUID('b0df44b5-0d33-525d-aa81-ae5eca8ad333'),
        'label': '2002 Math III · symmetric matrix polynomial',
        'prompt': (
            'A is a real symmetric 3x3 matrix with A^2+2A=0 and rank two. '
            'Find all eigenvalues and determine when A+kI is positive definite.'
        ),
    },
    {
        'parent_uuid': uuid.UUID('bdb4c67b-c5ad-5386-94b6-b45dacc49252'),
        'continuation_uuid': uuid.UUID('99eca915-b0a1-581a-bdf7-0f73758aca35'),
        'label': '2002 Math III · symmetric matrix polynomial',
        'prompt': (
            'A is a real symmetric 3x3 matrix with A^2+2A=0 and rank two. '
            'Find all eigenvalues and determine when A+kI is positive definite.'
        ),
    },
)


class Command(BaseCommand):
    help = 'Merge known page-break continuations in the linear-algebra source.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        changed = 0
        for spec in MERGES:
            try:
                parent = Question.objects.select_for_update().get(uuid=spec['parent_uuid'])
                continuation = Question.objects.select_for_update().get(
                    uuid=spec['continuation_uuid']
                )
            except Question.DoesNotExist as exc:
                raise CommandError(f'Missing continuation pair: {spec}') from exc
            if not continuation.is_practiceable and not continuation.assets.exists():
                continue
            if continuation.attempts.exists():
                raise CommandError(
                    f'Continuation {continuation.uuid} has attempts and cannot be merged safely'
                )
            self.stdout.write(f'Validated continuation {continuation.uuid} -> {parent.uuid}')
            if not options['apply']:
                changed += 1
                continue

            start = parent.assets.count()
            for offset, asset in enumerate(
                continuation.assets.select_for_update().order_by('position', 'id')
            ):
                asset.question = parent
                asset.position = start + offset
                asset.save(update_fields=('question', 'position'))
            parent.display_label = spec['label']
            parent.prompt_text = spec['prompt']
            parent.content_mode = 'image'
            parent.confidence = 0.99
            parent.save(
                update_fields=('display_label', 'prompt_text', 'content_mode', 'confidence')
            )
            continuation.is_practiceable = False
            continuation.record_kind = 'grouped'
            continuation.classification_reason = (
                f'page-break continuation merged into question {parent.uuid}'
            )
            continuation.classification_confidence = 1.0
            continuation.save(
                update_fields=(
                    'is_practiceable',
                    'record_kind',
                    'classification_reason',
                    'classification_confidence',
                )
            )
            changed += 1

        if not options['apply']:
            self.stdout.write(f'Dry run only; {changed} continuation merge(s) are pending.')
            transaction.set_rollback(True)
        else:
            self.stdout.write(self.style.SUCCESS(f'Applied {changed} continuation merge(s).'))
