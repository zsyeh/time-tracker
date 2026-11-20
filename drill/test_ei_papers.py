import datetime
from collections import Counter

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from .ei_paper import ei_candidate_pool
from .models import (
    ExamBlueprint, ExamPaper, ExamPaperItem, Question, QuestionAsset, QuestionAttempt, QuestionDocument,
    QuestionErratum, QuestionExamType, QuestionRevision, QuestionTopic, QuestionUserState,
)


class EiBlueprintTests(TestCase):
    def test_training_configuration_preserves_official_score_totals(self):
        blueprint = ExamBlueprint.objects.get(code='ei-focus-standard-v1')
        sections = list(blueprint.sections.order_by('order'))
        self.assertEqual((blueprint.subject, blueprint.duration_minutes, blueprint.total_score), ('ei', 180, 150))
        self.assertEqual(len(sections), 15)
        self.assertEqual(sum(s.question_count for s in sections), 30)
        courses, formats, counts = Counter(), Counter(), Counter()
        for section in sections:
            course = section.chapter_weights['$course']
            kind = section.chapter_weights['$exam_type']
            score = section.question_count * section.score_per_question
            courses[course] += score
            formats[kind] += score
            counts[kind] += section.question_count
        self.assertEqual(dict(courses), dict.fromkeys(('circuit', 'analog', 'digital', 'signals', 'communication'), 30))
        self.assertEqual(dict(formats), {'choice': 30, 'fill': 30, 'short_answer': 30, 'large': 60})
        self.assertEqual(dict(counts), {'choice': 10, 'fill': 10, 'short_answer': 5, 'large': 5})


class EiCandidateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('ei-exam-owner')
        self.other = get_user_model().objects.create_user('ei-exam-other')
        self.document = self.document_for(88001, '电子线路（数电·模电）')
        self.canonical = self.document_for(88002, '892 · 数字电子技术')
        self.topic = QuestionTopic.objects.create(
            source_id=88001, document=self.canonical, title='同步时序逻辑',
            normalized_title='同步时序逻辑', level=2, sort_order=1,
        )
        self.next_id = 88000

    def document_for(self, number, title):
        return QuestionDocument.objects.create(
            source_id=number, workspace='ei', filename=f'{number}.pdf',
            title=title, sha256=f'{number:064x}', page_count=10,
        )

    def question(self, kind='choice', *, images=True, **overrides):
        self.next_id += 1
        number = self.next_id
        fields = dict(
            document=self.document, similarity_topic=self.topic,
            subject='ei', question_order=number, source_label=str(number),
            fingerprint=f'{number:064x}', question_type='solution',
            is_practiceable=True, record_kind='question', syllabus_scope='in_scope',
        )
        fields.update(overrides)
        question = Question.objects.create(**fields)
        QuestionExamType.objects.create(
            question=question, source_system='ei', question_type=kind,
            classification_source='human', classification_version='test',
            content_hash='a' * 64, review_required=True, batch_id='test',
        )
        if images:
            for offset, asset_type in enumerate(('question_crop', 'answer_crop')):
                QuestionAsset.objects.create(
                    source_id=number * 2 + offset, question=question,
                    asset_type=asset_type, sha256=f'{number * 2 + offset:064x}',
                    image_data=b'nonempty-source-image', width=500, height=300,
                )
        return question

    def pool(self, kind='choice', **overrides):
        args = dict(user=self.user, question_type={'choice': 'single_choice', 'fill': 'fill_blank', 'short_answer': 'solution', 'large': 'solution'}[kind],
                    exam_type=kind, include_mastered=True, cooldown_days=0, excluded_ids=set())
        args.update(overrides)
        return ei_candidate_pool(**args)

    def test_final_format_and_canonical_course_override_source_and_legacy(self):
        good = self.question()
        self.question('large')
        self.question(similarity_topic=None)  # Mixed source cannot identify a course.
        fallback = self.question(document=self.canonical, similarity_topic=None)
        found = self.pool()
        self.assertEqual([q.pk for q in found], [good.pk, fallback.pk])
        self.assertEqual(found[0].paper_course, 'digital')
        self.assertTrue(found[0].has_readable_question_crop)
        self.assertTrue(found[0].has_answer_crop)
        self.assertEqual(self.pool(question_type='solution'), [])

    def test_missing_empty_small_images_scope_errata_and_exclusions(self):
        good = self.question()
        self.question(images=False)
        empty = self.question()
        empty.assets.filter(asset_type='answer_crop').update(image_data=b'')
        small = self.question()
        small.assets.filter(asset_type='question_crop').update(height=119)
        self.question(syllabus_scope='out_of_scope')
        self.question(is_practiceable=False)
        self.question(record_kind='section')
        flagged = self.question()
        QuestionErratum.objects.create(question=flagged, description='broken source', status='reviewing')
        self.assertEqual([q.pk for q in self.pool()], [good.pk])
        self.assertEqual(self.pool(excluded_ids={good.pk}), [])

    def test_latest_mastery_cooldown_and_review_state_are_user_scoped(self):
        mastered = self.question()
        recent = self.question()
        old = self.question()
        QuestionAttempt.objects.create(user=self.user, question=mastered, result='correct')
        QuestionAttempt.objects.create(user=self.user, question=recent, result='review')
        attempt = QuestionAttempt.objects.create(user=self.user, question=old, result='review')
        QuestionAttempt.objects.filter(pk=attempt.pk).update(created_at=timezone.now() - datetime.timedelta(days=15))
        QuestionUserState.objects.create(user=self.user, question=old, review_later=True)
        QuestionAttempt.objects.create(user=self.other, question=old, result='correct')
        self.assertEqual({q.pk for q in self.pool(include_mastered=False)}, {recent.pk, old.pk})
        found = self.pool(cooldown_days=14)
        self.assertEqual([q.pk for q in found], [old.pk])
        self.assertTrue(found[0].paper_review_later)

    def test_recently_selected_paper_cooldown(self):
        question = self.question()
        blueprint = ExamBlueprint.objects.get(code='ei-focus-standard-v1')
        paper = ExamPaper.objects.create(user=self.user, blueprint=blueprint, seed=1, mode='standard')
        ExamPaperItem.objects.create(
            paper=paper, section=blueprint.sections.first(), question=question,
            question_revision=QuestionRevision.capture(question),
            position=1, score=3, selected_fingerprint=question.fingerprint,
        )
        self.assertEqual(self.pool(cooldown_days=14), [])
        ExamPaper.objects.filter(pk=paper.pk).update(created_at=timezone.now() - datetime.timedelta(days=15))
        self.assertEqual([q.pk for q in self.pool(cooldown_days=14)], [question.pk])

    @override_settings(ALLOWED_HOSTS=['ei.test', 'drill.test'], EI_HOSTS=['ei.test'], DRILL_HOSTS=['drill.test'])
    def test_complete_paper_generation_and_workspace_isolation(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .paper_generator import PaperGenerator
        from .serializers import ExamPaperCreateSerializer
        from .views import DrillPaperReviewView
        blueprint = ExamBlueprint.objects.get(code='ei-focus-standard-v1')
        titles = {'circuit': '电路原理', 'analog': '模拟电子技术', 'digital': '数字电子技术', 'signals': '信号与系统', 'communication': '通信原理'}
        for index, section in enumerate(blueprint.sections.order_by('order')):
            doc = self.document_for(89000 + index, titles[section.chapter_weights['$course']])
            for _ in range(section.question_count):
                self.question(section.chapter_weights['$exam_type'], document=doc, similarity_topic=None)
        paper = PaperGenerator().generate(user=self.user, blueprint=blueprint, seed=5, include_mastered=True)
        self.assertEqual(paper.items.count(), 30)
        self.assertEqual(sum(item.score for item in paper.items.all()), 150)
        self.assertTrue(ExamPaperCreateSerializer(data={'blueprint': blueprint.code}, context={'workspace': 'ei'}).is_valid())
        self.assertFalse(ExamPaperCreateSerializer(data={'blueprint': blueprint.code}, context={'workspace': 'drill'}).is_valid())
        factory = APIRequestFactory()
        for workspace, expected in [('ei', 200), ('drill', 404)]:
            request = factory.get('/api/drill/papers/review/', HTTP_HOST=f'{workspace}.test')
            force_authenticate(request, user=self.user)
            response = DrillPaperReviewView.as_view()(request, paper_uuid=paper.uuid)
            self.assertEqual(response.status_code, expected)
            if expected == 200:
                self.assertEqual(len(response.data['items']), 30)
                self.assertTrue(all(item['question']['prompt_text'] == '' for item in response.data['items']))
