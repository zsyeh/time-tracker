import hashlib
import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TimeLog(models.Model):
    # 统一枚举值与前端 payload 严格对应
    CATEGORY_CHOICES = [
        ('math', 'Mathematics'),
        ('english', 'English'),
        ('major', 'Major'),
        ('training', 'Training'),
    ]
    
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

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='study_sessions',
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    chapter = models.CharField(max_length=200, blank=True)
    topic = models.CharField(max_length=200, blank=True)
    start_time = models.DateTimeField(default=timezone.now, db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='running')
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
    review_count = models.PositiveIntegerField(default=0)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
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


class GitHubNoteSync(models.Model):
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
    synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('created_at',)


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


class LearningIssue(models.Model):
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
    resolved = models.BooleanField(default=False)
    repeat_count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=('user', 'resolved'), name='issue_user_resolved_idx')]


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
    category = models.CharField(max_length=20, choices=TimeLog.CATEGORY_CHOICES)
    is_active = models.BooleanField(default=True)
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

    @property
    def usable(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        if self.max_uses is not None and self.usage_count >= self.max_uses:
            return False
        return True
