"""Reusable model behavior for transparent server-side encryption at rest."""

from django.db.models import DEFERRED

from .data_encryption import decrypt_payload, encrypt_payload, is_encrypted_payload


class EncryptedAtRestMixin:
    """Encrypt configured model fields while returning plaintext model attributes."""

    encrypted_field_groups: dict[str, tuple[str, ...]] = {}
    encryption_owner_field = 'user_id'

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._hydrate_encrypted_fields()
        return instance

    def _payload_context(self, payload_field: str) -> str:
        return f'{self._meta.label_lower}:{payload_field}'

    def _encryption_user_id(self) -> int | None:
        """Return the owner used for key derivation.

        Most protected models own a direct ``user`` relation. Outbox-like
        models can override this without duplicating the encryption behavior.
        """
        user_id = self.__dict__.get('user_id')
        if user_id:
            return int(user_id)
        return None

    def _hydrate_encrypted_fields(self):
        for payload_field, protected_fields in self.encrypted_field_groups.items():
            payload = self.__dict__.get(payload_field, DEFERRED)
            if payload is DEFERRED or not is_encrypted_payload(payload):
                continue
            user_id = self._encryption_user_id()
            if not user_id:
                raise ValueError(f'{self._meta.label} has no encryption owner.')
            decoded = decrypt_payload(
                payload,
                user_id=user_id,
                context=self._payload_context(payload_field),
            )
            for field_name in protected_fields:
                if field_name in decoded:
                    self.__dict__[field_name] = decoded[field_name]

    def refresh_from_db(self, using=None, fields=None):
        if fields is not None:
            expanded = set(fields)
            for payload_field, protected_fields in self.encrypted_field_groups.items():
                if expanded.intersection(protected_fields) or payload_field in expanded:
                    expanded.update(protected_fields)
                    expanded.add(payload_field)
                    expanded.add(self.encryption_owner_field)
            fields = tuple(expanded)
        super().refresh_from_db(using=using, fields=fields)
        self._hydrate_encrypted_fields()

    def _empty_database_value(self, field_name):
        field = self._meta.get_field(field_name)
        if field.null:
            return None
        default = field.get_default()
        return default if default is not None else ''

    def encrypted_storage_updates(self, *, enabled: bool) -> dict:
        user_id = self._encryption_user_id()
        if not user_id:
            raise ValueError(f'{self._meta.label} has no encryption owner.')
        updates = {}
        for payload_field, protected_fields in self.encrypted_field_groups.items():
            if enabled:
                values = {field_name: getattr(self, field_name) for field_name in protected_fields}
                updates[payload_field] = encrypt_payload(
                    values,
                    user_id=user_id,
                    context=self._payload_context(payload_field),
                )
                for field_name in protected_fields:
                    updates[field_name] = self._empty_database_value(field_name)
            else:
                for field_name in protected_fields:
                    updates[field_name] = getattr(self, field_name)
                updates[payload_field] = ''
        return updates

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        selected_groups = {}
        for payload_field, protected_fields in self.encrypted_field_groups.items():
            if (
                self._state.adding
                or update_fields is None
                or payload_field in update_fields
                or set(protected_fields).intersection(update_fields)
            ):
                selected_groups[payload_field] = protected_fields
        user_id = self._encryption_user_id()
        if not selected_groups or not user_id:
            return super().save(*args, **kwargs)

        from .data_encryption import user_encryption_enabled

        original_groups = self.encrypted_field_groups
        try:
            self.encrypted_field_groups = selected_groups
            enabled = user_encryption_enabled(user_id)
            database_values = self.encrypted_storage_updates(enabled=enabled)
            originals = {
                field_name: getattr(self, field_name)
                for protected_fields in selected_groups.values()
                for field_name in protected_fields
            }
            for field_name, value in database_values.items():
                setattr(self, field_name, value)
            if update_fields is not None:
                kwargs['update_fields'] = tuple(set(update_fields).union(database_values))
            try:
                result = super().save(*args, **kwargs)
            finally:
                for field_name, value in originals.items():
                    setattr(self, field_name, value)

            # A settings toggle may race a normal write. The toggle rewrites
            # existing rows after publishing its target state; this final check
            # also repairs the inverse ordering without locking ordinary writes.
            final_enabled = user_encryption_enabled(user_id)
            if final_enabled != enabled and self.pk:
                final_values = self.encrypted_storage_updates(enabled=final_enabled)
                type(self).objects.filter(pk=self.pk).update(**final_values)
                for payload_field in selected_groups:
                    setattr(self, payload_field, final_values[payload_field])
            return result
        finally:
            self.encrypted_field_groups = original_groups
