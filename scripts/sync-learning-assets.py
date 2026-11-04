#!/usr/bin/env python3
"""Run on RainYun: pull verified immutable bytes from 47 without a database copy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time

CACHE_ROOT = Path('/var/cache/time-tracker/__learning_asset_cache')
SOURCE = 'root@47.95.10.128'
REMOTE = 'docker exec time-tracker-ha-web python manage.py export_learning_assets'


def ssh(command, *, capture=False):
    return subprocess.run(['ssh', '-o', 'BatchMode=yes', SOURCE, command],
                          check=True, capture_output=capture)


def manifest():
    result = ssh(f'{REMOTE} --manifest', capture=True)
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    if any(row['workspace'] not in ('drill', 'ei') or not isinstance(row['id'], int) or row['id'] <= 0
           or not isinstance(row['size'], int) or row['size'] < 0
           or len(row['sha256']) != 64 or any(c not in '0123456789abcdef' for c in row['sha256'])
           for row in rows):
        raise RuntimeError('Invalid source manifest')
    return rows


def key(row):
    return CACHE_ROOT / row['workspace'] / str(row['id']) / row['sha256']


def verified(path, row):
    if not path.is_file() or path.stat().st_size != row['size']:
        return False
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest() == row['sha256']


def install_stream(rows):
    expected = {f"{row['workspace']}/{row['id']}/{row['sha256']}": row for row in rows}
    ids = ','.join(str(row['id']) for row in rows)
    process = subprocess.Popen(['ssh', '-o', 'BatchMode=yes', SOURCE,
                                f'{REMOTE} --ids {ids}'], stdout=subprocess.PIPE)
    received = set()
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
            for member in archive:
                row = expected.get(member.name)
                if row is None or not member.isfile() or member.size != row['size']:
                    raise RuntimeError('Unexpected asset in tar stream')
                destination = key(row)
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
                    temp_path = Path(temporary.name)
                    try:
                        source = archive.extractfile(member)
                        while True:
                            block = source.read(1024 * 1024)
                            if not block:
                                break
                            digest.update(block)
                            temporary.write(block)
                    except BaseException:
                        temp_path.unlink(missing_ok=True)
                        raise
                if digest.hexdigest() != row['sha256']:
                    temp_path.unlink(missing_ok=True)
                    raise RuntimeError(f"Asset {row['id']} SHA-256 mismatch")
                os.chmod(temp_path, 0o444)
                os.replace(temp_path, destination)
                received.add(member.name)
        if process.wait() != 0 or received != set(expected):
            raise RuntimeError('Incomplete source export')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prune', action='store_true', help='Remove no-longer-current asset versions')
    args = parser.parse_args()
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    rows = manifest()
    missing = [row for row in rows if not verified(key(row), row)]
    for offset in range(0, len(missing), 100):
        chunk = missing[offset:offset + 100]
        if shutil.disk_usage(CACHE_ROOT).free < sum(row['size'] for row in chunk) + 2 * 1024**3:
            raise RuntimeError('Stopping: less than 2 GiB reserve would remain')
        install_stream(chunk)
    removed = 0
    if args.prune:
        current = {key(row) for row in rows}
        for path in CACHE_ROOT.glob('*/*/*'):
            if path.is_file() and path not in current:
                path.unlink()
                removed += 1
    report = {'at': time.time(), 'manifest_assets': len(rows), 'manifest_bytes': sum(row['size'] for row in rows),
              'downloaded_assets': len(missing), 'removed_stale': removed,
              'disk_free_bytes': shutil.disk_usage(CACHE_ROOT).free}
    report_path = CACHE_ROOT.parent / 'learning-asset-sync.json'
    with tempfile.NamedTemporaryFile(dir=report_path.parent, mode='w', delete=False) as temporary:
        json.dump(report, temporary)
        temporary.write('\n')
        temporary_name = temporary.name
    os.replace(temporary_name, report_path)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
