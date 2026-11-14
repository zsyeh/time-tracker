"""Account-owned UI preferences with field conflicts and an atomic JSON merge.

No runtime environment, learning content or transient window state belongs here.
GET/HTML reads do not create rows. The global CAS closes the read/merge/write
race on PostgreSQL and SQLite; field revisions avoid unrelated-setting conflicts.
"""
import json
import math
import re
from copy import deepcopy
from datetime import date

from django.utils import timezone
from django.utils.cache import patch_vary_headers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserPreferences


SCHEMA_VERSION = 1
MAX_PAYLOAD_BYTES = 32 * 1024
MAX_PRESETS = 10
MAX_CAS_ATTEMPTS = 8
MAX_REVISION = 2 ** 53 - 1  # Keep JSON integers exact for browser clients.

SIDEBAR_IDS = {
    'timer': ('today', 'trends', 'sessions', 'issues', 'subject-math',
              'subject-english', 'subject-major', 'subject-training'),
    'drill': ('selected-heatmap', 'insight', 'progress', 'practice', 'diagnostics',
              'activity', 'book-activity', 'heatmap', 'papers', 'favorites',
              'review-later', 'feel', 'errata'),
    'ei': ('core-heatmap', 'insight', 'progress', 'cockpit', 'practice', 'diagnostics',
           'circuit-selected', 'signal-selected', 'signal-formulas', 'analog-selected',
           'digital-selected', 'communication-selected', 'selected-pdf-pages',
           'activity', 'book-activity', 'heatmap', 'papers', 'favorites',
           'review-later', 'feel', 'errata'),
}
SIDEBAR_GROUPS = ('primary', 'tools', 'subjects')
ENUM_FIELDS = {
    'appearance': ('system', 'light', 'dark'),
    'accent': ('blue', 'cyan', 'green', 'lime', 'yellow', 'orange', 'pink',
               'magenta', 'purple', 'monochrome'),
    'font': ('compact', 'small', 'default', 'large', 'extra-large'),
    'language': ('en', 'zh-CN', 'ja'),
    'practice.next_mode': ('sequential', 'overdue', 'review', 'unattempted'),
    'practice.drill.copy_mode': ('off', 'link', 'image'),
    'practice.ei.copy_mode': ('off', 'link', 'image'),
    'practice.drill.study_timer_mode': ('remind', 'auto_start', 'off'),
    'practice.ei.study_timer_mode': ('remind', 'auto_start', 'off'),
}
BOOL_FIELDS = ('practice.review_auto_next', 'practice.mastered_auto_next')
FILTER_ENUMS = {
    'source_category': ('past_exam', 'adapted_exam', 'mock_exam', 'workbook',
                        'competition', 'other_practice', 'unclassified'),
    'type_group': ('small', 'large', 'short_answer', 'unknown'),
    'exam_type': ('choice', 'fill', 'judgment', 'short_answer', 'large', 'unknown'),
    'status': ('all', 'unattempted', 'mastered', 'review', 'overdue'),
    'marker': ('overconfident', 'concept_gap', 'rusty', 'forgotten'),
    'course': ('circuit', 'signal', 'analog', 'digital', 'communication'),
    'material': ('ready',), 'tier': ('core', 'advanced', 'foundation', 'cross'),
    'kind': ('analysis', 'design', 'calculation', 'concept'), 'combined': ('1',),
    'state': ('unattempted', 'mastered', 'review'), 'scope': ('all', 'past_exam', 'mock_exam'),
    'sort': ('relevance', 'source'),
    'favorite': ('1',), 'review_later': ('1',), 'include_structure': ('1',),
}
FILTER_KEYS = frozenset((*FILTER_ENUMS, 'q', 'document', 'topic', 'collection', 'bucket'))
COLLECTIONS = {
    'drill': ('selected',),
    'ei': ('circuit_selected', 'signal_selected', 'analog_selected',
           'digital_selected', 'communication_selected', 'core_selected'),
}


