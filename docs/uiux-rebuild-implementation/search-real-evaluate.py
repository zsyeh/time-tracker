#!/usr/bin/env python3
"""One-pass real-public-corpus quality check; NOT a latency/load benchmark.

Run only on an isolated PostgreSQL DB named precision_search_real. Example:
  python docs/uiux-rebuild-implementation/search-real-evaluate.py --init-user
  python manage.py rebuild_question_search --workspace all --verify
  python docs/uiux-rebuild-implementation/search-real-evaluate.py

DATABASE_URL must explicitly select the isolated DB. No production access,
private notes, answer exports, request replay, warmups or concurrent requests.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'time_server.settings')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(ranking, judgments):
    positive = {u for u, grade in judgments.items() if grade >= 2}
    known = set(judgments)
    ranked20 = ranking[:20]
    first = next((i + 1 for i, u in enumerate(ranked20) if u in positive), None)
    judged_ranking = [judgments[u] for u in ranking if u in known]
    ideal = sorted(judgments.values(), reverse=True)
    dcg = lambda scores: sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(scores[:10]))
    return {
        'known_relevant_recall_at_20': len(set(ranked20) & positive) / len(positive) if positive else None,
        'known_relevant_hit_at_20': int(bool(set(ranked20) & positive)) if positive else None,
        'mrr_at_20': 1 / first if first else 0 if positive else None,
        'judged_coverage_at_10': sum(u in known for u in ranking[:10]) / min(10, len(ranking)) if ranking else None,
        'explicit_grade0_at_10': [u for u in ranking[:10] if judgments.get(u) == 0],
        'known_positive_count': len(positive),
        'known_positive_returned_at_20': [u for u in ranked20 if u in positive],
        'unjudged_returned_at_10': [u for u in ranking[:10] if u not in known],
        'condensed_ndcg_at_10_optimistic_partial_qrels': dcg(judged_ranking) / dcg(ideal) if dcg(ideal) else None,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--init-user', action='store_true', help='Create ONLY isolated fixture user and exit.')
    ap.add_argument('--qrels', type=Path, default=Path(__file__).with_name('search-real-qrels.json'))
    ap.add_argument('--output', type=Path, default=Path(__file__).with_name('search-real-quality.json'))
    args = ap.parse_args()
    if 'DATABASE_URL' not in os.environ:
        raise SystemExit('Set explicit isolated DATABASE_URL; inherited .env is not accepted.')
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django.test import override_settings
    from rest_framework.exceptions import APIException
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory
    from drill.models import Question, QuestionAttempt, QuestionUserState, QuestionSearchDocument, QuestionSearchState
    from drill.search.index import source_version
    from drill.search.service import question_list_response
    if connection.vendor != 'postgresql' or connection.settings_dict['NAME'] != 'precision_search_real':
        raise SystemExit('Refuse to run outside isolated PostgreSQL precision_search_real.')
    User = get_user_model()
    username = 'public-search-quality-fixture'
    if args.init_user:
        user, created = User.objects.get_or_create(username=username, defaults={'is_active': True})
        if created:
            user.set_unusable_password()
            user.save(update_fields=['password'])
        print(json.dumps({'fixture_user_created': created, 'fixture_user_id': user.pk}))
        return
    user = User.objects.get(username=username)
    if QuestionAttempt.objects.filter(user=user).exists() or QuestionUserState.objects.filter(user=user).exists():
        raise SystemExit('Fixture user has learning state; refusing contaminated relevance test.')
    fixture = json.loads(args.qrels.read_text())
    if Question.objects.count() != fixture['source_counts']['question']:
        raise SystemExit('Corpus count mismatch; this qrels is only for unchanged 9281-question real snapshot.')
    questions = {str(uuid): (workspace, practiceable) for uuid, workspace, practiceable in Question.objects.values_list('uuid', 'document__workspace', 'is_practiceable')}
    for query in fixture['queries']:
        for uuid in query['judgments']:
            if questions.get(uuid) != (query['workspace'], True):
                raise SystemExit(f'Judgment corpus mismatch: {query["id"]}')
    states = list(QuestionSearchState.objects.order_by('workspace').values('workspace', 'ready', 'rebuilding', 'build_source_version', 'aliases_hash', 'generation'))
    if len(states) != 2 or any(not s['ready'] or s['rebuilding'] or s['build_source_version'] != source_version() for s in states):
        raise SystemExit('Index not verified/current; rebuild --verify first.')
    relevant_code = list((ROOT / 'drill/search').glob('*.py')) + [ROOT / 'drill/data/search_aliases_v1.json']
    start_hash = {str(p.relative_to(ROOT)): digest(p) for p in relevant_code}
    rows = []
    for backend in ('legacy', 'hybrid_v1'):
        with override_settings(DRILL_SEARCH_BACKEND=backend, DRILL_HOSTS={'drill.search.test'}, EI_HOSTS={'ei.search.test'}, ALLOWED_HOSTS=['drill.search.test', 'ei.search.test']):
            for query in fixture['queries']:
                host = 'ei.search.test' if query['workspace'] == 'ei' else 'drill.search.test'
                params = {'q': query['q'], 'search_version': '2', **query.get('filters', {})}
                request = Request(APIRequestFactory().get('/api/drill/questions/', params, HTTP_HOST=host))
                request._user = user
                started = time.perf_counter()
                try:
                    response = question_list_response(request)
                    response.render() if getattr(response, 'accepted_renderer', None) else None
                    status = response.status_code
                    data = response.data
                    error = None
                except APIException as exc:
                    status = exc.status_code
                    data = {}
                    error = {'class': type(exc).__name__, 'code': exc.default_code}
                except Exception as exc:
                    status, data = 500, {}
                    error = {'class': type(exc).__name__}
                ranking = [r['uuid'] for r in data.get('results', [])]
                row = {'id': query['id'], 'q': query['q'], 'workspace': query['workspace'], 'backend': backend,
                       'filters': query.get('filters', {}), 'expected_behavior': query['expected_behavior'],
                       'status': status, 'count': data.get('count'), 'top24': ranking,
                       'search': data.get('search'), 'error': error,
                       'single_pass_observed_service_ms_not_latency_benchmark': round((time.perf_counter() - started) * 1000, 3)}
                if query['expected_behavior'] == 'relevant-results':
                    row['metrics'] = metrics(ranking, query['judgments'])
                    row['known_target_found_at_20'] = bool(row['metrics']['known_relevant_hit_at_20'])
                elif query['expected_behavior'] == 'expected-empty':
                    row['empty_check_passed'] = status == 200 and data.get('count') == 0
                else:
                    row['browse_check_passed'] = status == 200 and data.get('count', 0) > 0 and bool(ranking)
                rows.append(row)
                print(json.dumps({'backend': backend, 'id': row['id'], 'status': status, 'count': row['count'],
                                  'known_recall20': row.get('metrics', {}).get('known_relevant_recall_at_20')}, ensure_ascii=False), flush=True)
    end_hash = {str(p.relative_to(ROOT)): digest(p) for p in relevant_code}
    if start_hash != end_hash:
        raise SystemExit('Search source changed during run; discard partial result and rerun after index verification.')
    summaries = {}
    for backend in ('legacy', 'hybrid_v1'):
        group = [r for r in rows if r['backend'] == backend]
        metric_rows = [r['metrics'] for r in group if 'metrics' in r]
        summaries[backend] = {
            'queries': len(group), 'errors': [r['id'] for r in group if r['error'] or r['status'] != 200],
            'relevance_queries': len(metric_rows),
            'macro_known_relevant_recall_at_20': statistics.mean(m['known_relevant_recall_at_20'] for m in metric_rows),
            'macro_mrr_at_20': statistics.mean(m['mrr_at_20'] for m in metric_rows),
            'known_relevant_hit_at_20_queries': sum(m['known_relevant_hit_at_20'] for m in metric_rows),
            'macro_judged_coverage_at_10_nonempty_results': statistics.mean(m['judged_coverage_at_10'] for m in metric_rows if m['judged_coverage_at_10'] is not None),
            'known_target_miss_queries': [r['id'] for r in group if r.get('known_target_found_at_20') is False],
            'explicit_grade0_at_10_queries': [r['id'] for r in group if r.get('metrics', {}).get('explicit_grade0_at_10')],
            'expected_empty_passed': sum(r.get('empty_check_passed', False) for r in group),
            'expected_empty_total': sum(r['expected_behavior'] == 'expected-empty' for r in group),
            'browse_passed': all(r.get('browse_check_passed', True) for r in group),
        }
    payload = {
        'kind': 'single-pass-actual-engine-real-public-corpus-quality-not-http-not-load',
        'annotation_status': fixture['annotation_status'], 'evaluation_contract': fixture['evaluation_contract'],
        'corpus': fixture['corpus'], 'source_metadata_sha256': fixture['source_sha256'], 'qrels_sha256': digest(args.qrels),
        'question_count': len(questions), 'projection_count': QuestionSearchDocument.objects.count(),
        'db_vendor': connection.vendor, 'postgres_version': connection.pg_version,
        'api': 'real drill.search.service.question_list_response via DRF Request/APIRequestFactory; auth fixture user; existing live workspace scope/filter/pagination/ranking',
        'measurement_budget': {'passes_per_backend_query': 1, 'warmups': 0, 'concurrency': 1},
        'limitations': ['No independent blind/user labels.', 'Sparse judgments: unjudged is unknown, not relevance0.',
                         'KnownRelevantRecall is not full-corpus recall.', 'Single-pass service timing is diagnostic only; no HTTP p95 or throughput claim.',
                         'No images/OCR or private learning data imported.'],
        'search_code_sha256': start_hash, 'index_states': states, 'summary': summaries, 'rows': rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'saved': str(args.output), 'summary': summaries}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
