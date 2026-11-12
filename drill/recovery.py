"""Opt-in foreground timing on the existing timer model; no attempt creation."""
import datetime as dt
import math
import logging
import re
from urllib.parse import parse_qsl, urlsplit
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import LearningRecoveryState, Question, QuestionTimingSession

LEASE_SECONDS = 45
MAX_MS = 43200000
logger = logging.getLogger(__name__)
TIMING_CONFLICT_REASONS = frozenset(('owner_mismatch', 'lease_expired', 'stale_sequence',
    'active_timer_mismatch', 'timing_round_missing', 'timing_round_mismatch',
    'timing_protocol_mismatch', 'timing_finalized'))

class RecoveryConflict(APIException):
    status_code = 409
    default_detail = 'Another foreground window owns this timer. Local progress is retained.'

def timing_conflict(reason, timer=None, *, state=None, owner=None):
    """Stable, non-sensitive diagnostics; never log tokens, owners or study text."""
    reason = reason if reason in TIMING_CONFLICT_REASONS else 'timing_conflict'
    active = state.active_timer if state else timer
    retry_after = 0
    if active:
        try:
            lease = dt.datetime.fromisoformat((active.recovery or {}).get('lease_until', ''))
            retry_after = max(math.ceil((lease - timezone.now()).total_seconds()), 0)
        except (ValueError, TypeError):
            pass
    live = bool(active and _live(active, timezone.now()))
    owner_matches = bool(active and (active.recovery or {}).get('owner') == str(owner))
    can_reclaim = bool(state is not None and (not live or owner_matches))
    logger.warning('question_timing_conflict reason=%s', reason)
    error = RecoveryConflict({'detail': RecoveryConflict.default_detail, 'reason': reason})
    # APIException normally casts every primitive to ErrorDetail(str); retain
    # actual booleans so 'False' cannot become truthy in browser recovery logic.
    error.detail.update(lease_retry_after=retry_after, lease_live=live,
                        owner_matches=owner_matches,
                        active_matches=bool(active and timer and active.pk == timer.pk),
                        can_reclaim=can_reclaim)
    return error


def _lock(user):
    # Serialize the initial creation as well as every later lease/location change.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    state, _ = LearningRecoveryState.objects.get_or_create(user=user)
    return state

def _live(timer, now):
    r = timer.recovery or {}
    return not r.get('finalized') and r.get('lease_until', '') > now.isoformat()

def payload(timer, now):
    r = timer.recovery or {}
    return {'protocol': 2, 'timing_key': str(timer.client_key), 'server_now': now,
            'starts_at': timer.starts_at, 'elapsed_ms': r.get('elapsed_ms', 0),
            'countdown_ms': r.get('countdown_ms', 5000), 'sequence': r.get('sequence', 0),
            'lease_until': r.get('lease_until'), 'owner': r.get('owner'),
            'finalized': r.get('finalized', False)}

def _checkpoint(timer, data, now):
    r = dict(timer.recovery)
    if r.get('finalized'):
        raise timing_conflict('timing_finalized', timer)
    if r.get('owner') != str(data.get('owner')):
        raise timing_conflict('owner_mismatch', timer)
    seq = data.get('sequence', 0)
    # Absolute cumulative snapshots, never additive deltas. Retries/out-of-order
    # requests do not renew a lease or change duration.
    if seq > r.get('sequence', 0):
        last = dt.datetime.fromisoformat(r['checkpoint_at'])
        ceiling = r.get('elapsed_ms', 0) + max(0, int((now-last).total_seconds()*1000)) + 2000
        requested = data.get('elapsed_ms', r.get('elapsed_ms', 0))
        if requested > min(MAX_MS, ceiling):
            raise ValidationError({'elapsed_ms': 'Checkpoint exceeds the observable time window.'})
        r.update(elapsed_ms=max(r.get('elapsed_ms', 0), requested), sequence=seq,
                 countdown_ms=min(r.get('countdown_ms', 5000), data.get('countdown_ms', 5000)),
                 checkpoint_at=now.isoformat(), lease_until=(now+dt.timedelta(seconds=LEASE_SECONDS)).isoformat())
    timer.recovery = r

