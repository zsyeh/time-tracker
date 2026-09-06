import datetime
import random

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from .models import (
    ExamBlueprint, ExamBlueprintSection, ExamPaper, Question, QuestionAttempt,
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
                    display_label=f'{question_type}-{index}',
                    prompt_text='A complete standalone question prompt.',
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

    def test_recently_generated_paper_questions_observe_cooldown(self):
        paper = PaperGenerator().generate(user=self.user, blueprint=self.blueprint, seed=77)
        selected = set(paper.items.values_list('question_id', flat=True))

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=14, excluded_ids=set(),
        )

        self.assertTrue(selected)
        self.assertTrue(selected.isdisjoint({item.pk for item in pool}))

    def test_same_seed_is_reproducible_without_cooldown(self):
        first = PaperGenerator().generate(
            user=self.user, blueprint=self.blueprint, seed=12345, cooldown_days=0,
        )
        second = PaperGenerator().generate(
            user=self.user, blueprint=self.blueprint, seed=12345, cooldown_days=0,
        )

        self.assertEqual(
            list(first.items.values_list('question_id', flat=True)),
            list(second.items.values_list('question_id', flat=True)),
        )

    def test_empty_paper_can_be_regenerated_without_changing_its_identity(self):
        paper = PaperGenerator().generate(
            user=self.user, blueprint=self.blueprint, seed=101, cooldown_days=0,
        )
        old_uuid = paper.uuid
        old_ids = list(paper.items.values_list('question_id', flat=True))

        call_command(
            'regenerate_empty_exam_paper', str(paper.uuid), seed=202, apply=True,
        )

        paper.refresh_from_db()
        new_ids = list(paper.items.values_list('question_id', flat=True))
        self.assertEqual(paper.uuid, old_uuid)
        self.assertEqual(paper.seed, 202)
        self.assertEqual(paper.status, 'generated')
        self.assertNotEqual(new_ids, old_ids)
        self.assertEqual(ExamPaper.objects.filter(user=self.user).count(), 1)

    def test_paper_with_user_activity_cannot_be_regenerated(self):
        paper = PaperGenerator().generate(
            user=self.user, blueprint=self.blueprint, seed=303, cooldown_days=0,
        )
        item = paper.items.first()
        item.user_answer = 'work in progress'
        item.save(update_fields=('user_answer',))

        with self.assertRaises(CommandError):
            call_command(
                'regenerate_empty_exam_paper', str(paper.uuid), seed=404, apply=True,
            )

    def test_repeated_generation_preserves_all_hard_constraints(self):
        expected = {'single_choice': 2, 'fill_blank': 2, 'solution': 2}
        for seed in range(50):
            paper = PaperGenerator().generate(
                user=self.user, blueprint=self.blueprint,
                seed=seed, cooldown_days=0,
            )
            ids = list(paper.items.values_list('question_id', flat=True))
            counts = {
                question_type: paper.items.filter(
                    question_revision__question_type=question_type,
                ).count()
                for question_type in expected
            }
            self.assertEqual(counts, expected)
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(
                list(paper.items.values_list('position', flat=True)),
                list(range(1, 7)),
            )

    def test_weak_agent_label_is_not_used_in_strict_paper(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.question_type_source = 'agent'
        choice.question_type_confidence = 0.86
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

    def test_neighbor_consensus_label_is_used_in_strict_paper(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.question_type_source = 'neighbor'
        choice.question_type_confidence = 0.87
        choice.question_type_human_verified = False
        choice.save(update_fields=(
            'question_type_source', 'question_type_confidence',
            'question_type_human_verified',
        ))

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertIn(choice.pk, {item.pk for item in pool})

    def test_choice_requires_stronger_agent_evidence_than_a_single_marker(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.question_type_source = 'agent'
        choice.question_type_confidence = 0.91
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

    def test_math_one_or_three_past_exam_is_not_used_in_math_two_paper(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.is_past_exam = True
        choice.source_category = 'past_exam'
        choice.exam_variant = '数三'
        choice.save(update_fields=('is_past_exam', 'source_category', 'exam_variant'))

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertNotIn(choice.pk, {item.pk for item in pool})

    def test_math_one_special_topic_is_not_used_in_math_two_paper(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.similarity_topic.display_title = '数一专项'
        choice.similarity_topic.save(update_fields=('display_title',))

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertNotIn(choice.pk, {item.pk for item in pool})

    def test_explicit_non_math_two_adapted_question_is_not_used(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.source_category = 'adapted_exam'
        choice.exam_variant = '数三'
        choice.save(update_fields=('source_category', 'exam_variant'))

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertNotIn(choice.pk, {item.pk for item in pool})

    def test_single_legacy_link_marker_keeps_a_complete_question_eligible(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.source_label = 'Legacy question >>'
        choice.save(update_fields=('source_label',))

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertIn(choice.pk, {item.pk for item in pool})

    def test_prompt_with_second_source_anchor_is_not_used(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.prompt_text = 'Current complete question\n(k)26 版660 数二第247题'
        choice.save(update_fields=('prompt_text',))

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertNotIn(choice.pk, {item.pk for item in pool})

    def test_prompt_with_second_880_roman_anchor_is_not_used(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.prompt_text = 'Current complete question\nvi)\n880 第一章拓展3 >>'
        choice.save(update_fields=('prompt_text',))

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertNotIn(choice.pk, {item.pk for item in pool})

    def test_bare_bookmark_fragment_is_not_used(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.source_label = 'd) >>'
        choice.save(update_fields=('source_label',))

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertNotIn(choice.pk, {item.pk for item in pool})

    def test_unverified_daguan_crop_batch_is_not_used(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.source_label = '多元微分大观 · worked image'
        choice.save(update_fields=('source_label',))

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertNotIn(choice.pk, {item.pk for item in pool})

    def test_short_image_fragment_is_not_used_in_formal_paper(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.content_mode = 'image'
        choice.save(update_fields=('content_mode',))
        QuestionAsset.objects.create(
            source_id=7999, question=choice, position=0,
            asset_type='question_crop', sha256='6' * 64,
            image_data=b'short-fragment', width=1200, height=80,
        )

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertNotIn(choice.pk, {item.pk for item in pool})

    def test_short_crop_cannot_hide_a_nominal_text_record(self):
        choice = next(item for item in self.questions if item.question_type == 'single_choice')
        choice.prompt_text = 'Short imported label'
        choice.save(update_fields=('prompt_text',))
        QuestionAsset.objects.create(
            source_id=7998, question=choice, position=0,
            asset_type='question_crop', sha256='5' * 64,
            image_data=b'short-fragment', width=1200, height=41,
        )

        pool = PaperGenerator().candidate_pool(
            user=self.user, blueprint=self.blueprint, question_type='single_choice',
            include_mastered=False, cooldown_days=0, excluded_ids=set(),
        )

        self.assertNotIn(choice.pk, {item.pk for item in pool})

    def test_cross_section_document_load_is_balanced_before_rank_score(self):
        other_document = QuestionDocument.objects.create(
            source_id=7201, workspace='drill', filename='other.pdf',
            title='Other chapter', display_title='Other chapter',
            sha256='8' * 64, page_count=1,
        )
        candidates = []
        for index in range(2):
            topic = QuestionTopic.objects.create(
                source_id=7202 + index, document=other_document,
                title=f'Other topic {index}', display_title=f'Other topic {index}',
                level=1, sort_order=index,
            )
            candidates.append(Question.objects.create(
                document=other_document, topic=topic, similarity_topic=topic,
                question_order=index + 1, source_label=f'other-{index}',
                display_label=f'other-{index}',
                prompt_text='A complete standalone question prompt.',
                content_mode='text', fingerprint=f'{7202 + index:064x}',
                subject='math2', question_type='single_choice',
                question_type_source='human', question_type_confidence=1,
                question_type_human_verified=True,
            ))
        section = self.blueprint.sections.get(question_type='single_choice')

        chosen = PaperGenerator().choose_for_section(
            [
                item for item in self.questions
                if item.question_type == 'single_choice'
            ] + candidates,
            section, 'standard', random.Random(1),
            prior_document_counts={self.document.pk: 4},
        )

        self.assertEqual({item.document_id for item in chosen}, {other_document.pk})

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
        self.assertEqual(old_revision.prompt_text, 'A complete standalone question prompt.')
        self.assertEqual(old_revision.answer_markdown, '')
        self.client.force_login(self.user)
        review = self.client.get(f'/api/drill/papers/{paper.uuid}/review/', secure=True)
        matching = next(
            row for row in review.json()['items']
            if row['question']['uuid'] == str(item.question.uuid)
        )
        self.assertEqual(
            matching['question']['prompt_text'],
            'A complete standalone question prompt.',
        )
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
