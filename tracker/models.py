import datetime
import hashlib
import secrets
import uuid as uuid_lib
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .encrypted_models import EncryptedAtRestMixin


SUBJECT_CHOICES = [
    ('math', 'Mathematics'),
    ('english', 'English'),
    ('major', 'Major'),
    ('training', 'Training'),
]


class StudyTag(EncryptedAtRestMixin, models.Model):
    """Reusable user-owned label attached to presets and completed Sessions."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_tags',
    )
    name = models.CharField(max_length=64)
    color = models.CharField(max_length=16, default='green')
    encrypted_content = models.TextField(blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    encrypted_field_groups = {'encrypted_content': ('name',)}

    class Meta:
        ordering = ('name', 'pk')
        indexes = [models.Index(fields=('user',), name='tag_user_idx')]

    def __str__(self):
        return self.name


class TaskPreset(EncryptedAtRestMixin, models.Model):
    """A user-owned subject task tree with at most four custom levels."""

    MAX_DEPTH = 4

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_presets',
    )
    uuid = models.UUIDField(default=uuid_lib.uuid4, editable=False, unique=True)
    subject = models.CharField(max_length=20, choices=SUBJECT_CHOICES)
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='children',
    )
    tags = models.ManyToManyField(StudyTag, blank=True, related_name='task_presets')
    is_home_shortcut = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    encrypted_content = models.TextField(blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    encrypted_field_groups = {'encrypted_content': ('name',)}

    class Meta:
        ordering = ('subject', 'sort_order', 'created_at')
        indexes = [
            models.Index(fields=('user', 'subject', 'is_active'), name='preset_user_subject_idx'),
            models.Index(fields=('user', 'is_home_shortcut'), name='preset_user_home_idx'),
        ]

    @property
    def depth(self):
        depth = 1
        cursor = self.parent
        visited = {self.pk} if self.pk else set()
        while cursor is not None:
            if cursor.pk in visited:
                return self.MAX_DEPTH + 1
            visited.add(cursor.pk)
            depth += 1
            cursor = cursor.parent
        return depth

    @property
    def path_names(self):
        names = [self.name]
        cursor = self.parent
        visited = {self.pk} if self.pk else set()
        while cursor is not None and len(names) <= self.MAX_DEPTH:
            if cursor.pk in visited:
                break
            visited.add(cursor.pk)
            names.append(cursor.name)
            cursor = cursor.parent
        return list(reversed(names))

    @property
    def path_label(self):
        return ' › '.join(self.path_names)

    def __str__(self):
        return f'{self.get_subject_display()}: {self.path_label}'


class TimeLog(EncryptedAtRestMixin, models.Model):
    # 统一枚举值与前端 payload 严格对应
    CATEGORY_CHOICES = SUBJECT_CHOICES
    
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('abandoned', 'Legacy abandoned'),
    ]
    LEARNING_MODE_CHOICES = [
        ('theory', 'Theory'),
        ('exercise', 'Exercise'),
        ('review', 'Review'),
        ('memorization', 'Memorization'),
        ('project', 'Project'),
        ('exam_simulation', 'Exam simulation'),
    ]
    ENERGY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    EFFICIENCY_CHOICES = [
        ('A', 'A · 1.00'),
        ('B', 'B · 0.95'),
        ('C', 'C · 0.90'),
        ('D', 'D · 0.85'),
        ('E', 'E · 0.80'),
        ('F', 'F · 0.75'),
    ]
    EFFICIENCY_COEFFICIENTS = {
        'A': Decimal('1.00'),
        'B': Decimal('0.95'),
        'C': Decimal('0.90'),
        'D': Decimal('0.85'),
        'E': Decimal('0.80'),
        'F': Decimal('0.75'),
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_sessions',
    )
    uuid = models.UUIDField(default=uuid_lib.uuid4, editable=False, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    task_preset = models.ForeignKey(
        TaskPreset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='sessions',
    )
    task_path = models.TextField(blank=True)
    tags = models.ManyToManyField(StudyTag, blank=True, related_name='sessions')
    chapter = models.CharField(max_length=200, blank=True)
    topic = models.CharField(max_length=200, blank=True)
    start_time = models.DateTimeField(default=timezone.now, db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='running')
    efficiency_grade = models.CharField(
        max_length=1,
        choices=EFFICIENCY_CHOICES,
        default='A',
    )
    learning_mode = models.CharField(
        max_length=24,
        choices=LEARNING_MODE_CHOICES,
        blank=True,
    )
    difficulty = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    energy_level = models.CharField(max_length=12, choices=ENERGY_CHOICES, blank=True)
    focus_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    confidence_before = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    confidence_after = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    # Historical notes are preserved verbatim as titles by migration 0010.
    title = models.TextField(null=True, blank=True)
    details = models.TextField(blank=True)
    breakthrough = models.TextField(blank=True)
    problems = models.TextField(blank=True)
    next_action = models.TextField(blank=True)
    encrypted_summary = models.TextField(blank=True, editable=False)
    encrypted_content = models.TextField(blank=True, editable=False)
    review_count = models.PositiveIntegerField(default=0)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    disturbance_count = models.PositiveIntegerField(default=0)
    last_disturbance_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-start_time',)
        indexes = [
            models.Index(fields=('user', 'start_time'), name='session_user_start_idx'),
            models.Index(fields=('user', 'status'), name='session_user_status_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=('user',),
                condition=Q(status='running'),
                name='one_running_session_per_user',
            ),
        ]

    encrypted_field_groups = {
        'encrypted_summary': ('chapter', 'topic', 'title', 'task_path'),
        'encrypted_content': (
            'learning_mode', 'difficulty', 'energy_level', 'focus_level',
            'confidence_before', 'confidence_after', 'details', 'breakthrough',
            'problems', 'next_action',
        ),
    }

    @property
    def duration_minutes(self):
        """计算离散时间差，返回标量分钟数"""
        if self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() / 60)
        return 0

    @property
    def duration_seconds(self):
        if not self.end_time:
            return 0
        return max(0, int((self.end_time - self.start_time).total_seconds()))

    @property
    def efficiency_coefficient(self):
        return float(self.EFFICIENCY_COEFFICIENTS.get(self.efficiency_grade, Decimal('1.00')))

    @property
    def credited_duration_minutes(self):
        """Return whole credited minutes, rounded half up after weighting."""
        weighted = Decimal(max(0, self.duration_minutes)) * self.EFFICIENCY_COEFFICIENTS.get(
            self.efficiency_grade,
            Decimal('1.00'),
        )
        return int(weighted.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    def __str__(self):
        return f"{self.category} | {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}"


class DailyStudyStat(models.Model):
    """Denormalized statistics for completed study logs on one local day."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_study_stats',
    )
    date = models.DateField()
    study_count = models.PositiveIntegerField(default=0)
    first_start_time = models.DateTimeField()
    total_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('-date',)
        constraints = [
            models.UniqueConstraint(fields=('user', 'date'), name='unique_daily_stat_per_user'),
        ]

    @property
    def average_minutes(self):
        if not self.study_count:
            return 0
        return int(self.total_minutes / self.study_count)

    def __str__(self):
        return f"{self.date} | {self.study_count} sessions"