def timing_request(user, question, data):
    if not data.get('owner') or not data.get('timing_key'):
        raise ValidationError('owner and timing_key are required for protocol 2.')
    now = timezone.now()
    with transaction.atomic():
        state = _lock(user)
        action = data['action']
        timer = QuestionTimingSession.objects.select_for_update().filter(
            user=user, question=question, client_key=data['timing_key']).first()
        if action == 'claim':
            if timer is None:
                # A new device resumes the existing unsubmitted round, not a
                # second timer/statistics stream. User lock prevents creation races.
                timer = QuestionTimingSession.objects.filter(user=user, question=question,
                    recovery__protocol=2, recovery__finalized=False).order_by('-created_at').first()
            if timer and (timer.recovery or {}).get('finalized'):
                return payload(timer, now)
            active = state.active_timer
            # Shared browser storage is not proof that an older document died.
            # Never transfer a still-live lease to a different document owner.
            if active and _live(active, now) and active.recovery.get('owner') != str(data['owner']):
                raise timing_conflict('owner_mismatch' if active.pk == getattr(timer, 'pk', None) else 'active_timer_mismatch', timer,
                                      state=state, owner=data['owner'])
            if timer is None:
                timer = QuestionTimingSession.objects.create(user=user, question=question,
                    client_key=data['timing_key'], starts_at=now+dt.timedelta(seconds=5),
                    recovery={'protocol': 2, 'elapsed_ms': 0, 'countdown_ms': 5000,
                              'sequence': 0, 'finalized': False})
            if not (timer.recovery or {}).get('protocol') == 2:
                raise timing_conflict('timing_protocol_mismatch', timer)
            r = dict(timer.recovery)
            previous_owner = r.get('owner')
            local_base_valid = previous_owner in (None, str(data['owner'])) or (
                previous_owner == str(data.get('resume_owner'))
                and r.get('elapsed_ms', 0) == data.get('base_elapsed_ms'))
            if local_base_valid and state.active_timer_id == timer.pk and _live(timer, now) and data.get('sequence', 0) <= r.get('sequence', 0):
                return {**payload(timer, now), 'local_base_valid': True}
            r.update(sequence=max(r.get('sequence', 0)+1, data.get('sequence', 0)), owner=str(data['owner']), checkpoint_at=r.get('checkpoint_at', now.isoformat()) if local_base_valid else now.isoformat(),
                     lease_until=(now+dt.timedelta(seconds=LEASE_SECONDS)).isoformat())
            timer.recovery = r
            timer.stopped_at = None
            state.active_timer = timer
            state.save(update_fields=['active_timer'])
        elif action in ('checkpoint', 'pause'):
            if timer is None:
                raise timing_conflict('timing_round_missing', state=state, owner=data['owner'])
            if (timer.recovery or {}).get('owner') != str(data.get('owner')):
                raise timing_conflict('owner_mismatch', timer, state=state, owner=data['owner'])
            if state.active_timer_id != timer.pk:
                # Duplicate pause is harmless; late snapshots may not overwrite
                # a newly claimed device/question's ownership.
                if action == 'pause' and data.get('sequence', 0) <= timer.recovery.get('sequence', 0):
                    return {**payload(timer, now), 'active_matches': False}
                raise timing_conflict('active_timer_mismatch', timer, state=state, owner=data['owner'])
            if data.get('sequence', 0) <= timer.recovery.get('sequence', 0):
                return payload(timer, now)
            _checkpoint(timer, data, now)
            if action == 'pause':
                timer.recovery['lease_until'] = now.isoformat()
                timer.stopped_at = now
                state.active_timer = None
                state.save(update_fields=['active_timer'])
        else:
            raise ValidationError('Use claim/checkpoint/pause for protocol 2.')
        timer.save(update_fields=['recovery', 'stopped_at'])
        return {**payload(timer, now), **({'local_base_valid': local_base_valid} if action == 'claim' else {})}

