import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('sync_learning_assets', Path(__file__).with_name('sync-learning-assets.py'))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class FakeProcess:
    def __init__(self, payload):
        self.stdout = io.BytesIO(payload)

    def wait(self):
        return 0

    def poll(self):
        return 0


class CacheIntegrityTests(unittest.TestCase):
    def test_verified_install_and_corruption(self):
        content = b'authorized-image-bytes'
        digest = hashlib.sha256(content).hexdigest()
        row = {'id': 42, 'workspace': 'ei', 'sha256': digest, 'size': len(content)}
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w') as archive:
            info = tarfile.TarInfo(f'ei/42/{digest}')
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(sync, 'CACHE_ROOT', Path(directory)), patch.object(sync.subprocess, 'Popen', return_value=FakeProcess(tar_buffer.getvalue())):
                sync.install_stream([row])
                path = sync.key(row)
                self.assertTrue(sync.verified(path, row))
                os.chmod(path, 0o600)
                path.write_bytes(b'corrupted-image-bytes')
                self.assertFalse(sync.verified(path, row))

    def test_unexpected_tar_member_is_rejected(self):
        content = b'wrong'
        digest = hashlib.sha256(content).hexdigest()
        row = {'id': 42, 'workspace': 'drill', 'sha256': digest, 'size': len(content)}
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w') as archive:
            info = tarfile.TarInfo(f'ei/42/{digest}')
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(sync, 'CACHE_ROOT', Path(directory)), patch.object(sync.subprocess, 'Popen', return_value=FakeProcess(tar_buffer.getvalue())):
                with self.assertRaisesRegex(RuntimeError, 'Unexpected asset'):
                    sync.install_stream([row])
                self.assertFalse(sync.key(row).exists())


if __name__ == '__main__':
    unittest.main()
