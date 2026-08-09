"""Small, reloadable instance settings backed by a local dotenv file.

Only the explicitly managed keys below can be changed from the authenticated
settings screen. The rest of the dotenv file is preserved byte-for-byte as
far as possible, so credentials and deployment settings stay outside this API.
"""

import datetime
import fcntl
import json
import os
import re
import tempfile
import threading
from pathlib import Path

from django.conf import settings
from dotenv import dotenv_values


FIELD_TO_ENV = {
    'homepage_content': 'TRACKER_HOMEPAGE_CONTENT',
    'study_room_code': 'STUDY_ROOM_CODE',
    'tracking_start_date': 'TRACKER_HEATMAP_START_DATE',
    'exam_date': 'TRACKER_EXAM_DATE',
    'countdown_label': 'TRACKER_COUNTDOWN_LABEL',
}

_cache_lock = threading.RLock()
_cache_signature = None
_cache_values = {}


def local_env_path():
    return Path(settings.TRACKER_LOCAL_ENV_PATH).expanduser()


def _signature(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return str(path), None, None
    return str(path), stat.st_mtime_ns, stat.st_size


def _dotenv_values():
    """Read the local file once per change, even on hot dashboard requests."""
    global _cache_signature, _cache_values
    path = local_env_path()
    signature = _signature(path)
    with _cache_lock:
        if signature != _cache_signature:
            parsed = dotenv_values(path) if signature[1] is not None else {}
            _cache_values = {
                key: value
                for key, value in parsed.items()
                if key in FIELD_TO_ENV.values() and value is not None
            }
            _cache_signature = signature
        return dict(_cache_values), signature


def default_values():
    return {
        'homepage_content': settings.TRACKER_HOMEPAGE_CONTENT,
        'study_room_code': settings.STUDY_ROOM_CODE,
        'tracking_start_date': settings.TRACKER_HEATMAP_START_DATE,
        'exam_date': settings.TRACKER_EXAM_DATE,
        'countdown_label': settings.TRACKER_COUNTDOWN_LABEL,
    }


def runtime_config():
    dotenv, signature = _dotenv_values()
    defaults = default_values()
    values = {}
    sources = {}
    for field, env_key in FIELD_TO_ENV.items():
        local_value = dotenv.get(env_key)
        use_local = local_value not in (None, '') or (
            field in {'homepage_content', 'study_room_code'} and local_value == ''
        )
        if use_local and field in {'tracking_start_date', 'exam_date'}:
            try:
                datetime.date.fromisoformat(local_value)
            except (TypeError, ValueError):
                use_local = False
        if use_local and field == 'countdown_label' and not local_value.strip():
            use_local = False
        if use_local:
            values[field] = local_value
            sources[field] = 'local_env'
        else:
            values[field] = defaults[field]
            sources[field] = 'default'
    fingerprint = f'{signature[1]}-{signature[2]}'
    return {
        'values': values,
        'defaults': defaults,
        'sources': sources,
        'fingerprint': fingerprint,
        'local_env_exists': signature[1] is not None,
    }


def _dotenv_line(key, value):
    # JSON strings are accepted by python-dotenv and safely preserve spaces,
    # Unicode, hashes, quotes, and line breaks without shell interpolation.
    return f'{key}={json.dumps(str(value), ensure_ascii=False)}\n'


def _replace_managed_lines(existing, values):
    replacements = {
        FIELD_TO_ENV[field]: _dotenv_line(FIELD_TO_ENV[field], value)
        for field, value in values.items()
    }
    patterns = {
        key: re.compile(rf'^\s*(?:export\s+)?{re.escape(key)}\s*=')
        for key in replacements
    }
    output = []
    written = set()
    for line in existing.splitlines(keepends=True):
        matched_key = next((key for key, pattern in patterns.items() if pattern.match(line)), None)
        if matched_key is None:
            output.append(line)
        elif matched_key not in written:
            output.append(replacements[matched_key])
            written.add(matched_key)
    if output and not output[-1].endswith('\n'):
        output[-1] += '\n'
    if output and output[-1].strip():
        output.append('\n')
    for key in replacements:
        if key not in written:
            output.append(replacements[key])
    return ''.join(output)


def save_runtime_config(values):
    """Atomically update only the allow-listed dotenv values."""
    global _cache_signature
    path = local_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f'{path.name}.lock')
    with lock_path.open('a+', encoding='utf-8') as lock_file:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        existing = path.read_text(encoding='utf-8') if path.exists() else ''
        rendered = _replace_managed_lines(existing, values)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as temporary:
                temporary.write(rendered)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    with _cache_lock:
        _cache_signature = None
    return runtime_config()
