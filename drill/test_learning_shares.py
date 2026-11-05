import datetime as dt
import hashlib
import io
import json
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import (LearningShare, Question, QuestionAsset, QuestionAttempt,
                     QuestionDocument, QuestionTopic, QuestionUserState)


@override_settings(ALLOWED_HOSTS=['drill.ehzsy.site', 'ei.ehzsy.site'])
class LearningShareTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user('owner', password='test')
        self.other = User.objects.create_user('other', password='test')
        self.book = QuestionDocument.objects.create(source_id=9001, workspace='drill', filename='book.pdf',
            title='Math', sha256='1' * 64, page_count=1)
        self.ei_book = QuestionDocument.objects.create(source_id=9002, workspace='ei', filename='ei.pdf',
            title='Electronics', sha256='2' * 64, page_count=1)
        self.topic = QuestionTopic.objects.create(source_id=9001, document=self.book, title='Limits', level=1, sort_order=1)
        self.other_topic = QuestionTopic.objects.create(source_id=9002, document=self.book, title='Algebra', level=1, sort_order=2)
        self.question = self.make_question(self.book, self.topic, 1)
        self.outside = self.make_question(self.book, self.other_topic, 2)
        self.ei_question = self.make_question(self.ei_book, None, 1)
        self.asset_bytes = b'asset-binary-test'
        self.asset = QuestionAsset.objects.create(source_id=9001, question=self.question, position=0,
            asset_type='question_crop', sha256=hashlib.sha256(self.asset_bytes).hexdigest(),
            image_data=self.asset_bytes, width=1, height=1)
        QuestionUserState.objects.create(user=self.owner, question=self.question, note='private current note')
        QuestionUserState.objects.create(user=self.other, question=self.question, note='another user note')
        self.client.force_login(self.owner)

    def make_question(self, book, topic, order):
        return Question.objects.create(document=book, topic=topic, similarity_topic=topic,
            question_order=order, prompt_text=f'Question {order}', content_mode='text',
            fingerprint=f'{book.source_id}-{order}-'.ljust(64, '0'))

    def create(self, kind='heatmap', scope=None, host='drill.ehzsy.site', notes=True):
        import json
        response = self.client.post('/api/drill/learning-shares/', data=json.dumps({
            'kind': kind, 'scope': scope or {}, 'include_notes': notes}), content_type='application/json',
            HTTP_HOST=host, secure=True)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def public(self, url, host='drill.ehzsy.site'):
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        return self.client.get(parsed.path + (f'?{parsed.query}' if parsed.query else ''), HTTP_HOST=host, secure=True)

    def test_scope_notes_assets_and_workspace_isolation(self):
        data = self.create(scope={'topic': str(self.topic.pk)})
        self.assertEqual(len(data['url'].split('/')[5]), 43)
        self.assertNotIn(data['url'].split('/')[5], LearningShare.objects.get(pk=data['id']).token_digest)
        self.client.logout()
        index = self.public(data['url'])
        self.assertEqual(index.status_code, 200)
        self.assertIn('题目分页', index.content.decode())
        from urllib.parse import urlsplit
        head = self.client.head(urlsplit(data['url']).path, HTTP_HOST='drill.ehzsy.site', secure=True)
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b'')
        page = self.public(data['url'].replace('index.md', 'questions/index.json?page=1'))
        self.assertEqual(page.json()['count'], 1)
        question_url = data['url'].replace('index.md', f'questions/{self.question.uuid}.json')
        item = self.public(question_url).json()
        self.assertEqual(item['note'], 'private current note')
        self.assertNotIn('another user note', str(item))
        self.assertEqual(self.public(item['assets'][0]['url']).content, self.asset_bytes)
        accelerated = self.client.get(urlsplit(item['assets'][0]['url']).path,
            HTTP_HOST='drill.ehzsy.site', HTTP_X_TIME_TRACKER_EDGE='rainyun', secure=True)
        self.assertEqual(accelerated.status_code, 200)
        self.assertEqual(accelerated['X-Accel-Redirect'],
            f'/__learning_asset_cache/drill/{self.asset.pk}/{self.asset.sha256}')
        self.assertEqual(accelerated.content, b'')
        self.assertEqual(self.public(item['assets'][0]['url'].replace(self.asset.sha256, '0' * 64)).status_code, 404)
        self.assertEqual(self.public(data['url'].replace('index.md', f'assets/{self.asset.pk}/{self.asset.sha256}'), host='ei.ehzsy.site').status_code, 404)
        self.assertEqual(self.public(data['url'].replace('index.md', '')).status_code, 200)
        exported = self.public(data['url'].replace('index.md', 'export.md')).content.decode()
        self.assertIn('private current note', exported)
        self.assertNotIn('another user note', exported)
        self.assertEqual(self.public(data['url'].replace('index.md', 'heatmap.json')).json()['counts']['total'], 1)
        self.assertIn('topic_tree', self.public(data['url'].replace('index.md', 'topology.json')).json())
        self.assertEqual(self.public(data['url'].replace('index.md', f'questions/{self.outside.uuid}.json')).status_code, 404)
        self.assertEqual(self.public(data['url'].replace('index.md', f'questions/{self.ei_question.uuid}.json')).status_code, 404)
        self.assertEqual(self.public(data['url'], host='ei.ehzsy.site').status_code, 404)
        self.assertEqual(self.client.post('/share/learning/bad/index.md', HTTP_HOST='drill.ehzsy.site', secure=True).status_code, 405)

    def test_revocation_expiry_owner_and_fresh_note(self):
        data = self.create()
        share = LearningShare.objects.get(pk=data['id'])
        self.assertEqual(share.expires_at - share.created_at, dt.timedelta(days=7))
        QuestionUserState.objects.filter(user=self.owner, question=self.question).update(note='updated note')
        url = data['url'].replace('index.md', f'questions/{self.question.uuid}.json')
        self.assertEqual(self.public(url).json()['note'], 'updated note')
        self.client.force_login(self.other)
        self.assertEqual(self.client.delete(f'/api/drill/learning-shares/{share.pk}/', HTTP_HOST='drill.ehzsy.site', secure=True).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.delete(f'/api/drill/learning-shares/{share.pk}/', HTTP_HOST='drill.ehzsy.site', secure=True).status_code, 200)
        self.assertEqual(self.public(url).status_code, 410)
        asset_url = data['url'].replace('index.md', f'assets/{self.asset.pk}/{self.asset.sha256}')
        self.assertEqual(self.public(asset_url).status_code, 410)
        from urllib.parse import urlsplit
        blocked = self.client.get(urlsplit(asset_url).path, HTTP_HOST='drill.ehzsy.site',
            HTTP_X_TIME_TRACKER_EDGE='rainyun', secure=True)
        self.assertEqual(blocked.status_code, 410)
        self.assertNotIn('X-Accel-Redirect', blocked)
        share.revoked_at = None
        share.expires_at = timezone.now() - dt.timedelta(seconds=1)
        share.save(update_fields=['revoked_at', 'expires_at'])
        self.assertEqual(self.public(url).status_code, 410)

    def test_shanghai_day_and_daily_vs_period_unique(self):
        shanghai = ZoneInfo('Asia/Shanghai')
        midnight = dt.datetime(2026, 11, 3, 0, 0, tzinfo=shanghai)
        for moment in (midnight - dt.timedelta(minutes=1), midnight + dt.timedelta(minutes=1)):
            QuestionAttempt.objects.create(user=self.owner, question=self.question, result='correct',
                outcome='correct', is_independent=True, created_at=moment)
        data = self.create(kind='weekly', scope={'start': '2026-11-02', 'end': '2026-11-03'})
        report = self.public(data['url'].replace('index.md', 'summary.json')).json()
        self.assertEqual(report['valid_submissions'], 2)
        self.assertEqual(report['period_unique_questions'], 1)
        self.assertEqual(report['sum_of_daily_unique_questions'], 2)
        self.assertEqual(report['daily_trend'][0]['unique_questions'], 1, report['daily_trend'])
        self.assertEqual(report['daily_trend'][1]['unique_questions'], 1)

    def test_all_pages_are_traversable_and_notes_can_be_excluded(self):
        for order in range(3, 104):
            self.make_question(self.book, self.topic, order)
        data = self.create(notes=False)
        first = self.public(data['url'].replace('index.md', 'questions/index.json?page=1')).json()
        self.assertEqual(first['count'], 103)
        self.assertEqual(len(first['results']), 100)
        self.assertIsNotNone(first['next_url'])
        second = self.public(first['next_url']).json()
        self.assertEqual(len(second['results']), 3)
        self.assertIsNone(second['next_url'])
        detail = self.public(data['url'].replace('index.md', f'questions/{self.question.uuid}.json')).json()
        self.assertIsNone(detail['note'])
        self.assertNotIn('private current note', self.public(data['url'].replace('index.md', 'export.md')).content.decode())
        self.assertEqual(self.public(data['url'].replace('index.md', 'manifest.json')).json()['aggregate_counts']['total'], 103)

    def test_asset_manifest_uses_authoritative_hash_and_workspace(self):
        output = io.StringIO()
        call_command('export_learning_assets', manifest=True, stdout=output)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(rows, [{'id': self.asset.pk, 'workspace': 'drill',
            'sha256': self.asset.sha256, 'size': len(self.asset_bytes), 'mime_type': 'image/png'}])

    def test_ei_core_selection_reuses_canonical_manifest(self):
        from .core_selected import manifest
        row = manifest()['questions'][0]
        selected = Question.objects.create(document=self.ei_book, question_order=2,
            uuid=row['uuid'], fingerprint=row['fingerprint'], prompt_text='Core selected', content_mode='text')
        data = self.create(scope={'collection': 'core_selected'}, host='ei.ehzsy.site')
        report = self.public(data['url'].replace('index.md', 'heatmap.json'), host='ei.ehzsy.site').json()
        self.assertEqual(report['counts']['total'], 1)
        listing = self.public(data['url'].replace('index.md', 'questions/index.json?page=1'), host='ei.ehzsy.site').json()
        self.assertEqual(listing['results'][0]['uuid'], str(selected.uuid))
        self.assertEqual(self.public(data['url'].replace('index.md', f'questions/{self.question.uuid}.json'), host='ei.ehzsy.site').status_code, 404)
        self.assertEqual(self.public(data['url'].replace('index.md', f'assets/{self.asset.pk}/{self.asset.sha256}'), host='ei.ehzsy.site').status_code, 404)

    def test_asset_rerender_invalidates_old_cache_key(self):
        data = self.create()
        old_url = data['url'].replace('index.md', f'assets/{self.asset.pk}/{self.asset.sha256}')
        self.assertEqual(self.public(old_url).content, self.asset_bytes)
        updated = b'new-image-version'
        new_digest = hashlib.sha256(updated).hexdigest()
        QuestionAsset.objects.filter(pk=self.asset.pk).update(image_data=updated, sha256=new_digest)
        self.assertEqual(self.public(old_url).status_code, 404)
        new_url = data['url'].replace('index.md', f'assets/{self.asset.pk}/{new_digest}')
        self.assertEqual(self.public(new_url).content, updated)

    def test_bearer_token_is_redacted_from_request_logs(self):
        data = self.create()
        token = data['url'].split('/')[5]
        with self.assertLogs('django.request', level='WARNING') as captured:
            self.public(data['url'].replace('index.md', 'missing.md'))
        self.assertNotIn(token, '\n'.join(captured.output))
        self.assertIn('<redacted>', '\n'.join(captured.output))
