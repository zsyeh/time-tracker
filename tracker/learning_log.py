"""Archive completed MCP study sessions in a GitHub repository."""

import fcntl
import re
import subprocess
from pathlib import Path
from typing import Any, Dict

from django.conf import settings
from django.utils import timezone


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _ensure_repository(repo: str, path: Path) -> None:
    if not (path / '.git').is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            _run('gh', 'repo', 'clone', repo, str(path))
        except subprocess.CalledProcessError:
            # The requested repository does not exist or is inaccessible. Creating
            # it private keeps personal learning reports private by default.
            _run('gh', 'repo', 'create', repo, '--private')
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


def archive_completed_task(task: Dict[str, Any]) -> Dict[str, str]:
    """Append a Markdown entry, commit it, and push it with the gh/git CLIs."""
    repo = settings.LEARNING_REPO
    if not repo:
        return {'status': 'disabled'}

    path = Path(settings.LEARNING_REPO_PATH)
    lock_path = path.parent / f'.{path.name}.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('w') as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        _ensure_repository(repo, path)
        # Keep a long-running service aligned with edits made from elsewhere.
        # An empty, newly created repository has no branch to pull yet.
        try:
            _run('git', 'rev-parse', '--verify', 'HEAD', cwd=path)
        except subprocess.CalledProcessError:
            pass
        else:
            _run('git', 'pull', '--ff-only', cwd=path)

        started = timezone.datetime.fromisoformat(task['start_time'])
        ended = timezone.datetime.fromisoformat(task['end_time'])
        relative_file = Path('sessions') / f'{started:%Y-%m}.md'
        target = path / relative_file
        target.parent.mkdir(parents=True, exist_ok=True)
        report = task.get('report', '').strip()
        first_line = next((line.strip() for line in report.splitlines() if line.strip()), '学习总结')
        summary_title = re.sub(r'^#+\s*', '', first_line).strip()
        summary_title = summary_title[:80].rstrip() or '学习总结'
        entry = (
            f"\n## {summary_title} · {task['duration_minutes']} 分钟\n\n"
            f"- 科目：{task['category_label']}\n"
            f"- 开始：{started:%Y-%m-%d %H:%M}\n"
            f"- 结束：{ended:%Y-%m-%d %H:%M}\n"
            f"- Tracker session：{task['id']}\n\n"
            f"{report}\n"
        )
        with target.open('a', encoding='utf-8') as stream:
            stream.write(entry)

        _run('git', 'add', '--', str(relative_file), cwd=path)
        commit_message = (
            f"Log {started:%Y-%m-%d} {task['category']} study session"
        )
        _run('git', 'commit', '-m', commit_message, cwd=path)
        _run('git', 'push', '-u', 'origin', 'HEAD', cwd=path)
        commit = _run('git', 'rev-parse', '--short', 'HEAD', cwd=path).stdout.strip()
        return {
            'status': 'pushed',
            'repository': repo,
            'commit': commit,
            'file': str(relative_file),
        }
