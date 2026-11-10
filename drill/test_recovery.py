import datetime as dt
import uuid
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings, Client
from django.utils import timezone
from .models import Question, QuestionDocument, QuestionAttempt, QuestionTimingSession, LearningRecoveryState

@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class RecoveryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('resume')
        self.other = get_user_model().objects.create_user('other')
        self.client.force_login(self.user)
        book = QuestionDocument.objects.create(source_id=99, filename='x', sha256='f'*64, page_count=1)
        self.q = Question.objects.create(document=book, question_order=1, fingerprint='a'*64, content_mode='text')
        self.q2 = Question.objects.create(document=book, question_order=2, fingerprint='b'*64, content_mode='text')
        self.key, self.owner = str(uuid.uuid4()), str(uuid.uuid4())
        self.now = timezone.now()
        self.clock = patch('drill.recovery.timezone.now', side_effect=lambda:self.now); self.clock.start(); self.addCleanup(self.clock.stop)
    def call(self, action='claim', seq=1, elapsed=0, owner=None, key=None, q=None):
        return self.client.post(f'/api/drill/questions/{(q or self.q).uuid}/timing/',
            {'protocol':2, 'action':action, 'timing_key':key or self.key, 'owner':owner or self.owner,
             'sequence':seq, 'elapsed_ms':elapsed, 'countdown_ms':0}, content_type='application/json')
    def tick(self, seconds): self.now += dt.timedelta(seconds=seconds)
    def attempt(self, submission=None, sequence=4, elapsed=60000, owner=None):
        return self.client.post(f'/api/drill/questions/{self.q.uuid}/attempts/',
            {'result':'correct','timing_key':self.key,'timing_protocol':2,'timing_owner':owner or self.owner,
             'timing_sequence':sequence,'timing_elapsed_ms':elapsed,'submission_key':submission or str(uuid.uuid4())}, content_type='application/json')
    def test_refresh_checkpoints_are_absolute_and_idempotent(self):
        self.assertEqual(self.call().status_code,200)
        self.tick(60)
        self.assertEqual(self.call('checkpoint',2,60000).json()['elapsed_ms'],60000)
        for _ in range(5): self.assertEqual(self.call('claim',3,60000).json()['elapsed_ms'],60000)
        self.assertEqual(self.call('checkpoint',2,60000).json()['elapsed_ms'],60000)
        self.assertEqual(QuestionTimingSession.objects.count(),1)
        self.assertEqual(QuestionAttempt.objects.count(),0)
    def test_pause_and_lock_screen_do_not_earn_wall_time(self):
        self.call();self.tick(60);self.call('pause',2,60000)
        self.tick(3600);self.assertEqual(self.call('claim',3,60000).json()['elapsed_ms'],60000)
        done=self.attempt();self.assertEqual(done.status_code,201,done.content)
        self.assertEqual(done.json()['time_spent_seconds'],60)
    def test_submission_retry_does_not_create_two_attempts(self):
        self.call();self.tick(60);self.call('checkpoint',2,60000)
        key=str(uuid.uuid4()); first=self.attempt(key)
        self.assertEqual(first.status_code,201,first.content)
        self.assertEqual(self.attempt(key).status_code,200)
        self.assertEqual(QuestionAttempt.objects.count(),1)
        self.assertEqual(self.attempt().status_code,409)
    def test_foreground_duration_keeps_legacy_whole_second_rounding(self):
        self.call();self.tick(2)
        r=self.attempt(sequence=2,elapsed=1500)
        self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(r.json()['time_spent_seconds'],1)

    def test_reset_never_becomes_a_timed_attempt(self):
        self.call();self.tick(20);self.call('checkpoint',2,20000)
        r=self.client.post(f'/api/drill/questions/{self.q.uuid}/attempts/',
            {'result':'reset','timing_protocol':2,'timing_owner':self.owner,'timing_key':self.key,
             'timing_sequence':3,'timing_elapsed_ms':20000,'submission_key':str(uuid.uuid4())},content_type='application/json')
        self.assertEqual(r.status_code,201,r.content)
        self.assertIsNone(r.json()['time_spent_seconds'])

    def test_foreign_window_cannot_count_and_expired_lease_can_transfer(self):
        self.call();self.tick(20);self.call('checkpoint',2,20000)
        owner2=str(uuid.uuid4())
        self.assertEqual(self.call(owner=owner2).status_code,409)
        self.tick(46);res=self.call(seq=3,owner=owner2)
        self.assertEqual(res.status_code,200,res.content)
        self.assertFalse(res.json()['local_base_valid'])
        self.assertEqual(self.call('checkpoint',4,25000).status_code,409)
    def test_new_device_resumes_same_unfinished_round(self):
        self.call();self.tick(60);self.call('pause',2,60000)
        response=self.call(owner=str(uuid.uuid4()),key=str(uuid.uuid4()))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['timing_key'],self.key)
        self.assertEqual(response.json()['elapsed_ms'],60000)
    def test_crash_relaunch_can_recover_pending_local_time_only_on_matching_base(self):
        self.call();self.tick(20);self.call('checkpoint',2,20000);self.tick(46)
        new_owner=str(uuid.uuid4())
        r=self.client.post(f'/api/drill/questions/{self.q.uuid}/timing/',
            {'protocol':2,'action':'claim','owner':new_owner,'timing_key':self.key,'sequence':4,
             'resume_owner':self.owner,'base_elapsed_ms':20000},content_type='application/json')
        self.assertTrue(r.json()['local_base_valid'])
        synced=self.call('checkpoint',5,30000,owner=new_owner)
        self.assertEqual(synced.status_code,200,synced.content)
        self.assertEqual(synced.json()['elapsed_ms'],30000)

    def test_same_device_crash_proof_can_resume_without_waiting_for_expiry(self):
        self.call();self.tick(20);self.call('checkpoint',2,20000)
        owner=str(uuid.uuid4())
        r=self.client.post(f'/api/drill/questions/{self.q.uuid}/timing/',
            {'protocol':2,'action':'claim','owner':owner,'timing_key':self.key,'sequence':3,
             'resume_owner':self.owner,'base_elapsed_ms':20000},content_type='application/json')
        self.assertEqual(r.status_code,200,r.content)
        self.assertTrue(r.json()['local_base_valid'])
        self.assertEqual(self.call('checkpoint',4,20000).status_code,409)

    def test_stale_pause_cannot_stop_reclaimed_round(self):
        self.call();self.tick(10);self.call('pause',2,10000);self.call('claim',3,10000)
        self.call('pause',2,10000)
        state=LearningRecoveryState.objects.get(user=self.user)
        self.assertIsNotNone(state.active_timer_id)
        self.assertEqual(state.active_timer.recovery['sequence'],3)
    def test_impossible_checkpoint_and_wrong_owner_rejected(self):
        self.call()
        self.assertEqual(self.call('checkpoint',2,600000).status_code,400)
        self.assertEqual(self.call('checkpoint',2,0,owner=str(uuid.uuid4())).status_code,409)
    def test_switching_question_invalidates_old_foreground_lease(self):
        self.call();self.tick(10)
        self.call(q=self.q2,key=str(uuid.uuid4()))
        self.assertEqual(self.call('checkpoint',2,10000).status_code,409)
    def test_location_version_and_workspace_merge_and_deleted_question(self):
        url='/api/learning/recovery/'
        self.assertEqual(self.client.get(url).json()['version'],0)
        r=self.client.put(url,{'version':0,'workspace':'drill','location':{'path':f'/drill/practice/{self.q.uuid}','scroll':{'right':250}}},content_type='application/json')
        self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(self.client.put(url,{'version':0,'workspace':'timer','location':{'path':'/'}},content_type='application/json').status_code,409)
        r=self.client.put(url,{'version':1,'workspace':'timer','location':{'path':'/sessions'}},content_type='application/json')
        self.assertEqual(set(r.json()['locations']),{'timer','drill'})
        self.q.delete();self.assertNotIn('drill',self.client.get(url).json()['locations'])
    def test_other_account_sees_no_location_or_timer(self):
        self.call();self.client.force_login(self.other)
        self.assertEqual(self.client.get('/api/learning/recovery/').json()['locations'],{})
        self.assertEqual(self.call(owner=str(uuid.uuid4())).status_code,200)
        self.assertEqual(QuestionTimingSession.objects.count(),2)
    def test_unsafe_and_cross_workspace_resume_paths_rejected(self):
        for workspace,path in [('timer','https://evil.test'),('timer','//evil.test'),('timer','/accounts/login/'),('drill',f'/ei/practice/{self.q.uuid}'),('ei',f'/ei/practice/{self.q.uuid}'),('timer','/?token=secret'),('drill','/drill/practice/'+'-'*36)]:
            r=self.client.put('/api/learning/recovery/',{'version':0,'workspace':workspace,'location':{'path':path}},content_type='application/json')
            self.assertEqual(r.status_code,400,(path,r.content))
    def test_new_write_endpoint_requires_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.put('/api/learning/recovery/',{'workspace':'timer','version':0,'location':{'path':'/'}},content_type='application/json').status_code,403)