class GitHubNoteSync(EncryptedAtRestMixin, models.Model):
    """Durable outbox entry for one completed session Markdown document."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('synced', 'Synced'),
    ]

    session = models.OneToOneField(
        TimeLog,
        on_delete=models.CASCADE,
        related_name='github_note_sync',
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending', db_index=True)
    markdown_path = models.CharField(max_length=500, blank=True)
    branch = models.CharField(max_length=255, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    encrypted_content = models.TextField(blank=True, editable=False)
    synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('created_at',)

    encrypted_field_groups = {
        'encrypted_content': ('markdown_path', 'last_error'),
    }
    encryption_owner_field = 'session_id'

    def _encryption_user_id(self):
        session = self._state.fields_cache.get('session')
        if session is not None:
            return session.user_id
        session_id = self.__dict__.get('session_id')
        if not session_id:
            return None
        return TimeLog.objects.filter(pk=session_id).values_list('user_id', flat=True).get()


class SessionReview(models.Model):
    """One meaningful review visit for a completed session."""

    session = models.ForeignKey(TimeLog, on_delete=models.CASCADE, related_name='review_events')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='session_reviews',
    )
    reviewed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ('-reviewed_at',)
        indexes = [models.Index(fields=('session', 'reviewed_at'), name='review_session_time_idx')]


class SessionShare(models.Model):
    """Revocable public capability for one otherwise private study session."""

    session = models.ForeignKey(TimeLog, on_delete=models.CASCADE, related_name='shares')
    token_digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=('session',),
                condition=Q(is_active=True),
                name='one_active_share_per_session',
            ),
        ]

    @staticmethod
    def digest(raw_token):
        return hashlib.sha256(raw_token.strip().encode('utf-8')).hexdigest()

    @classmethod
    def issue(cls, *, session, expires_at=None):
        raw_token = f'share_{secrets.token_urlsafe(32)}'
        share = cls.objects.create(
            session=session,
            token_digest=cls.digest(raw_token),
            expires_at=expires_at,
        )
        return share, raw_token

    @property
    def usable(self):
        if not self.is_active or self.revoked_at is not None:
            return False
        return not self.expires_at or self.expires_at > timezone.now()

    def revoke(self):
        if not self.is_active and self.revoked_at is not None:
            return False
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=('is_active', 'revoked_at'))
        return True

    def __str__(self):
        return f'Share for session {self.session_id}'


class InviteCode(models.Model):
    """Hashed, revocable signup capability issued by an administrator."""

    name = models.CharField(max_length=120)
    code_digest = models.CharField(max_length=64, unique=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_invite_codes',
    )
    is_active = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    use_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_self_service = models.BooleanField(default=False, db_index=True)
    issued_local_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(
                check=Q(max_uses__gte=models.F('use_count')),
                name='invite_use_count_lte_max',
            ),
            models.CheckConstraint(
                check=(
                    Q(is_self_service=False)
                    | (Q(max_uses=1) & Q(issued_local_date__isnull=False))
                ),
                name='self_service_invite_single_use',
            ),
            models.UniqueConstraint(
                fields=('created_by', 'issued_local_date'),
                condition=Q(is_self_service=True),
                name='unique_daily_self_service_invite',
            ),
        ]

    @staticmethod
    def digest(raw_code):
        return hashlib.sha256(raw_code.strip().encode('utf-8')).hexdigest()

    @classmethod
    def issue(cls, **fields):
        raw_code = f"invite_{secrets.token_urlsafe(18)}"
        invite = cls.objects.create(code_digest=cls.digest(raw_code), **fields)
        return invite, raw_code

    @property
    def usable(self):
        if not self.is_active or self.use_count >= self.max_uses:
            return False
        return not self.expires_at or self.expires_at > timezone.now()

    @property
    def remaining_uses(self):
        return max(0, self.max_uses - self.use_count)

    def __str__(self):
        return self.name


class InviteRedemption(models.Model):
    invite = models.ForeignKey(InviteCode, on_delete=models.PROTECT, related_name='redemptions')
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='invite_redemption',
    )
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-redeemed_at',)


class SiteConfiguration(models.Model):
    """Singleton instance policy edited from Django Admin."""

    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    registration_open = models.BooleanField(
        default=False,
        help_text='Allow anyone to register without an invite code.',
    )
    math_visualization_enabled = models.BooleanField(
        default=False,
        help_text='Show Markdown formula launch buttons and enable the visualization window.',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site configuration'
        verbose_name_plural = 'Site configuration'

    @classmethod
    def load(cls):
        configuration, _ = cls.objects.get_or_create(singleton_key=1)
        return configuration

    @classmethod
    def registration_is_open(cls):
        return cls.objects.filter(singleton_key=1, registration_open=True).exists()

    @classmethod
    def math_visualization_is_enabled(cls):
        return cls.objects.filter(singleton_key=1, math_visualization_enabled=True).exists()

    def __str__(self):
        return 'Registration policy'


class UserDataEncryptionPreference(models.Model):
    """Per-user opt-in for transparent server-managed encryption at rest."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='data_encryption_preference',
    )
    enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'user data encryption preference'
        verbose_name_plural = 'user data encryption preferences'

    def __str__(self):
        return f'{self.user} | {"encrypted" if self.enabled else "plaintext"}'


