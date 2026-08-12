"""Server-managed encryption helpers for optional per-user data-at-rest protection.

This deliberately is not end-to-end encryption: Django can obtain the server
master key and decrypt records in memory so existing search, export, GitHub sync,
and public sharing behavior remains available.
"""

import base64
import hashlib
import hmac
import json
import os
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.cache import cache
from django.db import transaction


PAYLOAD_PREFIX = 'enc:aesgcm:v1:'
KEY_BYTES = 32
NONCE_BYTES = 12


class DataEncryptionError(RuntimeError):
    """Raised when encrypted data cannot be safely read or written."""


def _decode_key(value: str) -> bytes:
    try:
        encoded = value.strip().encode('ascii')
        encoded += b'=' * (-len(encoded) % 4)
        key = base64.urlsafe_b64decode(encoded)
    except (UnicodeEncodeError, ValueError) as exc:
        raise DataEncryptionError('The configured data encryption key is invalid.') from exc
    if len(key) != KEY_BYTES:
        raise DataEncryptionError('The data encryption key must contain 32 random bytes.')
    return key


@lru_cache(maxsize=8)
def _read_configured_key(configured_value: str, key_path_value: str) -> bytes | None:
    if configured_value:
        return _decode_key(configured_value)
    key_path = Path(key_path_value)
    if not key_path.exists():
        return None
    try:
        key = _decode_key(key_path.read_text(encoding='ascii'))
        os.chmod(key_path, 0o600)
        return key
    except OSError as exc:
        raise DataEncryptionError('The server data encryption key is not readable.') from exc


def _key_sources() -> tuple[str, str]:
    return (
        str(getattr(settings, 'DATA_ENCRYPTION_MASTER_KEY', '') or '').strip(),
        str(settings.DATA_ENCRYPTION_KEY_PATH),
    )


def master_key(*, create: bool = False) -> bytes | None:
    configured_value, key_path_value = _key_sources()
    key = _read_configured_key(configured_value, key_path_value)
    if key is not None or not create or configured_value:
        return key

    key_path = Path(key_path_value)
    temporary_path = key_path.with_name(
        f'.{key_path.name}.{os.getpid()}.{os.urandom(8).hex()}.tmp',
    )
    try:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        generated = os.urandom(KEY_BYTES)
        encoded = base64.urlsafe_b64encode(generated).decode('ascii')
        descriptor = os.open(
            temporary_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, 'w', encoding='ascii') as key_file:
            key_file.write(f'{encoded}\n')
            key_file.flush()
            os.fsync(key_file.fileno())
        # Publishing a fully written hard link avoids another worker observing
        # an empty/partial key. The first worker wins; all others read its key.
        os.link(temporary_path, key_path)
    except FileExistsError:
        pass
    except OSError as exc:
        raise DataEncryptionError('The server could not create its data encryption key.') from exc
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass

    _read_configured_key.cache_clear()
    key = _read_configured_key(configured_value, key_path_value)
    if key is None:
        raise DataEncryptionError('The server data encryption key is unavailable.')
    return key


def encryption_available() -> bool:
    try:
        return master_key(create=False) is not None
    except DataEncryptionError:
        return False


@lru_cache(maxsize=4096)
def _derived_user_key(master_key_value: bytes, user_id: int) -> bytes:
    context = f'time-tracker:user-data:v1:{int(user_id)}'.encode('ascii')
    return hmac.new(master_key_value, context, hashlib.sha256).digest()


def is_encrypted_payload(value) -> bool:
    return isinstance(value, str) and value.startswith(PAYLOAD_PREFIX)


def encrypt_payload(data: dict, *, user_id: int, context: str) -> str:
    root_key = master_key(create=False)
    if root_key is None:
        raise DataEncryptionError('The server data encryption key is unavailable.')
    nonce = os.urandom(NONCE_BYTES)
    plaintext = json.dumps(
        data,
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True,
    ).encode('utf-8')
    associated_data = f'time-tracker:v1:{int(user_id)}:{context}'.encode('utf-8')
    ciphertext = AESGCM(_derived_user_key(root_key, int(user_id))).encrypt(
        nonce,
        plaintext,
        associated_data,
    )
    return PAYLOAD_PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode('ascii')