from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature

@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
@skipUnlessDBFeature('has_select_for_update')
class RecoveryConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('concurrent')
        book=QuestionDocument.objects.create(source_id=88,filename='x',sha256='e'*64,page_count=1)
        self.q=Question.objects.create(document=book,question_order=1,fingerprint='c'*64,content_mode='text')
    def test_two_devices_claim_one_foreground_lease(self):
        from threading import Barrier
        barrier=Barrier(2)
        def claim(_):
            close_old_connections()
            try:
                client=Client();client.force_login(get_user_model().objects.get(pk=self.user.pk));barrier.wait(timeout=10)
                return client.post(f'/api/drill/questions/{self.q.uuid}/timing/',{'protocol':2,'action':'claim','owner':str(uuid.uuid4()),'timing_key':str(uuid.uuid4()),'sequence':1},content_type='application/json').status_code
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(claim,range(2)))
        self.assertEqual(sorted(results),[200,409])
        self.assertEqual(QuestionTimingSession.objects.count(),1)
        self.assertEqual(QuestionAttempt.objects.count(),0)

@override_settings(SECURE_SSL_REDIRECT=False)
class RecoveryAccountAffinityTests(TestCase):
    def test_old_window_cannot_write_to_newly_signed_in_account(self):
        old=get_user_model().objects.create_user('old-window')
        new=get_user_model().objects.create_user('new-login')
        self.client.force_login(new)
        r=self.client.put('/api/learning/recovery/',{'version':0,'workspace':'timer','location':{'path':'/'}},content_type='application/json',HTTP_X_LEARNING_USER_ID=str(old.pk))
        self.assertEqual(r.status_code,409)
        self.assertFalse(LearningRecoveryState.objects.exists())
        self.assertEqual(self.client.get('/api/auth/session/',HTTP_X_LEARNING_USER_ID=str(old.pk)).json()['user']['id'],new.pk)
        self.client.logout()
        self.assertIn(self.client.get('/api/learning/recovery/',HTTP_X_LEARNING_USER_ID=str(old.pk)).status_code,(401,403))