class LearningIssue(EncryptedAtRestMixin, models.Model):
    ISSUE_TYPE_CHOICES = [
        ('concept_error', 'Concept error'),
        ('calculation_error', 'Calculation error'),
        ('recognition_error', 'Recognition error'),
        ('memory_error', 'Memory error'),
        ('speed_problem', 'Speed problem'),
        ('careless_error', 'Careless error'),
        ('strategy_problem', 'Strategy problem'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='learning_issues')
    category = models.CharField(max_length=20, choices=TimeLog.CATEGORY_CHOICES)
    topic = models.CharField(max_length=200, blank=True)
    study_session = models.ForeignKey(
        TimeLog,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='issues',
    )
    issue_type = models.CharField(max_length=24, choices=ISSUE_TYPE_CHOICES)
    description = models.TextField()
    solution = models.TextField(blank=True)
    encrypted_content = models.TextField(blank=True, editable=False)
    resolved = models.BooleanField(default=False)
    repeat_count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=('user', 'resolved'), name='issue_user_resolved_idx')]

    encrypted_field_groups = {
        'encrypted_content': ('topic', 'issue_type', 'description', 'solution'),
    }


class KnowledgePoint(models.Model):
    STATUS_CHOICES = [
        ('unknown', 'Unknown'),
        ('learning', 'Learning'),
        ('understood', 'Understood'),
        ('stable', 'Stable'),
        ('automatic', 'Automatic'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='knowledge_points')
    category = models.CharField(max_length=20, choices=TimeLog.CATEGORY_CHOICES)
    name = models.CharField(max_length=200)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    importance = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    mastery_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='unknown')
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    review_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('category', 'name')
        indexes = [models.Index(fields=('user', 'category'), name='knowledge_user_cat_idx')]


class LaunchToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='launch_tokens')
    name = models.CharField(max_length=120)
    token_digest = models.CharField(max_length=64, unique=True, db_index=True)
    disturbance_token_digest = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )
    category = models.CharField(max_length=20, choices=TimeLog.CATEGORY_CHOICES)
    is_active = models.BooleanField(default=True)
    is_paused = models.BooleanField(default=False)
    available_from = models.TimeField(default=datetime.time(6, 0))
    available_until = models.TimeField(default=datetime.time(22, 0))
    expires_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    source_label = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=('user', 'is_active'), name='token_user_active_idx')]

    @staticmethod
    def digest(raw_token):
        return hashlib.sha256(raw_token.encode('ascii')).hexdigest()

    @classmethod
    def issue(cls, **fields):
        raw_token = secrets.token_urlsafe(32)
        token = cls.objects.create(token_digest=cls.digest(raw_token), **fields)
        return token, raw_token

    @classmethod
    def issue_with_disturbance(cls, **fields):
        raw_token = secrets.token_urlsafe(32)
        disturbance_token = secrets.token_urlsafe(32)
        token = cls.objects.create(
            token_digest=cls.digest(raw_token),
            disturbance_token_digest=cls.digest(disturbance_token),
            **fields,
        )
        return token, raw_token, disturbance_token

    @property
    def credential_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True

    def schedule_allows(self, at=None):
        local_time = timezone.localtime(at or timezone.now()).time().replace(tzinfo=None)
        if self.available_from == self.available_until:
            return True
        if self.available_from < self.available_until:
            return self.available_from <= local_time < self.available_until
        return local_time >= self.available_from or local_time < self.available_until

    @property
    def within_schedule(self):
        return self.schedule_allows()

    @property
    def has_disturbance_uri(self):
        return bool(self.disturbance_token_digest)

    @property
    def usable(self):
        if not self.credential_valid or self.is_paused or not self.within_schedule:
            return False
        if self.max_uses is not None and self.usage_count >= self.max_uses:
            return False
        return True
