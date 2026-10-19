import hashlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import pymupdf
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from drill.linear_selected import parse_selected_book
from drill.management.commands.import_linear_selected_pdf import fingerprint
from drill.models import Question, QuestionAsset, QuestionAttempt, QuestionDocument, QuestionRevision
from drill.views import DrillHeatmapView, DrillQuestionAttemptView, DrillQuestionDetailView
from drill_sources.models import SourceQuestionAnchor
from drill.web_views import drill_spa_view, practice_site
from drill.views import request_workspace


@override_settings(ALLOWED_HOSTS=['*'], DEBUG=False, LOGIN_URL='/accounts/login/')
class DedicatedWorkspaceTests(SimpleTestCase):
    @override_settings(DRILL_HOSTS={'172.20.10.2'}, EI_HOSTS={'disabled.invalid'})
    def test_new_private_ip_follows_drill_container_without_stale_ip_redirect(self):
        for host in ['192.168.0.109:8002', '10.12.3.4:8002', '127.0.0.1:8002', '[fd00::123]:8002']:
            request = RequestFactory().get('/selected-heatmap', HTTP_HOST=host)
            request.user = AnonymousUser()
            self.assertEqual(practice_site(request), 'drill')
            self.assertEqual(request_workspace(request), 'drill')
            response = drill_spa_view(request)
            self.assertTrue(response['Location'].startswith('/accounts/login/'))
            self.assertNotIn('172.20.10.2', response['Location'])

    @override_settings(DRILL_HOSTS={'disabled.invalid'}, EI_HOSTS={'172.20.10.2'})
    def test_ei_container_uses_its_own_workspace_on_new_private_ip(self):
        request = RequestFactory().get('/', HTTP_HOST='192.168.0.109:8003')
        self.assertEqual(practice_site(request), 'ei')
        self.assertEqual(request_workspace(request), 'ei')

    @override_settings(DRILL_HOSTS={'drill.example'}, EI_HOSTS={'ei.example'})
    def test_shared_public_server_keeps_hostname_routing(self):
        for host, expected in [('drill.example', 'drill'), ('ei.example', 'ei'), ('8.8.8.8', None)]:
            request = RequestFactory().get('/', HTTP_HOST=host)
            self.assertEqual(practice_site(request), expected)


def make_pdf(path, *, missing_anchor=False):
    pdf = pymupdf.open()
    pdf.new_page(width=595, height=842)
    page = pdf.new_page(width=595, height=842)
    page.insert_text((62, 90), '#001', fontsize=10)
    page.insert_text((62, 130), 'A. 1\nB. 2\nC. 3\nD. 4', fontsize=10)
    page.insert_text((62, 440), '#002', fontsize=10)
    page.insert_text((62, 490), 'det(A) = ______', fontsize=10)
    page = pdf.new_page(width=595, height=842)
    if not missing_anchor:
        page.insert_text((62, 90), '#003', fontsize=10)
    page.insert_text((62, 130), '(1) Find matrix A.', fontsize=10)
    pdf.set_toc([
        [1, '一、行列式', 2], [2, '具体行列式计算', 2],
        [3, '#001 · 2014数一二三', 2], [3, '#002 · 2015数一', 2],
        [1, '二、矩阵', 3], [2, '矩阵乘法', 3], [3, '#003 · 880矩阵综合填空', 3],
    ])
    pdf.save(path); pdf.close()