def preference_defaults():
    """Return an independent copy; never share mutable defaults across users."""
    defaults = {
        'appearance': 'system', 'accent': 'blue', 'font': 'small', 'language': 'en',
        'practice.next_mode': 'sequential', 'practice.review_auto_next': False,
        'practice.mastered_auto_next': True,
        'practice.drill.copy_mode': 'off', 'practice.ei.copy_mode': 'off',
        'practice.drill.study_timer_mode': 'remind', 'practice.ei.study_timer_mode': 'remind',
        'practice.image_copy_scale': 1,
        'filters.drill': [], 'filters.ei': [],
        'progress.drill': {'target': 24, 'deadline': '2026-11-21'},
        'progress.ei': {'target': 11, 'deadline': '2026-11-21'},
    }
    for workspace, ids in SIDEBAR_IDS.items():
        first_tool = 4 if workspace in ('timer', 'ei') else 3
        defaults['sidebar.' + workspace] = {
            'order': list(ids), 'hidden': list(ids[first_tool:]), 'collapsed_groups': [],
        }
    return defaults


def _invalid(message, key=None):
    raise ValidationError({'code': 'INVALID_PREFERENCES', 'detail': message,
                           **({'field': key} if key else {})})


def _string_list(value, allowed, key):
    if not isinstance(value, list) or len(value) > len(allowed):
        _invalid('Expected a bounded list of known IDs.', key)
    if any(not isinstance(item, str) or item not in allowed for item in value):
        _invalid('Unknown ID.', key)
    if len(set(value)) != len(value):
        _invalid('Duplicate IDs are not allowed.', key)
    return list(value)


def _sidebar(value, workspace, key):
    if not isinstance(value, dict) or set(value) != {'order', 'hidden', 'collapsed_groups'}:
        _invalid('Sidebar requires order, hidden and collapsed_groups only.', key)
    ids = SIDEBAR_IDS[workspace]
    order = _string_list(value['order'], ids, key)
    # A client predating a new route may submit a subset. Never lose that route.
    order.extend(item for item in ids if item not in order)
    return {
        'order': order,
        'hidden': _string_list(value['hidden'], ids, key),
        'collapsed_groups': _string_list(value['collapsed_groups'], SIDEBAR_GROUPS, key),
    }


def _filter_query(value, workspace, key):
    if not isinstance(value, dict) or set(value) - FILTER_KEYS:
        _invalid('Preset contains unknown or transient query fields.', key)
    result = {}
    for name, raw in value.items():
        if not isinstance(raw, str) or len(raw) > 256 or any(ord(c) < 32 for c in raw):
            _invalid('Preset query values must be bounded strings without control characters.', key)
        text = raw.strip()
        if not text:
            continue
        if name == 'q' and len(text) > 120:
            _invalid('Search keywords must not exceed the search API limit of 120 characters.', key)
        if name in FILTER_ENUMS and text not in FILTER_ENUMS[name]:
            _invalid('Unknown filter value: ' + name, key)
        if name in ('document', 'topic') and (
            not re.fullmatch(r'[1-9][0-9]{0,15}', text) or int(text) > MAX_REVISION
        ):
            _invalid('Document and topic IDs must be positive safe integers.', key)
        if name == 'bucket' and not re.fullmatch(r'[A-Za-z0-9_:-]{1,120}', text):
            _invalid('Invalid collection bucket.', key)
        if name == 'collection' and text not in COLLECTIONS[workspace]:
            _invalid('Collection is not part of this workspace.', key)
        result[name] = text
    return result


