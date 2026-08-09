"""Archive completed study sessions as individual Markdown files on GitHub."""

import fcntl
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from .models import GitHubNoteSync, TimeLog


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _ensure_repository(repo: str, path: Path) -> None:
    if not (path / '.git').is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            _run('gh', 'repo', 'clone', repo, str(path))
        except subprocess.CalledProcessError:
            # Creation is private by default because the documents can contain
            # personal learning notes.
            _run('gh', 'repo', 'create', repo, '--private', '--add-readme')
            _run('gh', 'repo', 'clone', repo, str(path))

    owner = repo.split('/', 1)[0]
    try:
        _run('git', 'config', 'user.name', cwd=path)
    except subprocess.CalledProcessError:
        _run('git', 'config', 'user.name', owner, cwd=path)
    try:
        _run('git', 'config', 'user.email', cwd=path)
    except subprocess.CalledProcessError:
        _run('git', 'config', 'user.email', f'{owner}@users.noreply.github.com', cwd=path)


def session_task(session: TimeLog) -> Dict[str, Any]:
    start = timezone.localtime(session.start_time)
    end = timezone.localtime(session.end_time) if session.end_time else None
    return {
        'id': session.pk,
        'category': session.category,
        'category_label': session.get_category_display(),
        'start_time': start.isoformat(),
        'end_time': end.isoformat() if end else None,
        'duration_minutes': session.duration_minutes,
        'title': session.title or '',
        'details': session.details,
    }


def markdown_relative_path(task: Dict[str, Any]) -> Path:
    started = timezone.datetime.fromisoformat(task['start_time'])
    title = re.sub(r'^#+\s*', '', str(task.get('title', '')).strip())
    safe_title = slugify(title, allow_unicode=True)[:72].strip('-') or 'untitled-session'
    filename = f"{started:%Y-%m-%d-%H%M}-{int(task['id'])}-{safe_title}.md"
    return Path('sessions') / f'{started:%Y}' / f'{started:%m}' / filename


def render_session_markdown(task: Dict[str, Any]) -> str:
    started = timezone.datetime.fromisoformat(task['start_time'])
    ended = timezone.datetime.fromisoformat(task['end_time'])
    title = re.sub(r'\s+', ' ', re.sub(r'^#+\s*', '', str(task.get('title', '')).strip()))
    title = title[:500].rstrip() or 'Untitled session'
    details = str(task.get('details', '')).strip()
    return (
        '---\n'
        f"session_id: {int(task['id'])}\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"subject: {json.dumps(str(task['category']), ensure_ascii=False)}\n"
        f"subject_label: {json.dumps(str(task['category_label']), ensure_ascii=False)}\n"
        f"started_at: {json.dumps(started.isoformat(), ensure_ascii=False)}\n"
        f"ended_at: {json.dumps(ended.isoformat(), ensure_ascii=False)}\n"
        f"duration_minutes: {int(task['duration_minutes'])}\n"
        '---\n\n'
        f'# {title}\n\n'
        f'{details}\n'
    )


def archive_completed_task(task: Dict[str, Any]) -> Dict[str, str]:
    """Write one idempotent Markdown document, commit it, and push it."""
    repo = settings.LEARNING_REPO
    if not repo:
        return {'status': 'disabled'}

    path = Path(settings.LEARNING_REPO_PATH)
    lock_path = path.parent / f'.{path.name}.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    relative_file = markdown_relative_path(task)
    with lock_path.open('w') as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        _ensure_repository(repo, path)
        try:
            _run('git', 'rev-parse', '--verify', 'HEAD', cwd=path)
        except subprocess.CalledProcessError:
            pass
        else:
            _run('git', 'pull', '--rebase', cwd=path)

        target = path / relative_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_session_markdown(task), encoding='utf-8')
        _run('git', 'add', '--', str(relative_file), cwd=path)

        staged = subprocess.run(
            ('git', 'diff', '--cached', '--quiet', '--', str(relative_file)),
            cwd=path,
            check=False,
            timeout=10,
        ).returncode != 0
        if staged:
            title = re.sub(r'\s+', ' ', str(task.get('title', '')).strip())[:72]
            _run('git', 'commit', '-m', f"Add session {int(task['id'])}: {title}", cwd=path)
        _run('git', 'push', '-u', 'origin', 'HEAD', cwd=path)
        commit = _run('git', 'rev-parse', '--short', 'HEAD', cwd=path).stdout.strip()
        return {
            'status': 'pushed',
            'repository': repo,
            'commit': commit,
            'file': str(relative_file),
        }


def sync_session_note(session: TimeLog) -> Dict[str, str]:
    """Synchronize one completed session and update its durable outbox row."""
    if not settings.LEARNING_REPO:
        return {'status': 'disabled'}
    if session.status != 'completed' or not session.end_time:
        return {'status': 'skipped'}

    sync, _ = GitHubNoteSync.objects.get_or_create(session=session)
    if sync.status == 'synced':
        return {'status': 'pushed', 'file': sync.markdown_path, 'repository': settings.LEARNING_REPO}

    sync.attempts += 1
    try:
        result = archive_completed_task(session_task(session))
    except (OSError, subprocess.SubprocessError) as exc:
        sync.last_error = str(exc)[:4000]
        sync.save(update_fields=['attempts', 'last_error', 'updated_at'])
        return {'status': 'pending', 'error': sync.last_error}

    sync.status = 'synced'
    sync.markdown_path = result.get('file', '')
    sync.last_error = ''
    sync.synced_at = timezone.now()
    sync.save(update_fields=[
        'status', 'markdown_path', 'attempts', 'last_error', 'synced_at', 'updated_at',
    ])
    return result


def dispatch_github_note_sync(session_id: int) -> Dict[str, str]:
    """Start an immediate background attempt; the timer remains the fallback."""
    if not settings.LEARNING_REPO:
        return {'status': 'disabled'}
    try:
        subprocess.Popen(
            (
                sys.executable,
                str(Path(settings.BASE_DIR) / 'manage.py'),
                'sync_github_notes',
                '--session-id',
                str(session_id),
            ),
            cwd=settings.BASE_DIR,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as exc:
        return {'status': 'pending', 'error': str(exc)}
    return {'status': 'queued'}
