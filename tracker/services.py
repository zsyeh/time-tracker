import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import TimeLog


SUBJECT_ALIASES = {
    'math': 'math',
    'english': 'english',
    'professional': 'major',
    'major': 'major',
    'training': 'training',
}
MINIMUM_SESSION_MINUTES = 25
MAXIMUM_SESSION_HOURS = 12


class ActiveSessionConflict(Exception):
    def __init__(self, session):
        self.session = session
        super().__init__('another subject is already running')


def normalize_subject(subject):
    try:
        return SUBJECT_ALIASES[subject]
    except KeyError as exc:
        raise ValueError('unsupported subject') from exc


def get_service_user():
    User = get_user_model()
    username = settings.TRACKER_OWNER_USERNAME
    if username:
        return User.objects.get(username=username, is_active=True)
    user = User.objects.filter(is_superuser=True, is_active=True).order_by('pk').first()
    if not user:
        raise RuntimeError('TRACKER_OWNER_USERNAME must reference an active user')
    return user


def start_session(user, subject, **metadata):
    category = normalize_subject(subject)
    now = timezone.now()
    with transaction.atomic():
        active = TimeLog.objects.select_for_update().filter(
            user=user,
            status='running',
        ).first()
        if active and is_long_session(active.start_time, now):
            active.delete()
            active = None
        if active:
            if active.category == category:
                return active, True
            raise ActiveSessionConflict(active)
        try:
            session = TimeLog.objects.create(
                user=user,
                category=category,
                start_time=now,
                status='running',
                task_preset=metadata.get('task_preset'),
                task_path=metadata.get('task_path', ''),
                chapter=metadata.get('chapter', ''),
                topic=metadata.get('topic', ''),
                learning_mode=metadata.get('learning_mode', ''),
                confidence_before=metadata.get('confidence_before'),
            )
        except IntegrityError:
            active = TimeLog.objects.get(user=user, status='running')
            if active.category == category:
                return active, True
            raise ActiveSessionConflict(active)
        task_preset = metadata.get('task_preset')
        if task_preset is not None:
            session.tags.set(task_preset.tags.all())
    return session, False


def is_short_session(start_time, end_time):
    return (end_time - start_time).total_seconds() < MINIMUM_SESSION_MINUTES * 60


def is_long_session(start_time, end_time):
    return (end_time - start_time).total_seconds() > MAXIMUM_SESSION_HOURS * 60 * 60


def session_discard_reason(start_time, end_time):
    if is_short_session(start_time, end_time):
        return 'shorter_than_minimum'
    if is_long_session(start_time, end_time):
        return 'longer_than_maximum'
    return None


def finish_session(session, reflection):
    with transaction.atomic():
        locked = TimeLog.objects.select_for_update().get(pk=session.pk, user=session.user)
        if locked.status != 'running':
            return locked, False, None
        end_time = timezone.now()
        discard_reason = session_discard_reason(locked.start_time, end_time)
        if discard_reason:
            locked.delete()
            return None, True, discard_reason

        reflection = dict(reflection)
        selected_tags = reflection.pop('tags', None)
        if not str(reflection.get('title', '')).strip() and locked.task_path:
            reflection['title'] = locked.task_path.split(' › ')[-1].strip()

        locked.end_time = end_time
        locked.status = 'completed'
        for field in (
            'chapter',
            'topic',
            'learning_mode',
            'difficulty',
            'energy_level',
            'focus_level',
            'confidence_after',
            'title',
            'details',
            'breakthrough',
            'problems',
            'next_action',
        ):
            if field in reflection:
                setattr(locked, field, reflection[field])
        locked.full_clean()
        locked.save()
        if selected_tags is not None:
            locked.tags.set(selected_tags)
    return locked, True, None


def abandon_session(session):
    with transaction.atomic():
        locked = TimeLog.objects.select_for_update().get(pk=session.pk, user=session.user)
        if locked.status == 'running':
            locked.delete()
            return True
    return False


def local_day_bounds(day):
    current_timezone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.datetime.combine(day, datetime.time.min), current_timezone)
    return start, start + datetime.timedelta(days=1)