def _presets(value, workspace, key):
    if not isinstance(value, list) or len(value) > MAX_PRESETS:
        _invalid('At most ten explicitly saved presets are allowed per workspace.', key)
    result, seen = [], set()
    for preset in value:
        if not isinstance(preset, dict) or set(preset) != {'id', 'name', 'query'}:
            _invalid('A preset requires id, name and query only.', key)
        identifier, name = preset['id'], preset['name']
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', identifier):
            _invalid('Preset ID must be 1–64 ASCII letters, digits, hyphens or underscores.', key)
        if identifier in seen:
            _invalid('Preset IDs must be unique.', key)
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or any(ord(c) < 32 for c in name):
            _invalid('Preset name must contain 1–80 characters without control characters.', key)
        seen.add(identifier)
        result.append({'id': identifier, 'name': name.strip(),
                       'query': _filter_query(preset['query'], workspace, key)})
    return result


def _goal_settings(value, key):
    if not isinstance(value, dict) or set(value) != {'target', 'deadline'}:
        _invalid('Progress settings require target and deadline only.', key)
    target, deadline = value['target'], value['deadline']
    if type(target) is not int or not 1 <= target <= 500:
        _invalid('Daily workload target must be an integer from 1 to 500.', key)
    if not isinstance(deadline, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', deadline):
        _invalid('Deadline must be a calendar date in YYYY-MM-DD format.', key)
    try:
        date.fromisoformat(deadline)
    except ValueError:
        _invalid('Deadline must be a valid calendar date.', key)
    return {'target': target, 'deadline': deadline}


def _value(key, value):
    if key == 'practice.image_copy_scale':
        if type(value) not in (int, float) or not 1 <= value <= 8 or not math.isfinite(value):
            _invalid('Image copy scale must be a finite number from 1 to 8.', key)
        return value
    if key in ENUM_FIELDS:
        if not isinstance(value, str) or value not in ENUM_FIELDS[key]:
            _invalid('Unknown preference value.', key)
        return value
    if key in BOOL_FIELDS:
        if type(value) is not bool:
            _invalid('Expected a boolean.', key)
        return value
    if key in ('sidebar.timer', 'sidebar.drill', 'sidebar.ei'):
        return _sidebar(value, key.split('.')[1], key)
    if key in ('filters.drill', 'filters.ei'):
        return _presets(value, key.split('.')[1], key)
    if key in ('progress.drill', 'progress.ei'):
        return _goal_settings(value, key)
    _invalid('Unknown preference key.', key)


def _json_size(value):
    try:
        return len(json.dumps(value, ensure_ascii=False, allow_nan=False,
                              separators=(',', ':')).encode('utf-8'))
    except (TypeError, ValueError, UnicodeError, RecursionError):
        _invalid('Preferences must be valid bounded JSON.')


def _snapshot(row=None):
    values = preference_defaults()
    revisions = dict.fromkeys(values, 0)
    if row is not None:
        stored = row.values if isinstance(row.values, dict) else {}
        stored_revisions = row.field_revisions if isinstance(row.field_revisions, dict) else {}
        for key in values:
            if key in stored:
                try:
                    values[key] = _value(key, stored[key])
                except ValidationError:
                    pass  # Corrupt/removed legacy values cannot break the HTML shell.
            revision = stored_revisions.get(key, 0)
            if type(revision) is int and 0 <= revision <= row.revision:
                revisions[key] = revision
    return {'schema_version': row.schema_version if row else SCHEMA_VERSION,
            'revision': row.revision if row else 0,
            'values': values, 'field_revisions': revisions}


def preferences_snapshot(user):
    """Safe server-first HTML/auth hook. Does not create a row or use cookies."""
    if not user or not user.is_authenticated or not user.is_active:
        return _snapshot()
    return _snapshot(UserPreferences.objects.filter(user_id=user.pk).first())


class PreferencesConflict(Exception):
    def __init__(self, current, conflicts, code='PREFERENCES_CONFLICT'):
        self.payload = {'code': code, 'conflicts': conflicts, 'current': current}
        super().__init__(code)


def _validate_patch(payload):
    if not isinstance(payload, dict) or set(payload) != {'schema_version', 'changes', 'base_revisions'}:
        _invalid('Expected schema_version, changes and base_revisions only.')
    if type(payload['schema_version']) is not int or payload['schema_version'] != SCHEMA_VERSION:
        _invalid('Unsupported preferences schema version.')
    if _json_size(payload) > MAX_PAYLOAD_BYTES:
        _invalid('Preferences payload exceeds 32 KiB.')
    changes, bases = payload['changes'], payload['base_revisions']
    if not isinstance(changes, dict) or not changes or not isinstance(bases, dict) or set(changes) != set(bases):
        _invalid('Each changed field requires exactly one base revision.')
    for key, revision in bases.items():
        if type(revision) is not int or not 0 <= revision <= MAX_REVISION:
            _invalid('Base revisions must be non-negative safe integers.', key)
    return {key: _value(key, value) for key, value in changes.items()}, bases


def patch_preferences(user, payload):
    if not user or not user.is_authenticated or not user.is_active:
        raise PermissionDenied('Authentication is required.')
    changes, bases = _validate_patch(payload)
    for _ in range(MAX_CAS_ATTEMPTS):
        row = UserPreferences.objects.filter(user_id=user.pk).first()
        current = _snapshot(row)
        if current['schema_version'] != SCHEMA_VERSION:
            raise PreferencesConflict(current, [], 'PREFERENCES_SCHEMA_CHANGED')
        conflicts = [key for key in changes if current['field_revisions'][key] != bases[key]]
        if conflicts:
            raise PreferencesConflict(current, conflicts)
        changed = {key: value for key, value in changes.items() if current['values'][key] != value}
        if not changed:
            return current
        if row is None:
            # OneToOne uniqueness resolves simultaneous first writes; re-read
            # and recheck field revisions rather than assuming an empty row.
            UserPreferences.objects.get_or_create(user_id=user.pk)
            continue
        if row.revision >= MAX_REVISION:
            raise PreferencesConflict(current, [], 'PREFERENCES_REVISION_LIMIT')
        values = deepcopy(row.values) if isinstance(row.values, dict) else {}
        revisions = deepcopy(row.field_revisions) if isinstance(row.field_revisions, dict) else {}
        next_revision = row.revision + 1
        values.update(changed)
        revisions.update(dict.fromkeys(changed, next_revision))
        if _json_size(values) > MAX_PAYLOAD_BYTES:
            _invalid('Saved preferences exceed 32 KiB.')
        # Single atomic UPDATE closes the stale read/merge race even on SQLite,
        # where select_for_update does not provide a row lock. Unrelated fields
        # retry from fresh state; same-field edits return a recoverable conflict.
        updated = UserPreferences.objects.filter(
            user_id=user.pk, revision=row.revision, schema_version=SCHEMA_VERSION,
        ).update(values=values, field_revisions=revisions, revision=next_revision,
                 updated_at=timezone.now())
        if updated:
            row.values, row.field_revisions, row.revision = values, revisions, next_revision
            return _snapshot(row)
    current = preferences_snapshot(user)
    conflicts = [key for key in changes if current['field_revisions'][key] != bases[key]]
    raise PreferencesConflict(current, conflicts, 'PREFERENCES_CONFLICT')


class UserPreferencesView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    http_method_names = ['get', 'patch', 'head', 'options']

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        patch_vary_headers(response, ('Cookie',))
        return response

    def get(self, request):
        return Response(preferences_snapshot(request.user))

    def patch(self, request):
        if len(request.body) > MAX_PAYLOAD_BYTES:
            _invalid('Preferences payload exceeds 32 KiB.')
        try:
            return Response(patch_preferences(request.user, request.data))
        except PreferencesConflict as exc:
            # Do not pass snapshots through APIException's ErrorDetail coercion:
            # the conflict response must retain typed booleans/integers/arrays.
            return Response(exc.payload, status=409)