def decrypt_payload(value: str, *, user_id: int, context: str) -> dict:
    if not is_encrypted_payload(value):
        raise DataEncryptionError('The stored data is not a supported encrypted payload.')
    root_key = master_key(create=False)
    if root_key is None:
        raise DataEncryptionError('The server data encryption key is unavailable.')
    try:
        raw = base64.urlsafe_b64decode(value[len(PAYLOAD_PREFIX):].encode('ascii'))
        nonce, ciphertext = raw[:NONCE_BYTES], raw[NONCE_BYTES:]
        associated_data = f'time-tracker:v1:{int(user_id)}:{context}'.encode('utf-8')
        plaintext = AESGCM(_derived_user_key(root_key, int(user_id))).decrypt(
            nonce,
            ciphertext,
            associated_data,
        )
        decoded = json.loads(plaintext.decode('utf-8'))
    except Exception as exc:
        raise DataEncryptionError('Encrypted user data failed authentication.') from exc
    if not isinstance(decoded, dict):
        raise DataEncryptionError('Encrypted user data has an invalid structure.')
    return decoded


def user_encryption_enabled(user_id: int | None) -> bool:
    if not user_id:
        return False
    from .models import UserDataEncryptionPreference

    return UserDataEncryptionPreference.objects.filter(
        user_id=user_id,
        enabled=True,
    ).exists()


def encryption_status(user) -> dict:
    from .models import UserDataEncryptionPreference

    preference = UserDataEncryptionPreference.objects.filter(user=user).first()
    return {
        'enabled': bool(preference and preference.enabled),
        'available': encryption_available(),
        'algorithm': 'AES-256-GCM',
        'mode': 'server-managed-at-rest',
        'updated_at': preference.updated_at if preference else None,
    }


def set_user_encryption(user, enabled: bool) -> dict:
    """Publish the target policy, then rewrite all protected rows."""

    from .models import (
        GitHubNoteSync, LearningIssue, StudyTag, TaskPreset, TimeLog,
        UserDataEncryptionPreference,
    )

    migrated = 0
    preference, _ = UserDataEncryptionPreference.objects.get_or_create(user=user)
    with transaction.atomic():
        # Serialize toggles from separate tabs and make the policy plus all row
        # rewrites one rollback-safe state transition.
        preference = UserDataEncryptionPreference.objects.select_for_update().get(
            pk=preference.pk,
        )
        if enabled:
            key = master_key(create=not preference.enabled)
            if key is None:
                # Never silently replace a lost key for existing ciphertext.
                raise DataEncryptionError('The server data encryption key is unavailable.')
        if preference.enabled == enabled:
            payload = encryption_status(user)
            payload['migrated_records'] = 0
            return payload
        preference.enabled = enabled
        preference.save(update_fields=('enabled', 'updated_at'))

        for model in (TimeLog, LearningIssue, StudyTag, TaskPreset):
            for instance in model.objects.filter(user_id=user.pk).iterator(chunk_size=200):
                updates = instance.encrypted_storage_updates(enabled=enabled)
                model.objects.filter(pk=instance.pk).update(**updates)
                migrated += 1
        for sync in GitHubNoteSync.objects.filter(
            session__user_id=user.pk,
        ).select_related('session').iterator(chunk_size=200):
            updates = sync.encrypted_storage_updates(enabled=enabled)
            GitHubNoteSync.objects.filter(pk=sync.pk).update(**updates)
            migrated += 1

    cache.set(f'dashboard-version:{user.pk}', os.urandom(8).hex(), timeout=None)
    payload = encryption_status(user)
    payload['migrated_records'] = migrated
    return payload
