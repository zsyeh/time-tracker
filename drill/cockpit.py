import datetime

from django.db.models import Q
from django.utils import timezone

from .models import Question, QuestionDocument, QuestionTopic, TopicMastery


COURSES = (
    ('circuit', '电路', ('电路',)),
    ('analog', '模拟电子技术', ('模拟电子', '模电')),
    ('digital', '数字电子技术', ('数字电子', '数电')),
    ('signals', '信号与系统', ('信号与系统', '信号课后')),
    ('communication', '通信原理', ('通信原理', '通信课后')),
)


def course_for_title(title):
    for code, label, needles in COURSES:
        if any(needle in title for needle in needles):
            return code, label
    return None, None


def syllabus_documents():
    """Select the five canonical syllabus documents, excluding exercise supplements."""
    result = {}
    for document in QuestionDocument.objects.filter(workspace='ei').order_by('id'):
        title = document.display_title or document.title
        code, _label = course_for_title(title)
        if not code or code in result or any(token in title for token in ('课后题', '例题精解')):
            continue
        result[code] = document
    return result


def syllabus_topics():
    documents = syllabus_documents()
    return QuestionTopic.objects.filter(
        document_id__in=[item.pk for item in documents.values()], level=2,
    ).select_related('document', 'parent').order_by('document_id', 'sort_order')


def schedule_for_grade(grade, *, now=None, streak=0):
    now = now or timezone.now()
    days = {'D': 0, 'C': 1, 'B': 3, 'A': min(30, (7, 14, 30)[min(streak, 2)])}[grade]
    return now + datetime.timedelta(days=days)


def apply_mastery_grade(record, grade, *, independent=None, reviewed=False, now=None):
    now = now or timezone.now()
    record.grade = grade
    if reviewed:
        record.review_count += 1
        record.last_reviewed_at = now
        record.correct_streak = record.correct_streak + 1 if grade in ('A', 'B') else 0
    if independent is not None:
        record.independent_last_time = independent
    record.retention_score = {'A': 100, 'B': 72, 'C': 35, 'D': 0}[grade]
    record.next_review_at = schedule_for_grade(grade, now=now, streak=record.correct_streak)
    return record


def eligible_topic_questions(topic):
    return Question.objects.filter(
        document__workspace='ei', similarity_topic=topic, is_practiceable=True,
    ).exclude(syllabus_scope='out_of_scope')