def validate_attempt_timing(data):
    """Protocol 2 may not silently fall through to unverified legacy duration."""
    if data.get('timing_protocol') != 2:
        if data.get('timing_omit'):
            raise ValidationError({'timing_omit': 'Protocol 2 is required to explicitly omit timing.'})
        return
    if data.get('timing_omit') and data.get('time_spent_seconds') is not None:
        raise ValidationError({'time_spent_seconds': 'Explicitly omitted timing must not include a duration.'})
    required = ['timing_key', 'timing_owner', 'submission_key']
    if not data.get('timing_omit'):
        required += ['timing_sequence', 'timing_elapsed_ms']
    missing = [field for field in required if field not in data or data[field] is None]
    if missing:
        raise ValidationError({field: 'Required for protocol 2 submission.' for field in missing})


def omit_timing(user, question, key, owner, submission_key):
    """Record explicit omission without changing another document's live timer."""
    now = timezone.now()
    state = _lock(user)
    timer = QuestionTimingSession.objects.select_for_update().filter(
        user=user, question=question, client_key=key).first()
    if timer is None and QuestionTimingSession.objects.filter(client_key=key).exists():
        raise timing_conflict('timing_round_mismatch', state=state, owner=owner)
    recovery = dict(timer.recovery or {}) if timer else {}
    if timer and recovery.get('protocol') != 2:
        raise timing_conflict('timing_protocol_mismatch', timer)
    if recovery.get('finalized'):
        raise timing_conflict('timing_finalized', timer)
    if timer is None or recovery.get('owner') != str(owner):
        # Keep an audit link in the existing timer metadata. A foreign-owner
        # round remains untouched, including its active pointer and lease.
        audit_key = submission_key if timer else key
        if QuestionTimingSession.objects.filter(user=user, question=question, client_key=audit_key).exists():
            raise timing_conflict('timing_round_mismatch', state=state, owner=owner)
        return QuestionTimingSession.objects.create(user=user, question=question, client_key=audit_key,
            starts_at=now, stopped_at=now, recovery={'protocol': 2, 'finalized': True,
                'owner': str(owner), 'elapsed_ms': 0, 'sequence': 0,
                'requested_timing_key': str(key), 'time_basis': 'explicitly_omitted',
                'lease_until': now.isoformat()})
    recovery.update(finalized=True, lease_until=now.isoformat(), time_basis='explicitly_omitted')
    timer.recovery, timer.stopped_at = recovery, now
    timer.save(update_fields=['recovery', 'stopped_at'])
    if state.active_timer_id == timer.pk:
        state.active_timer = None
        state.save(update_fields=['active_timer'])
    return timer


def finish_timing(user, question, key, data):
    """Called inside existing attempt transaction/idempotency lock."""
    now = timezone.now()
    state = _lock(user)
    timer = QuestionTimingSession.objects.select_for_update().filter(user=user, question=question, client_key=key).first()
    if timer is None:
        raise timing_conflict('timing_round_missing', state=state, owner=data.get('timing_owner'))
    r = timer.recovery or {}
    if r.get('protocol') != 2:
        raise timing_conflict('timing_protocol_mismatch', timer, state=state, owner=data.get('timing_owner'))
    if r.get('finalized'):
        raise timing_conflict('timing_finalized', timer, state=state, owner=data.get('timing_owner'))
    if r.get('owner') != str(data.get('timing_owner')):
        raise timing_conflict('owner_mismatch', timer, state=state, owner=data.get('timing_owner'))
    if state.active_timer_id != timer.pk:
        raise timing_conflict('active_timer_mismatch', timer, state=state, owner=data.get('timing_owner'))
    if not _live(timer, now):
        raise timing_conflict('lease_expired', timer, state=state, owner=data.get('timing_owner'))
    if data.get('timing_sequence', 0) < r.get('sequence', 0):
        raise timing_conflict('stale_sequence', timer, state=state, owner=data.get('timing_owner'))
    _checkpoint(timer, {'owner': data.get('timing_owner'), 'sequence': data.get('timing_sequence', 0),
                        'elapsed_ms': data.get('timing_elapsed_ms', 0)}, now)
    timer.recovery.update(finalized=True, lease_until=now.isoformat())
    timer.stopped_at = now
    timer.save(update_fields=['recovery', 'stopped_at'])
    state.active_timer = None
    state.save(update_fields=['active_timer'])
    value = timer.recovery['elapsed_ms'] // 1000
    return value if 1 <= value <= 43200 else None