@override_settings(ALLOWED_HOSTS=['*'], EI_HOSTS={'ei.test'})
class LinearSelectedTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'linear.pdf'
        make_pdf(self.path)
        self.user = get_user_model().objects.create_user(username='linear-owner')
        self.factory = APIRequestFactory()

    def run_import(self, **options):
        output = io.StringIO()
        call_command('import_linear_selected_pdf', str(self.path), stdout=output, **options)
        return output.getvalue()

    def get(self, view, question=None, path='/'):
        request = self.factory.get(path, HTTP_HOST='drill.test')
        force_authenticate(request, user=self.user)
        return view.as_view()(request, **({'question_uuid': question.uuid} if question else {}))

    def test_parser_checks_outline_against_text_and_keeps_chapters(self):
        book = parse_selected_book(self.path)
        self.assertEqual([q.number for q in book.questions], [1, 2, 3])
        self.assertEqual(book.manifest()['by_chapter'], {'一、行列式': 2, '二、矩阵': 1})
        self.assertEqual(book.manifest()['question_page_count'], 2)
        self.assertEqual(book.manifest()['ocr_pages'], [])
        self.assertLess(book.questions[0].y, book.questions[1].y)
        self.assertEqual([q.question_type for q in book.questions], ['single_choice', 'fill_blank', 'solution'])

    def test_dry_run_has_no_database_writes(self):
        manifest = Path(self.temp.name) / 'manifest.json'
        self.run_import(dry_run=True, manifest_output=manifest)
        self.assertEqual(json.loads(manifest.read_text())['question_count'], 3)
        self.assertEqual(QuestionDocument.objects.count(), 0)
        self.assertEqual(QuestionAsset.objects.count(), 0)
        self.assertEqual(SourceQuestionAnchor.objects.count(), 0)

    def test_whole_pages_are_shared_and_repeat_preserves_attempts(self):
        self.run_import()
        first, second, third = list(Question.objects.filter(is_practiceable=True).order_by('question_order'))
        self.assertEqual(QuestionAsset.objects.count(), 2)
        self.assertEqual(Question.objects.count(), 5)  # three questions + two hidden source pages
        anchors = list(SourceQuestionAnchor.objects.order_by('question__question_order'))
        self.assertEqual(anchors[0].asset_id, anchors[1].asset_id)
        self.assertNotEqual(anchors[1].asset_id, anchors[2].asset_id)
        asset = anchors[0].asset
        self.assertEqual((asset.source_x0, asset.source_y0, asset.source_x1, asset.source_y1), (0, 0, 595, 842))
        self.assertEqual((asset.width, asset.height), (1240, 1755))
        QuestionAttempt.objects.create(user=self.user, question=first, result='correct', note='Keep this note')
        first.display_label = 'My reviewed label'; first.save(update_fields=['display_label'])
        with patch('drill.management.commands.import_linear_selected_pdf.pymupdf.Page.get_pixmap', side_effect=AssertionError('Already rendered')):
            self.assertIn('"created_questions": 0', self.run_import())
        self.assertEqual(QuestionAsset.objects.count(), 2)
        first.refresh_from_db(); self.assertEqual(first.display_label, 'My reviewed label')
        self.assertTrue(QuestionAttempt.objects.filter(question=first, note='Keep this note').exists())
        first_detail = self.get(DrillQuestionDetailView, first).data
        second_detail = self.get(DrillQuestionDetailView, second).data
        self.assertEqual(first_detail['state'], 'mastered')
        self.assertEqual(second_detail['state'], 'unattempted')
        self.assertEqual(first_detail['question_assets'][0]['id'], asset.pk)
        self.assertFalse(first_detail['has_answer'])
        self.assertEqual(first_detail['answer_assets'], [])
        self.assertEqual(first_detail['source_context']['anchor']['asset_id'], asset.pk)
        self.assertEqual(len(first_detail['source_context']['anchors']), 2)

    def test_selected_heatmap_includes_new_book_and_legacy_without_fake_answers(self):
        self.run_import()
        other = QuestionDocument.objects.create(source_id=88001, sha256='e'*64, page_count=1, title='Legacy selected')
        Question.objects.create(document=other, question_order=1, fingerprint='e'*64,
                                content_mode='image', answer_source='daguan_answer_guide_pdf')
        response = self.get(DrillHeatmapView, path='/?collection=selected&mode=questions&scope=all')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['question_count'], 4)
        rows = [q for group in response.data['groups'] for q in group['questions']]
        self.assertEqual(sum(bool(q.get('source_indexed')) for q in rows), 3)
        self.assertFalse(Question.objects.filter(source_label__startswith='linear-selected:', answer_source='daguan_answer_guide_pdf').exists())

    def test_paper_revision_pins_shared_page_without_duplicate_image(self):
        self.run_import()
        first = Question.objects.filter(is_practiceable=True).order_by('question_order').first()
        revision = QuestionRevision.capture(first)
        self.assertEqual(list(revision.assets.values_list('pk', flat=True)), [first.source_anchor.asset_id])
        self.assertEqual(QuestionRevision.capture(first).pk, revision.pk)
        self.assertEqual(QuestionAsset.objects.count(), 2)

    def test_missing_anchor_rejected_and_failure_rolls_back_all_new_content(self):
        bad = Path(self.temp.name) / 'bad.pdf'; make_pdf(bad, missing_anchor=True)
        with self.assertRaises(CommandError):
            call_command('import_linear_selected_pdf', str(bad), stdout=io.StringIO())
        self.assertEqual(QuestionDocument.objects.count(), 0)
        other = QuestionDocument.objects.create(source_id=77001, sha256='a'*64, page_count=1, title='Do not touch')
        sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        Question.objects.create(document=other, question_order=1, fingerprint=fingerprint(sha, 'question', 2), content_mode='image')
        with self.assertRaises(CommandError):
            self.run_import()
        self.assertEqual(QuestionDocument.objects.count(), 1)
        self.assertEqual(Question.objects.count(), 1)
        self.assertEqual(QuestionAsset.objects.count(), 0)
        self.assertEqual(SourceQuestionAnchor.objects.count(), 0)
