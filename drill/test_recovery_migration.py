"""Local-only schema rehearsal: pending recovery is additive to attempt history."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone
import uuid

class RecoveryMigrationTests(TransactionTestCase):
    def test_down_up_preserves_attempt_statistics_and_legacy_inserts(self):
        executor=MigrationExecutor(connection)
        executor.migrate([('drill','0034_questionexamtypeedit')])
        old=executor.loader.project_state([('drill','0034_questionexamtypeedit')]).apps
        User=old.get_model('auth','User');Book=old.get_model('drill','QuestionDocument')
        Question=old.get_model('drill','Question');Attempt=old.get_model('drill','QuestionAttempt')
        user=User.objects.create(username='migration-history')
        book=Book.objects.create(source_id=222,filename='old.pdf',sha256='9'*64,page_count=1)
        question=Question.objects.create(document=book,question_order=1,fingerprint='8'*64,content_mode='text')
        attempt=Attempt.objects.create(user=user,question=question,result='correct',time_spent_seconds=37)
        try:
            executor=MigrationExecutor(connection);executor.migrate([('drill','0035_learning_recovery')])
            from .models import QuestionTimingSession, QuestionAttempt
            self.assertEqual(QuestionAttempt.objects.get(pk=attempt.pk).time_spent_seconds,37)
            now=timezone.now();key=uuid.uuid4()
            with connection.cursor() as cursor:
                cursor.execute('INSERT INTO drill_questiontimingsession (user_id,question_id,client_key,starts_at,stopped_at,created_at) VALUES (%s,%s,%s,%s,%s,%s)',
                               [user.pk,question.pk,key.hex if connection.vendor=='sqlite' else key,now,None,now])
            self.assertIsNone(QuestionTimingSession.objects.get(client_key=key).recovery)
            MigrationExecutor(connection).migrate([('drill','0034_questionexamtypeedit')])
            self.assertEqual(Attempt.objects.get(pk=attempt.pk).time_spent_seconds,37)
        finally:
            latest = MigrationExecutor(connection)
            latest.migrate(latest.loader.graph.leaf_nodes())
