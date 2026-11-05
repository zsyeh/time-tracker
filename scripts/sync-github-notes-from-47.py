#!/usr/bin/env python3
"""Commit learning notes on RainYun using read-only tasks from the 47 primary.

The authoritative database is accessed only by Django running on 47. RainYun
handles Git and asks 47 to acknowledge a successfully pushed outbox row.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOURCE = 'root@47.95.10.128'
REMOTE = ['docker', 'exec', 'time-tracker-ha-web', 'python', 'manage.py', 'shell', '-c']


def primary(code):
    command = shlex.join([*REMOTE, code])
    return subprocess.run(['ssh', '-o', 'BatchMode=yes', SOURCE, command],
                          check=True, capture_output=True, text=True, timeout=120).stdout


def pending(limit):
    code = (
        'import json; from tracker.models import GitHubNoteSync; '
        'from tracker.learning_log import session_task; '
        'rows=GitHubNoteSync.objects.filter(status="pending",session__status="completed")'
        '.select_related("session","session__user").order_by("created_at")[:%d]; '
        '[print(json.dumps(session_task(row.session),ensure_ascii=False)) for row in rows]'
    ) % limit
    return [json.loads(line) for line in primary(code).splitlines() if line.startswith('{')]


def acknowledge(session_id):
    code = (
        'from tracker.models import GitHubNoteSync; '
        'from tracker.learning_log import session_task, markdown_relative_path, github_branch_for_user; '
        'from django.conf import settings; from django.utils import timezone; '
        'row=GitHubNoteSync.objects.select_related("session","session__user")'
        '.get(session_id=%d,status="pending"); '
        'task=session_task(row.session); row.status="synced"; '
        'row.markdown_path=str(markdown_relative_path(task)); '
        'row.branch=settings.LEARNING_REPO_MAIN_BRANCH if task["is_admin"] else '
        'github_branch_for_user(task["username"],is_admin=False,user_id=task["user_id"]); '
        'row.attempts+=1; row.last_error=""; row.synced_at=timezone.now(); '
        'row.save(update_fields=["status","markdown_path","branch","attempts",'
        '"last_error","synced_at","updated_at"]); print("acknowledged")'
    ) % session_id
    primary(code)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error('--limit must be between 1 and 20')

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'time_server.settings')
    import django
    django.setup()
    from tracker.learning_log import archive_completed_task

    tasks = pending(args.limit)
    if args.dry_run:
        print(json.dumps({'pending_fetched': len(tasks), 'session_ids': [t['id'] for t in tasks]}))
        return
    completed = 0
    for task in tasks:
        result = archive_completed_task(task)
        if result.get('status') != 'pushed':
            raise RuntimeError('GitHub archive is not enabled on RainYun')
        acknowledge(int(task['id']))
        completed += 1
        print(json.dumps({'session_id': task['id'], 'commit': result['commit'],
                          'branch': result['branch']}), flush=True)
    print(json.dumps({'fetched': len(tasks), 'acknowledged': completed}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
        print(f'RainYun GitHub note sync failed: {exc}', file=sys.stderr)
        sys.exit(1)
