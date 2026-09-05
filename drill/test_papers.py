import datetime

from django.contrib.auth import get_user_model
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from .models import (
    ExamBlueprint, ExamBlueprintSection, Question, QuestionAttempt,
    QuestionAsset, QuestionDocument, QuestionRevision, QuestionTopic,
)
from .paper_generator import PaperGenerationError, PaperGenerator
from .paper_pdf import render_paper_pdf


class PaperGeneratorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('paper-owner', password='x')
        self.document = QuestionDocument.objects.create(
            source_id=7001, workspace='drill', filename='math.pdf', title='Math II',
            sha256='7' * 64, page_count=10,
        )
        self.topics = [
            QuestionTopic.objects.create(
                source_id=7100 + index, document=self.document, title=f'Topic {index}',
                display_title=f'Topic {index}', normalized_title=f'topic-{index}',
                level=1, sort_order=index,
            )
            for index in range(1, 4)
        ]
        self.questions = []
        order = 1
        for question_type in ('single_choice', 'fill_blank', 'solution'):
            for index in range(6):
                topic = self.topics[index % len(self.topics)]
                self.questions.append(Question.objects.create(
                    document=self.document, topic=topic, similarity_topic=topic,
                    question_order=order, source_label=f'{question_type}-{index}',
                    display_label=f'{question_type}-{index}', prompt_text='question',
                    content_mode='text', fingerprint=f'{order:064x}',
                    subject='math2', question_type=question_type,
                    question_type_source='human', question_type_confidence=1,
                    question_type_human_verified=True,
                ))
                order += 1
        self.blueprint = ExamBlueprint.objects.create(
            code='test-math2-v1', title='Test Math II', subject='math2', mode='standard',
            version=99, duration_minutes=30, total_score=30, cooldown_days=14,
        )
        for order, question_type in enumerate(('single_choice', 'fill_blank', 'solution'), 1):
            ExamBlueprintSection.objects.create(
                blueprint=self.blueprint, order=order, title=question_type,
                question_type=question_type, question_count=2,
                score_per_question=5, max_per_topic=1,
            )

    def test_mastered_and_recent_questions_are_excluded(self):
        choice = [item for item in self.questions if item.question_type == 'single_choice']
        QuestionAttempt.objects.create(user=self.user, question=choice[0], result='correct')
        QuestionAttempt.objects.create(user=self.user, question=choice[1], result='review')

        paper = PaperGenerator().generate(user=self.user, blueprint=self.blueprint, seed=42)
        selected = set(paper.items.values_list('question_id', flat=True))

        self.assertNotIn(choice[0].pk, selected)
        self.assertNotIn(choice[1].pk, selected)

    def test_question_type_counts_uniqueness_and_order_are_persistent(self):
        paper = PaperGenerator().generate(user=self.user, blueprint=self.blueprint, seed=7)
        first_order = list(paper.items.values_list('question_id', flat=True))
        counts = {
            question_type: paper.items.filter(question__question_type=question_type).count()
            for question_type in ('single_choice', 'fill_blank', 'solution')
        }

        paper.refresh_from_db()
        self.assertEqual(counts, {'single_choice': 2, 'fill_blank': 2, 'solution': 2})
        self.assertEqual(len(first_order), len(set(first_order)))
        self.assertEqual(first_order, list(paper.items.values_list('question_id', flat=True)))
        self.assertFalse(paper.items.filter(question_revision__isnull=True).exists())

    def test_topic_cap_avoids_abnormal_concentration(self):
        paper = PaperGenerator().generate(user=self.user, blueprint=self.blueprint, seed=9)
        for section in self.blueprint.sections.all():
            topic_ids = list(paper.items.filter(section=section).values_list(
                'question__similarity_topic_id', flat=True,
            ))
            self.assertEqual(len(topic_ids), len(set(topic_ids)))

    def test_old_attempt_is_eligible_after_cooldown(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        old = QuestionAttempt.objects.create(user=self.user, question=choice, result='review')
        QuestionAttempt.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=15),
        )
        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=14, excluded_ids=set(),
        )
        self.assertIn(choice.pk, {item.pk for item in pool})

    def test_low_confidence_agent_label_is_not_used_in_strict_paper(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.question_type_source = 'agent'
        choice.question_type_confidence = 0.62
        choice.question_type_human_verified = False
        choice.save(update_fields=(
            'question_type_source', 'question_type_confidence',
            'question_type_human_verified',
        ))

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertNotIn(choice.pk, {item.pk for item in pool})

    def test_insufficient_candidates_raise_clear_error(self):
        self.blueprint.sections.filter(question_type='single_choice').update(question_count=20)
        with self.assertRaises(PaperGenerationError) as raised:
            PaperGenerator().generate(user=self.user, blueprint=self.blueprint, seed=1)
        self.assertEqual(raised.exception.required, 20)
        self.assertEqual(raised.exception.available, 6)

    def test_deleting_unrelated_question_does_not_change_paper(self):
        paper = PaperGenerator().generate(user=self.user, blueprint=self.blueprint, seed=12)
        selected = list(paper.items.values_list('question_id', flat=True))
        Question.objects.exclude(pk__in=selected).first().delete()
        self.assertEqual(selected, list(paper.items.values_list('question_id', flat=True)))

    def test_api_persists_paper_and_keeps_answers_out_of_exam_mode(self):
        self.questions[0].answer_markdown = '## Correct answer'
        self.questions[0].save(update_fields=('answer_markdown',))
        self.client.force_login(self.user)
        response = self.client.post(
            '/api/drill/papers/',
            {'blueprint': self.blueprint.code, 'seed': 123},
            content_type='application/json',
            secure=True,
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(len(payload['items']), 6)
        self.assertNotIn('answer_markdown', payload['items'][0]['question'])
        paper_uuid = payload['uuid']

        review = self.client.get(f'/api/drill/papers/{paper_uuid}/review/', secure=True)
        self.assertEqual(review.status_code, 200)
        self.assertIn('answer_markdown', review.json()['items'][0]['question'])
        self.assertEqual(self.client.get('/api/drill/papers/', secure=True).json()['results'][0]['uuid'], paper_uuid)

    def test_other_user_cannot_access_paper(self):
        paper = PaperGenerator().generate(user=self.user, blueprint=self.blueprint, seed=4)
        other = get_user_model().objects.create_user('paper-other', password='x')
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/api/drill/papers/{paper.uuid}/', secure=True).status_code, 404)
        self.assertEqual(self.client.get(f'/api/drill/papers/{paper.uuid}/review/', secure=True).status_code, 404)

    def test_item_update_records_answer_and_learning_result(self):
        paper = PaperGenerator().generate(user=self.user, blueprint=self.blueprint, seed=5)
        item = paper.items.first()
        self.client.force_login(self.user)
        response = self.client.patch(
            f'/api/drill/papers/{paper.uuid}/items/{item.position}/',
            {'user_answer': 'My work', 'result': 'incorrect', 'time_spent_seconds': 90},
            content_type='application/json',
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.user_answer, 'My work')
        self.assertEqual(item.time_spent_seconds, 90)
        self.assertTrue(QuestionAttempt.objects.filter(
            user=self.user, question=item.question, result='review',
        ).exists())

    def test_paper_revision_freezes_text_and_answer_for_review(self):
        paper = PaperGenerator().generate(user=self.user, blueprint=self.blueprint, seed=15)
        item = paper.items.select_related('question', 'question_revision').first()
        old_revision = item.question_revision
        item.question.prompt_text = 'changed after paper generation'
        item.question.answer_markdown = '## New answer that must not leak into the old paper'
        item.question.save(update_fields=('prompt_text', 'answer_markdown'))
        new_revision = QuestionRevision.capture(item.question)

        self.assertNotEqual(old_revision.pk, new_revision.pk)
        self.assertEqual(old_revision.prompt_text, 'question')
        self.assertEqual(old_revision.answer_markdown, '')
        self.client.force_login(self.user)
        review = self.client.get(f'/api/drill/papers/{paper.uuid}/review/', secure=True)
        matching = next(
            row for row in review.json()['items']
            if row['question']['uuid'] == str(item.question.uuid)
        )
        self.assertEqual(matching['question']['prompt_text'], 'question')
        self.assertEqual(matching['question']['answer_markdown'], '')

    def test_revision_pins_existing_binary_asset_without_copying_it(self):
        question = self.questions[0]
        asset = QuestionAsset.objects.create(
            source_id=7999, question=question, position=0,
            asset_type='question_crop', sha256='d' * 64,
            image_data=b'asset', width=10, height=10,
        )
        revision = QuestionRevision.capture(question)

        self.assertEqual(revision.revision_assets.get().asset_id, asset.pk)
        with self.assertRaises(ProtectedError):
            asset.delete()

    def test_pdf_renderers_read_pinned_question_revision(self):
        Question.objects.filter(pk__in=[item.pk for item in self.questions]).update(
            answer_markdown='## Solution\n\nUse $x=1$.',
        )
        paper = PaperGenerator().generate(user=self.user, blueprint=self.blueprint, seed=15)

        question_pdf = render_paper_pdf(paper, solutions=False)
        solution_pdf = render_paper_pdf(paper, solutions=True)

        self.assertTrue(question_pdf.startswith(b'%PDF'))
        self.assertTrue(solution_pdf.startswith(b'%PDF'))
        self.assertGreater(len(solution_pdf), 500)
        self.client.force_login(self.user)
        response = self.client.get(
            f'/api/drill/papers/{paper.uuid}/pdf/solutions/', secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
