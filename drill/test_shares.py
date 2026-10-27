from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import (
    DrillContentShare,
    ExamBlueprint,
    ExamBlueprintSection,
    ExamPaper,
    ExamPaperItem,
    Question,
    QuestionAsset,
    QuestionDocument,
    QuestionRevision,
    QuestionTopic,
)


class DrillContentShareTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='share-owner', password='password')
        self.other = get_user_model().objects.create_user(username='other-user', password='password')
        self.document = QuestionDocument.objects.create(
            source_id=880001,
            workspace='drill',
            filename='share.pdf',
            title='Share source',
            display_title='Calculus source',
            sha256='8' * 64,
            page_count=1,
        )
        self.topic = QuestionTopic.objects.create(
            source_id=880001,
            document=self.document,
            title='Limits',
            display_title='Limits',
            level=1,
            sort_order=1,
        )
        self.question = Question.objects.create(
            document=self.document,
            topic=self.topic,
            similarity_topic=self.topic,
            question_order=1,
            source_label='Source Q1',
            display_label='Limit question',
            prompt_text='Find $\\lim_{x \\to 0} \\frac{\\sin x}{x}$.',
            latex_text='\\lim_{x \\to 0} \\frac{\\sin x}{x}',
            content_mode='text',
            fingerprint='a' * 64,
            answer_markdown='The answer is $1$.',
            answer_source='provided-reference',
            question_type='solution',
        )
        self.asset = QuestionAsset.objects.create(
            source_id=880001,
            question=self.question,
            position=0,
            asset_type='question_crop',
            sha256='b' * 64,
            image_data=b'public-image-bytes',
            width=120,
            height=80,
        )

    def create_question_share(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f'/api/drill/questions/{self.question.uuid}/share/',
            data={},
            content_type='application/json',
            HTTP_HOST='drill.ehzsy.site',
            secure=True,
        )
        self.assertEqual(response.status_code, 201)
        return response.json()['share_url'].split('/share/', 1)[1]

    def test_question_share_is_anonymous_minimal_and_ai_readable(self):
        raw_token = self.create_question_share()
        self.client.logout()

        page = self.client.get(f'/share/{raw_token}', HTTP_HOST='drill.ehzsy.site', secure=True)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Limit question')
        self.assertContains(page, 'The answer is $1$.')
        self.assertNotContains(page, self.user.username)
        self.assertNotContains(page, 'MASTERED')
        self.assertNotContains(page, 'Needs review')
        self.assertContains(page, 'AI-readable Markdown')

        markdown = self.client.get(
            f'/share/{raw_token}/content.md', HTTP_HOST='drill.ehzsy.site', secure=True,
        )
        self.assertEqual(markdown.status_code, 200)
        self.assertEqual(markdown['Content-Type'], 'text/markdown; charset=utf-8')
        self.assertContains(markdown, '### Question')
        self.assertContains(markdown, '### Answer and explanation')
        self.assertContains(markdown, f'/share/{raw_token}/assets/{self.asset.pk}')

        image = self.client.get(
            f'/share/{raw_token}/assets/{self.asset.pk}', HTTP_HOST='drill.ehzsy.site', secure=True,
        )
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.content, b'public-image-bytes')

    def test_question_share_is_bound_to_workspace_and_token(self):
        raw_token = self.create_question_share()
        self.client.logout()
        self.assertEqual(
            self.client.get(f'/share/{raw_token}', HTTP_HOST='ei.ehzsy.site', secure=True).status_code,
            404,
        )
        self.assertEqual(
            self.client.get('/share/question_invalid', HTTP_HOST='drill.ehzsy.site', secure=True).status_code,
            404,
        )
        unrelated = QuestionAsset.objects.create(
            source_id=880002,
            question=self.question,
            position=1,
            asset_type='answer_crop',
            sha256='c' * 64,
            image_data=b'answer',
            width=50,
            height=50,
        )
        other_document = QuestionDocument.objects.create(
            source_id=880002, workspace='drill', filename='other.pdf', title='Other',
            sha256='d' * 64, page_count=1,
        )
        other_question = Question.objects.create(
            document=other_document, question_order=1, content_mode='text',
            fingerprint='e' * 64,
        )
        foreign_asset = QuestionAsset.objects.create(
            source_id=880003, question=other_question, position=0,
            sha256='f' * 64, image_data=b'private', width=20, height=20,
        )
        self.assertEqual(
            self.client.get(
                f'/share/{raw_token}/assets/{foreign_asset.pk}',
                HTTP_HOST='drill.ehzsy.site',
                secure=True,
            ).status_code,
            404,
        )
        self.assertTrue(unrelated.pk)

    def test_paper_share_requires_owner_and_exposes_source_answers(self):
        blueprint = ExamBlueprint.objects.create(
            code='share-paper', title='Shared paper', subject='math2', mode='standard',
            duration_minutes=180, total_score=150, version=99,
        )
        section = ExamBlueprintSection.objects.create(
            blueprint=blueprint, order=1, title='Solutions', question_type='solution',
            question_count=1, score_per_question=10,
        )
        revision = QuestionRevision.capture(self.question)
        paper = ExamPaper.objects.create(
            user=self.user, blueprint=blueprint, seed=123, mode='standard',
        )
        ExamPaperItem.objects.create(
            paper=paper, section=section, question=self.question,
            question_revision=revision, position=1, score=10,
            selected_fingerprint=self.question.fingerprint,
        )

        self.client.force_login(self.other)
        denied = self.client.post(
            f'/api/drill/papers/{paper.uuid}/share/', data={}, content_type='application/json',
            HTTP_HOST='drill.ehzsy.site',
            secure=True,
        )
        self.assertEqual(denied.status_code, 404)

        self.client.force_login(self.user)
        created = self.client.post(
            f'/api/drill/papers/{paper.uuid}/share/', data={}, content_type='application/json',
            HTTP_HOST='drill.ehzsy.site',
            secure=True,
        )
        self.assertEqual(created.status_code, 201)
        raw_token = created.json()['share_url'].split('/share/', 1)[1]
        self.client.logout()
        page = self.client.get(f'/share/{raw_token}', HTTP_HOST='drill.ehzsy.site', secure=True)
        self.assertContains(page, 'Shared paper')
        self.assertContains(page, 'Question 01')
        self.assertContains(page, 'The answer is $1$.')
        self.assertNotContains(page, 'Your answer')

    def test_revoked_share_immediately_stops_working(self):
        raw_token = self.create_question_share()
        share = DrillContentShare.objects.get(token_digest=DrillContentShare.digest(raw_token))
        share.revoke()
        self.client.logout()
        self.assertEqual(
            self.client.get(f'/share/{raw_token}', HTTP_HOST='drill.ehzsy.site', secure=True).status_code,
            404,
        )