# Navigation metadata only. No credentials, tokens, arbitrary URLs or user text.
def valid_location(workspace, path, user=None):
    if workspace not in ('timer', 'drill', 'ei') or not isinstance(path, str) or len(path) > 2048:
        return False
    p = urlsplit(path)
    if p.scheme or p.netloc or p.fragment or not path.startswith('/') or path.startswith('//') or '\\' in path:
        return False
    if any(re.search(r'token|password|secret|csrf|key|pwa_launch', k, re.I) for k, _ in parse_qsl(p.query)):
        return False
    if workspace == 'timer':
        if re.fullmatch(r'/sessions/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', p.path):
            from tracker.models import TimeLog
            return user is not None and TimeLog.objects.filter(user=user, uuid=p.path.split('/')[-1]).exists()
        return bool(re.fullmatch(r'/(?:today|trends|sessions(?:/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})?|issues|settings)?', p.path))
    prefix = f'/{workspace}'
    route = p.path.removeprefix(prefix) if p.path.startswith(prefix+'/') else p.path
    if re.fullmatch(r'/practice/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', route):
        return Question.objects.filter(uuid=route.split('/')[-1], document__workspace=workspace).exists()
    if route == '/papers/new':
        return True
    paper = re.fullmatch(r'/papers/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:/review)?', route)
    if paper:
        from .models import ExamPaper
        subject = 'ei' if workspace == 'ei' else 'math2'
        return user is not None and ExamPaper.objects.filter(uuid=paper.group(1), user=user, blueprint__subject=subject).exists()
    return bool(re.fullmatch(r'/(?:practice|progress|settings|selected-pdf-pages|activity|book-activity|heatmap|selected-heatmap|core-heatmap|insight|favorites|review-later|diagnostics|diagnostic-queue|cockpit|circuit-selected|signal-selected|signal-formulas|analog-selected|digital-selected|communication-selected|papers|errata|feel)', route))

class LearningRecoveryView(APIView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response

    def get(self, request):
        state = LearningRecoveryState.objects.filter(user=request.user).first()
        locations = {k:v for k,v in (state.locations if state else {}).items() if valid_location(k, v.get('path'), request.user)}
        last = state.last_workspace if state and state.last_workspace in locations else None
        return Response({'version': state.version if state else 0, 'last_workspace': last, 'locations': locations})

    def put(self, request):
        workspace = request.data.get('workspace')
        location = request.data.get('location', {})
        if not isinstance(location, dict) or not valid_location(workspace, location.get('path'), request.user):
            raise ValidationError('This learning location is unavailable or outside the allowed routes.')
        scroll = location.get('scroll', {})
        if not isinstance(scroll, dict):
            raise ValidationError('Invalid scroll state.')
        safe_scroll = {k: min(10000000, max(0, int(v))) for k,v in scroll.items()
                       if k in ('window', 'right', 'left') and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)}
        with transaction.atomic():
            state = _lock(request.user)
            if type(request.data.get('version')) is not int or request.data.get('version') != state.version:
                raise RecoveryConflict('Resume state was updated in another window; reload its version.')
            state.version += 1
            state.locations = {**state.locations, workspace: {'path': location['path'], 'scroll': safe_scroll,
                               'updated_at': timezone.now().isoformat()}}
            state.last_workspace = workspace
            state.save(update_fields=['version', 'locations', 'last_workspace', 'updated_at'])
        return Response({'version': state.version, 'last_workspace': workspace, 'locations': state.locations})
