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
    return session, False


def finish_session(session, reflection):
    required = ('note', 'breakthrough', 'problems', 'next_action')
    missing = [field for field in required if not str(reflection.get(field, '')).strip()]
    if not str(reflection.get('chapter', '')).strip() and not str(
        reflection.get('topic', '')
    ).strip():
        missing.append('chapter_or_topic')
    if missing:
        raise ValueError(f"missing reflection fields: {', '.join(missing)}")

    with transaction.atomic():
        locked = TimeLog.objects.select_for_update().get(pk=session.pk, user=session.user)
        if locked.status != 'running':
            return locked, False
        locked.end_time = timezone.now()
        locked.status = 'completed'
        for field in (
            'chapter',
            'topic',
            'learning_mode',
            'difficulty',
            'energy_level',
            'focus_level',
            'confidence_after',
            'note',
            'breakthrough',
            'problems',
            'next_action',
        ):
            if field in reflection:
                setattr(locked, field, reflection[field])
        locked.full_clean()
        locked.save()
    return locked, True


def abandon_session(session):
    with transaction.atomic():
        locked = TimeLog.objects.select_for_update().get(pk=session.pk, user=session.user)
        if locked.status == 'running':
            locked.end_time = timezone.now()
            locked.status = 'abandoned'
            locked.save(update_fields=('end_time', 'status', 'updated_at'))
    return locked


def local_day_bounds(day):
    current_timezone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.datetime.combine(day, datetime.time.min), current_timezone)
    return start, start + datetime.timedelta(days=1)
