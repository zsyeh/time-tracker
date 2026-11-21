"""Replacement must preserve selection rules and paper ownership."""
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import DrillContentShare, QuestionAttempt, QuestionErratum, QuestionUserState
from .paper_generator import PaperGenerator
from . import test_focus_training
from . import test_ei_papers
from .views import DrillPaperItemReplaceView


class ReplaceApiMixin:
    def replace(self, paper, *, position=1, user=None, workspace='drill', expected=None, question=None):
        data = {'expected_question_uuid': str(expected or paper.items.get(position=position).question.uuid)}
        if question:
            data['question_uuid'] = str(question.uuid)
        request = APIRequestFactory().post('/', data, format='json', HTTP_HOST=f'{workspace}.ehzsy.site')
        request.workspace = workspace
        force_authenticate(request, user=user or self.user)
        return DrillPaperItemReplaceView.as_view()(request, paper_uuid=paper.uuid, position=position)


@override_settings(ALLOWED_HOSTS=['drill.ehzsy.site', 'ei.ehzsy.site'],
                   DRILL_HOSTS={'drill.ehzsy.site'}, EI_HOSTS={'ei.ehzsy.site'})
class MathPaperReplaceTests(ReplaceApiMixin, TestCase):
    setUp = test_focus_training.FocusTrainingTests.setUp
    question = test_focus_training.FocusTrainingTests.question

    def paper(self, **options):
        return PaperGenerator().generate(user=self.user, blueprint=self.bp, **options)

    def test_reset_and_history_without_changing_learning(self):
        original = self.question(1)
        paper = self.paper()
        replacement = self.question(2)
        QuestionAttempt.objects.create(user=self.user, question=original, result='correct')
        QuestionUserState.objects.create(user=self.user, question=original, note='private global note')
        item = paper.items.get()
        item.self_score, item.self_note, item.user_answer = 5, 'private item note', 'answer'
        item.result, item.time_spent_seconds, item.submitted_at = 'correct', 65, timezone.now()
        item.save()
        response = self.replace(paper, question=replacement)
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db(); paper.refresh_from_db()
        self.assertEqual((item.pk, item.position, item.score), (response.data['items'][0]['id'], 1, 5))
        self.assertEqual((item.question_id, item.result, item.self_score, item.self_note, item.user_answer,
                          item.time_spent_seconds, item.submitted_at),
                         (replacement.pk, 'unanswered', None, '', '', None, None))
        self.assertEqual(QuestionAttempt.objects.count(), 1)
        self.assertEqual(QuestionUserState.objects.get().note, 'private global note')
        self.assertEqual(paper.generation_options['replacement_history'][0]['previous_question_uuid'], str(original.uuid))
        self.assertNotIn('generation_options', response.data)
        self.assertNotIn('private item note', str(response.data))
        self.assertIn('answer_assets', response.data['items'][0]['question'])
        self.assertEqual(self.replace(paper, expected=original.uuid).status_code, 409)
        self.assertEqual(self.replace(paper, question=original).status_code, 400)

    def test_stale_item_patch_does_not_attach_old_notes_to_replacement(self):
        from .views import DrillPaperItemView
        original = self.question(1)
        paper = self.paper()
        good = self.question(2)
        self.assertEqual(self.replace(paper, question=good).status_code, 200)
        request = APIRequestFactory().patch('/', {'self_note': 'stale note',
            'expected_question_uuid': str(original.uuid)}, format='json', HTTP_HOST='drill.ehzsy.site')
        force_authenticate(request, user=self.user)
        response = DrillPaperItemView.as_view()(request, paper_uuid=paper.uuid, position=1)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(paper.items.get().self_note, '')

    def test_no_candidates_and_owner_workspace_isolation(self):
        self.question(1)
        paper = self.paper()
        self.assertEqual(self.replace(paper).status_code, 400)
        other = get_user_model().objects.create_user('replace-other')
        self.assertEqual(self.replace(paper, user=other).status_code, 404)
        self.assertEqual(self.replace(paper, workspace='ei').status_code, 404)

    def test_excludes_existing_other_position_and_all_prior_replacements(self):
        self.section.question_count = 2
        self.section.save()
        self.question(1); self.question(2)
        paper = self.paper()
        other_question = paper.items.get(position=2).question
        self.assertEqual(self.replace(paper, question=other_question).status_code, 400)
        self.question(3)
        self.assertEqual(self.replace(paper).status_code, 200)
        self.assertEqual(self.replace(paper).status_code, 400)
        self.assertEqual(paper.items.values('question_id').distinct().count(), 2)

    def test_saved_filters_and_open_errata_are_not_relaxed(self):
        self.question(1)
        paper = self.paper(exclude_review=True, document_ids=[self.doc.pk], cooldown_days=0)
        mastered = self.question(2)
        review = self.question(3)
        erratum = self.question(4)
        wrong_area = self.question(5, document=self.linear)
        QuestionAttempt.objects.create(user=self.user, question=mastered, result='correct')
        QuestionUserState.objects.create(user=self.user, question=review, review_later=True)
        QuestionErratum.objects.create(question=erratum, description='source issue')
        for q in (mastered, review, erratum, wrong_area):
            self.assertEqual(self.replace(paper, question=q).status_code, 400)
        good = self.question(6)
        self.assertEqual(self.replace(paper, question=good).status_code, 200)
        paper.refresh_from_db()
        self.assertEqual(paper.generation_options['document_ids'], [self.doc.pk])

    def test_shared_paper_is_immutable(self):
        self.question(1)
        paper = self.paper()
        self.question(2)
        DrillContentShare.issue(owner=self.user, workspace='drill', paper=paper)
        before = paper.items.get().question_id
        response = self.replace(paper)
        self.assertEqual((response.status_code, response.data['code']), (409, 'paper_already_shared'))
        self.assertEqual(paper.items.get().question_id, before)

    def test_legacy_options_warn_and_use_relaxed_user_filters(self):
        self.question(1)
        paper = self.paper()
        paper.generation_options = {}; paper.save(update_fields=('generation_options',))
        candidate = self.question(2)
        QuestionAttempt.objects.create(user=self.user, question=candidate, result='correct')
        response = self.replace(paper, question=candidate)
        self.assertEqual(response.status_code, 200)
        self.assertIn('warning', response.data['replacement'])


