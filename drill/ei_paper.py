"""EI paper candidates, using source formats and complete source image pairs."""
import datetime

from django.db.models import Exists, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Length
from django.utils import timezone

from .cockpit import COURSES, course_for_title
from .exam_types import with_exam_type
from .models import (
    ExamPaperItem, Question, QuestionAsset, QuestionAttempt, QuestionErratum,
    QuestionUserState,
)


# Official syllabus: 180 minutes, 150 points; five courses about 20% each;
# choice/fill/short answer/calculation totals 30/30/30/60. It gives no item
# counts. These counts are a training configuration fitted to available images.
EI_TRAINING_COUNTS = {
    'circuit': (0, 2, 2, 1),
    'analog': (4, 4, 1, 0),
    'digital': (4, 2, 0, 1),
    'signals': (2, 2, 1, 1),
    'communication': (0, 0, 1, 2),
}
EI_EXAM_TYPES = ('choice', 'fill', 'short_answer', 'large')
EI_TYPE_SCORES = (3, 3, 6, 12)
EI_LEGACY_TYPES = dict(zip(EI_EXAM_TYPES, ('single_choice', 'fill_blank', 'solution', 'solution')))


def ei_candidate_pool(*, user, question_type, exam_type, include_mastered,
                      cooldown_days, excluded_ids):
    """Return eligible EI questions without relabelling or filling shortages."""
    if EI_LEGACY_TYPES.get(exam_type) != question_type:
        return []
    latest = QuestionAttempt.objects.filter(user=user, question_id=OuterRef('pk')).order_by('-created_at', '-pk')
    state = QuestionUserState.objects.filter(user=user, question_id=OuterRef('pk'))
    # Length(BinaryField) uses octet length on PostgreSQL and avoids loading
    # image bytes into Python while rejecting placeholder empty blobs.
    assets = QuestionAsset.objects.filter(question_id=OuterRef('pk')).annotate(
        image_byte_count=Length('image_data'),
    ).filter(image_byte_count__gt=0)
    unresolved = QuestionErratum.objects.filter(
        question_id=OuterRef('pk'), status__in=('open', 'reviewing'),
    )
    queryset = with_exam_type(Question.objects.filter(
        document__workspace='ei', subject='ei', is_practiceable=True,
        record_kind='question',
    )).filter(final_question_type=exam_type).exclude(
        syllabus_scope='out_of_scope',
    ).exclude(pk__in=excluded_ids).select_related(
        'document', 'similarity_topic', 'similarity_topic__document',
    ).annotate(
        has_readable_question_crop=Exists(assets.filter(asset_type='question_crop', height__gte=120)),
        has_answer_crop=Exists(assets.filter(asset_type='answer_crop', height__gte=60)),
        unresolved_paper_erratum=Exists(unresolved),
        latest_result_for_paper=Subquery(latest.values('result')[:1]),
        latest_attempt_at=Subquery(latest.values('created_at')[:1]),
        paper_review_later=Exists(state.filter(review_later=True)),
        paper_attempt_count=Value(0, output_field=IntegerField()),
        paper_error_count=Value(0, output_field=IntegerField()),
        paper_marker_count=Value(0, output_field=IntegerField()),
        prior_paper_time=Value(0, output_field=IntegerField()),
    ).filter(has_readable_question_crop=True, has_answer_crop=True, unresolved_paper_erratum=False)
    if not include_mastered:
        queryset = queryset.filter(Q(latest_result_for_paper__isnull=True) | ~Q(latest_result_for_paper__in=('done', 'correct')))
    if cooldown_days:
        cutoff = timezone.now() - datetime.timedelta(days=cooldown_days)
        recent = ExamPaperItem.objects.filter(
            paper__user=user, paper__created_at__gte=cutoff, question_id=OuterRef('pk'),
        )
        queryset = queryset.annotate(recently_selected_for_paper=Exists(recent)).filter(
            Q(latest_attempt_at__isnull=True) | Q(latest_attempt_at__lt=cutoff),
            recently_selected_for_paper=False,
        )
    result = []
    for question in queryset.order_by('document_id', 'question_order', 'pk'):
        document = question.similarity_topic.document if question.similarity_topic_id else question.document
        title = document.display_title or document.title
        # Mixed-source books need an assigned canonical topic; a title naming
        # both analog and digital cannot establish one course by itself.
        matches = {code for code, _label, needles in COURSES if any(needle in title for needle in needles)}
        question.paper_course, _ = course_for_title(title)
        if question.paper_course and len(matches) == 1:
            result.append(question)
    return result
