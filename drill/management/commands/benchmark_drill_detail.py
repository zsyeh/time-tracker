"""Read-only endpoint microbenchmark for an isolated database (no response bodies logged)."""
import json
import statistics
import time
import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIRequestFactory, force_authenticate

from drill.views import DrillQuestionDetailView


class Command(BaseCommand):
    help = 'Measure detail SQL and rendering locally; use an isolated database and an existing test user.'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', required=True, type=int)
        parser.add_argument('--question-uuid', required=True, type=uuid.UUID)
        parser.add_argument('--workspace', choices=('drill', 'ei'), default='drill')
        parser.add_argument('--query-json', default='{}')
        parser.add_argument('--samples', type=int, default=10)
        parser.add_argument('--warmup', type=int, default=2)
        parser.add_argument('--explain', action='store_true', help='Run PostgreSQL EXPLAIN ANALYZE on the three slowest SELECTs.')

    def handle(self, *args, **options):
        if not 1 <= options['samples'] <= 100 or not 0 <= options['warmup'] <= 10:
            raise CommandError('Use 1–100 samples and 0–10 warmup calls.')
        try:
            query = json.loads(options['query_json'])
        except ValueError as exc:
            raise CommandError('query-json must be a JSON object.') from exc
        if not isinstance(query, dict):
            raise CommandError('query-json must be a JSON object.')
        try:
            user = get_user_model().objects.get(pk=options['user_id'], is_active=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError('An existing active user is required.') from exc
        if options['explain'] and connection.vendor != 'postgresql':
            raise CommandError('--explain requires PostgreSQL.')
        factory = APIRequestFactory()
        rows = []
        for index in range(options['warmup'] + options['samples']):
            request = factory.get('/', query, HTTP_HOST=f"{options['workspace']}.ehzsy.site")
            force_authenticate(request, user=user)
            with CaptureQueriesContext(connection) as captured:
                started = time.perf_counter()
                response = DrillQuestionDetailView.as_view()(request, question_uuid=options['question_uuid'])
                JSONRenderer().render(response.data)
                elapsed = (time.perf_counter() - started) * 1000
            if response.status_code != 200:
                raise CommandError(f'Detail returned HTTP {response.status_code}.')
            if index >= options['warmup']:
                rows.append((len(captured), elapsed, sum(float(q['time']) * 1000 for q in captured)))
        report = {
            'workspace': options['workspace'], 'samples': len(rows),
            'sql_count_min': min(row[0] for row in rows),
            'sql_count_max': max(row[0] for row in rows),
            'median_wall_ms': round(statistics.median(row[1] for row in rows), 3),
            'median_sql_ms': round(statistics.median(row[2] for row in rows), 3),
            'min_wall_ms': round(min(row[1] for row in rows), 3),
            'max_wall_ms': round(max(row[1] for row in rows), 3),
        }
        if options['explain']:
            report['slowest_select_plans'] = []
            for statement in sorted(captured, key=lambda row: float(row['time']), reverse=True)[:3]:
                if not statement['sql'].lstrip().upper().startswith('SELECT'):
                    continue
                with connection.cursor() as cursor:
                    cursor.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + statement['sql'])
                    plan = cursor.fetchone()[0][0]
                report['slowest_select_plans'].append({
                    'node': plan['Plan']['Node Type'],
                    'actual_rows': plan['Plan']['Actual Rows'],
                    'execution_ms': plan['Execution Time'],
                    'shared_hit_blocks': plan['Plan'].get('Shared Hit Blocks', 0),
                    'shared_read_blocks': plan['Plan'].get('Shared Read Blocks', 0),
                })
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
