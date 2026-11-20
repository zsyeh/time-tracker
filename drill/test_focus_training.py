"""Focused regression coverage for image-only training and aggregate sharing."""
import io
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import RequestFactory
import pymupdf
from .models import ExamBlueprint, ExamBlueprintSection, QuestionDocument, Question, QuestionAsset, QuestionAttempt, ExamPaper, DrillContentShare
from .paper_generator import PaperGenerator, PaperGenerationError
from .paper_pdf import render_paper_pdf
from .sharing import public_share_context, share_markdown
from .views import paper_queryset, exam_paper_payload


class FocusTrainingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('focus-fixture')
        self.bp = ExamBlueprint.objects.create(code='math2-focus-test', title='数学二测试', subject='math2', mode='standard', version=99, duration_minutes=180, total_score=10, cooldown_days=0)
        self.doc = QuestionDocument.objects.create(source_id=998001, workspace='drill', title='一元微分', filename='x.pdf', sha256='a'*64, page_count=1)
        self.linear = QuestionDocument.objects.create(source_id=998002, workspace='drill', title='线性代数', filename='y.pdf', sha256='b'*64, page_count=1)
        self.section = ExamBlueprintSection.objects.create(blueprint=self.bp, order=1, title='高数选择', question_type='single_choice', question_count=1, score_per_question=5, chapter_weights={'$subject_area':'calculus'})
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 200), False)
        pix.clear_with(255)
        self.image = io.BytesIO(pix.tobytes('png'))

    def question(self, n, *, document=None, images=True):
        q = Question.objects.create(document=document or self.doc, question_order=n, source_label=f'Q{n}', display_label=f'Q{n}', subject='math2', question_type='single_choice', question_type_human_verified=True, prompt_text='NOISY OCR '*20, answer_markdown='NOISY ANSWER OCR', fingerprint=f'{n:064x}')
        if images:
            for i, kind in enumerate(('question_crop','answer_crop')):
                QuestionAsset.objects.create(question=q, source_id=998000+n*2+i, position=i, asset_type=kind, sha256=f'{n*2+i:064x}', image_data=self.image.getvalue(), width=400, height=200)
        return q

    def test_blueprint_quotas_and_duration(self):
        for mode, counts, minutes in [('standard',[7,3,5,1,5,1],180),('intensive',[11,4,7,2,7,2],240)]:
            bp = ExamBlueprint.objects.get(code=f'math2-focus-{mode}-v2')
            sections = list(bp.sections.order_by('order'))
            self.assertEqual([s.question_count for s in sections], counts)
            self.assertEqual(bp.duration_minutes, minutes)
            self.assertEqual(sum(s.question_count*s.score_per_question for s in sections),bp.total_score)

    def test_image_only_area_and_no_automatic_attempt(self):
        self.question(1, images=False)
        self.question(2, document=self.linear)
        expected = self.question(3)
        paper = PaperGenerator().generate(user=self.user, blueprint=self.bp, include_mastered=True)
        self.assertEqual(list(paper.items.values_list('question_id',flat=True)),[expected.pk])
        self.assertEqual(QuestionAttempt.objects.count(),0)
        payload = exam_paper_payload(paper_queryset(self.user).get(pk=paper.pk),review=True)
        self.assertEqual(payload['items'][0]['id'],paper.items.get().pk)
        self.assertEqual(payload['items'][0]['question']['prompt_text'],'')
        self.assertEqual(payload['items'][0]['question']['answer_markdown'],'')
        self.assertTrue(render_paper_pdf(paper).startswith(b'%PDF'))
        self.assertNotIn(b'NOISY',render_paper_pdf(paper,solutions=True))

    def test_exclusions_do_not_silently_relax_or_persist_partial_paper(self):
        q = self.question(1)
        QuestionAttempt.objects.create(user=self.user, question=q, result='review')
        with self.assertRaises(PaperGenerationError):
            PaperGenerator().generate(user=self.user, blueprint=self.bp, exclude_review=True)
        self.assertEqual(ExamPaper.objects.count(),0)
        with self.assertRaises(PaperGenerationError):
            PaperGenerator().generate(user=self.user, blueprint=self.bp, document_ids=[self.linear.pk])

    def test_aggregate_links_use_public_domain_and_expose_no_notes(self):
        q = self.question(1)
        paper = PaperGenerator().generate(user=self.user, blueprint=self.bp)
        item = paper.items.get(); item.user_answer='PRIVATE NOTE'; item.save()
        DrillContentShare.get_or_issue(owner=self.user, workspace='drill', question=q)
        share, token, _ = DrillContentShare.get_or_issue(owner=self.user,workspace='drill',paper=paper)
        req = RequestFactory().get('/', HTTP_X_FORWARDED_PREFIX='/drill', HTTP_X_TIME_TRACKER_EXTERNAL_HOST='47.95.10.128')
        context = public_share_context(req,share,token)
        self.assertTrue(context['items'][0]['share_url'].startswith('https://drill.ehzsy.site/share/'))
        self.assertNotIn('PRIVATE NOTE',str(context))
        self.assertNotIn('NOISY',share_markdown(context))
        self.assertEqual(context['items'][0]['practice_path'],f'/drill/practice/{q.uuid}')