@override_settings(ALLOWED_HOSTS=['drill.ehzsy.site', 'ei.ehzsy.site'],
                   DRILL_HOSTS={'drill.ehzsy.site'}, EI_HOSTS={'ei.ehzsy.site'})
class EiPaperReplaceTests(ReplaceApiMixin, TestCase):
    setUp = test_ei_papers.EiCandidateTests.setUp
    document_for = test_ei_papers.EiCandidateTests.document_for
    question = test_ei_papers.EiCandidateTests.question

    def test_same_final_format_and_course(self):
        from .models import ExamBlueprint, ExamBlueprintSection
        bp = ExamBlueprint.objects.create(code='ei-focus-replace', title='EI replace', subject='ei', mode='standard',
            version=99, duration_minutes=180, total_score=3, cooldown_days=0)
        ExamBlueprintSection.objects.create(blueprint=bp, order=1, title='数电选择',
            question_type='single_choice', question_count=1, score_per_question=3,
            chapter_weights={'$exam_type': 'choice', '$course': 'digital'})
        self.question()
        paper = PaperGenerator().generate(user=self.user, blueprint=bp)
        wrong_format = self.question('large')
        wrong_course = self.question(document=self.document_for(88003, '模拟电子技术'), similarity_topic=None)
        good = self.question()
        for q in (wrong_format, wrong_course):
            self.assertEqual(self.replace(paper, question=q, workspace='ei').status_code, 400)
        response = self.replace(paper, question=good, workspace='ei')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['items'][0]['question']['uuid'], str(good.uuid))
        self.assertEqual(response.data['items'][0]['score'], 3)
        self.assertEqual(self.replace(paper, workspace='drill').status_code, 404)


@override_settings(ALLOWED_HOSTS=['drill.ehzsy.site', 'ei.ehzsy.site'],
                   DRILL_HOSTS={'drill.ehzsy.site'}, EI_HOSTS={'ei.ehzsy.site'})
class ConcurrentPaperReplaceTests(ReplaceApiMixin, TransactionTestCase):
    setUp = test_focus_training.FocusTrainingTests.setUp
    question = test_focus_training.FocusTrainingTests.question

    @skipUnlessDBFeature('has_select_for_update')
    def test_different_positions_cannot_choose_the_same_last_candidate(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        self.section.question_count = 2
        self.section.save()
        self.question(1); self.question(2)
        paper = PaperGenerator().generate(user=self.user, blueprint=self.bp)
        self.question(3)
        expected = {item.position: item.question.uuid for item in paper.items.all()}
        barrier = Barrier(2)

        def replace(position):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return self.replace(paper, position=position, expected=expected[position]).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as workers:
            codes = list(workers.map(replace, (1, 2)))
        self.assertEqual(sorted(codes), [200, 400])
        self.assertEqual(paper.items.values('question_id').distinct().count(), 2)
        paper.refresh_from_db()
        self.assertEqual(len(paper.generation_options['replacement_history']), 1)
