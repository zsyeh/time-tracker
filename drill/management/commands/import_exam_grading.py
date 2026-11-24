"""Agent-operated grading import. No frontend AI or anonymous write endpoint."""
import json
import os
import uuid
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.core import serializers
from django.db import transaction
from drill.models import DrillContentShare, ExamPaper, QuestionUserState, QuestionAttempt
from drill.exam_grading import import_grading

class Command(BaseCommand):
    help = 'Validate/import a privately supplied grading JSON; dry-run unless --apply.'
    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--share-token', required=True)
        parser.add_argument('--input', required=True)
        parser.add_argument('--backup')
        parser.add_argument('--apply', action='store_true')
    def handle(self, **options):
        user = get_user_model().objects.get(username=options['username'])
        data = json.loads(Path(options['input']).read_text())
        root = Path(options['backup']) if options.get('backup') else None
        if options['apply'] and root is None: raise CommandError('--backup is required for writes.')
        with transaction.atomic():
            share = DrillContentShare.objects.get(token_digest=DrillContentShare.digest(options['share_token']), owner=user)
            paper = ExamPaper.objects.select_for_update().get(pk=share.paper_id, user=user)
            ids = list(paper.items.values_list('question_id',flat=True))
            mastery_keys = [uuid.uuid5(uuid.NAMESPACE_URL, f'exam-grading:{paper.uuid}:{r["position"]}:mastery') for r in data['items'] if r.get('confirm_mastered')]
            def snapshot():
                paper.refresh_from_db()
                return serializers.serialize('json', [paper, *paper.items.order_by('pk'),
                    *QuestionUserState.objects.filter(user=user, question_id__in=ids).order_by('pk'),
                    *QuestionAttempt.objects.filter(user=user,submission_key__in=mastery_keys).order_by('pk')])
            before = snapshot()
            result = import_grading(user=user, share_token=options['share_token'],data=data,apply=options['apply'])
            if options['apply'] and not result['unchanged']:
                root.mkdir(mode=0o700, parents=True, exist_ok=False)
                for name,content in [('before.json',before),('after.json',snapshot()),('result.json',json.dumps(result,ensure_ascii=False,indent=2))]:
                    path=root/name;path.write_text(content);os.chmod(path,0o600)
            self.stdout.write(json.dumps(result,ensure_ascii=False))
