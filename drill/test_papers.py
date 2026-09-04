import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import (
    ExamBlueprint, ExamBlueprintSection, Question, QuestionAttempt,
    QuestionDocument, QuestionTopic,
)
from .paper_generator import PaperGenerationError, PaperGenerator


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
