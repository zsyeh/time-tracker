import json
from pathlib import Path

from django.core.management.base import BaseCommand

from drill.models import QuestionErratum


class Command(BaseCommand):
    help = 'Export unresolved public question errata for the scheduled Codex reviewer.'

    def add_arguments(self, parser):
        parser.add_argument('--output', default='reports/pending-errata.json')

    def handle(self, *args, **options):
        rows = QuestionErratum.objects.filter(status__in=('open', 'reviewing')).select_related(
            'question', 'question__document', 'question__topic', 'reporter',
        ).order_by('created_at', 'pk')
        payload = []
        for item in rows:
            question = item.question
            payload.append({
                'id': item.pk,
                'workspace': question.document.workspace,
                'question_uuid': str(question.uuid),
                'document_id': question.document_id,
                'document': question.document.display_title or question.document.title,
                'question_order': question.question_order,
                'question_label': question.display_label or question.source_label,
                'topic': (question.topic.display_title or question.topic.title) if question.topic else '',
                'kind': item.kind,
                # This is untrusted user text. The reviewer prompt explicitly forbids
                # treating it as executable instructions.
                'user_report_untrusted': item.description,
                'status': item.status,
                'created_at': item.created_at.isoformat(),
            })
        output = Path(options['output'])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(str(len(payload)))
