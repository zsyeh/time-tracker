import hashlib
import secrets
import uuid as uuid_lib

import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone


class QuestionDocument(models.Model):
    """One imported source book. Its content is shared by every account."""

    source_id = models.PositiveBigIntegerField(unique=True)
    filename = models.TextField()
    title = models.CharField(max_length=240)
    display_title = models.CharField(max_length=240, blank=True)
    author = models.CharField(max_length=240, blank=True)
    attribution = models.CharField(max_length=500, blank=True)
    sha256 = models.CharField(max_length=64, unique=True)
    page_count = models.PositiveIntegerField()
    parser_strategy = models.CharField(max_length=64, blank=True)
    relation_type = models.CharField(max_length=32, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('source_id',)

    def __str__(self):
        return self.title


class QuestionTopic(models.Model):
    """Imported knowledge hierarchy used to select comparable questions."""

    source_id = models.PositiveBigIntegerField(unique=True)
    document = models.ForeignKey(
        QuestionDocument,
        on_delete=models.CASCADE,
        related_name='topics',
    )
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children',
    )
    title = models.TextField()
    display_title = models.TextField(blank=True)
    normalized_title = models.TextField(blank=True)
    level = models.PositiveSmallIntegerField()
    sort_order = models.PositiveIntegerField()

    class Meta:
        ordering = ('document_id', 'sort_order')
        constraints = [
            models.UniqueConstraint(
                fields=('document', 'sort_order'),
                name='drill_topic_document_order_unique',
            ),
        ]
        indexes = [
            models.Index(fields=('document', 'parent'), name='drill_topic_parent_idx'),
        ]

    def __str__(self):
        return self.title


class Question(models.Model):
    """Stable canonical question imported from the supplied question bank."""

    SOURCE_CATEGORY_CHOICES = [
        ('past_exam', 'Past exam'),
        ('adapted_exam', 'Adapted past exam'),
        ('mock_exam', 'Mock paper'),
        ('workbook', 'Workbook'),
        ('competition', 'Competition'),
        ('other_practice', 'Other practice'),
        ('unclassified', 'Unclassified'),
    ]
    RECORD_KIND_CHOICES = [
        ('question', 'Question'),
        ('grouped', 'Grouped extract'),
        ('section', 'Source outline'),
    ]

    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)
    document = models.ForeignKey(
        QuestionDocument,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    topic = models.ForeignKey(
        QuestionTopic,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='questions',
    )
    similarity_topic = models.ForeignKey(
        QuestionTopic,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='similar_questions',
    )
    question_order = models.PositiveIntegerField()
    source_label = models.TextField(blank=True)
    display_label = models.TextField(blank=True)
    prompt_text = models.TextField(blank=True)
    latex_text = models.TextField(blank=True)
    content_mode = models.CharField(max_length=12)
    fingerprint = models.CharField(max_length=64, unique=True)
    confidence = models.FloatField(default=1.0)
    is_past_exam = models.BooleanField(default=False, db_index=True)
    source_category = models.CharField(
        max_length=20,
        choices=SOURCE_CATEGORY_CHOICES,
        default='unclassified',
        db_index=True,
    )
    record_kind = models.CharField(
        max_length=12,
        choices=RECORD_KIND_CHOICES,
        default='question',
        db_index=True,
    )
    is_practiceable = models.BooleanField(default=True, db_index=True)
    classification_reason = models.CharField(max_length=200, blank=True)
    classification_confidence = models.FloatField(default=0.0)
    exam_year = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    exam_variant = models.CharField(max_length=16, blank=True)
    answer_markdown = models.TextField(blank=True)
    answer_source = models.CharField(max_length=32, blank=True)
    answer_confidence = models.FloatField(null=True, blank=True)
    answer_generated_at = models.DateTimeField(null=True, blank=True)
    topic_classification_source = models.CharField(max_length=32, blank=True)
    topic_classification_confidence = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ('document_id', 'question_order')
        constraints = [
            models.UniqueConstraint(
                fields=('document', 'question_order'),
                name='drill_question_document_order_unique',
            ),
        ]
        indexes = [
            models.Index(fields=('document', 'question_order'), name='drill_question_order_idx'),
            models.Index(fields=('similarity_topic', 'question_order'), name='drill_question_similar_idx'),
        ]

    def __str__(self):
        return self.source_label or f'{self.document.title} #{self.question_order}'


class QuestionAsset(models.Model):
    """A lossless PNG crop stored in PostgreSQL with the question metadata."""

    source_id = models.PositiveBigIntegerField(unique=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='assets')
    position = models.PositiveSmallIntegerField(default=0)
    asset_type = models.CharField(max_length=24, default='question_crop')
    sha256 = models.CharField(max_length=64)
    mime_type = models.CharField(max_length=64, default='image/png')
    image_data = models.BinaryField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    source_page_index = models.PositiveIntegerField(null=True, blank=True)
    source_x0 = models.FloatField(null=True, blank=True)
    source_y0 = models.FloatField(null=True, blank=True)
    source_x1 = models.FloatField(null=True, blank=True)
    source_y1 = models.FloatField(null=True, blank=True)
    render_dpi = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ('position', 'source_id')
        constraints = [
            models.UniqueConstraint(
                fields=('question', 'sha256'),
                name='drill_question_asset_hash_unique',
            ),
        ]
        indexes = [models.Index(fields=('question', 'position'), name='drill_asset_order_idx')]

    def __str__(self):
        return f'Asset {self.source_id} for {self.question_id}'


class QuestionAttempt(models.Model):
    RESULT_CHOICES = [
        ('done', 'Done'),
        ('correct', 'Correct'),
        ('review', 'Needs review'),
        ('reset', 'Reset to unattempted'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='question_attempts',
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='attempts')
    result = models.CharField(max_length=12, choices=RESULT_CHOICES, default='done')
    confidence = models.PositiveSmallIntegerField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('user', 'question'), name='drill_attempt_user_q_idx'),
            models.Index(fields=('user', 'created_at'), name='drill_attempt_user_time_idx'),
        ]

    def __str__(self):
        return f'{self.user_id} · {self.question_id} · {self.result}'


class QuestionUserState(models.Model):
    """Small, private per-user state that does not create an attempt."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='question_user_states',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='user_states',
    )
    note = models.TextField(blank=True)
    is_favorite = models.BooleanField(default=False, db_index=True)
    review_later = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'question'),
                name='drill_user_question_state_unique',
            ),
        ]
        indexes = [
            models.Index(fields=('user', 'is_favorite'), name='drill_state_favorite_idx'),
            models.Index(fields=('user', 'review_later'), name='drill_state_review_idx'),
        ]

    def __str__(self):
        return f'{self.user_id} · {self.question_id} · saved state'


class QuestionMarker(models.Model):
    """Independent, combinable learning signals attached by one user."""

    MARKER_CHOICES = [
        ('overconfident', 'Overconfident'),
        ('concept_gap', 'Concept Gap'),
        ('rusty', 'Rusty'),
        ('forgotten', 'Forgotten'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='question_markers',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='markers',
    )
    code = models.CharField(max_length=24, choices=MARKER_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'question', 'code'),
                name='drill_user_question_marker_unique',
            ),
        ]
        indexes = [
            models.Index(fields=('user', 'code'), name='drill_marker_user_code_idx'),
            models.Index(fields=('user', 'question'), name='drill_marker_user_q_idx'),
        ]

    def __str__(self):
        return f'{self.user_id} · {self.question_id} · {self.code}'


class DrillLoginHandoff(models.Model):
    """Short-lived, one-time authentication handoff from Timer to Drill."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='+',
    )
    token_digest = models.CharField(max_length=64, unique=True, db_index=True)
    target_path = models.CharField(max_length=500, default='/practice')
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    @staticmethod
    def digest(raw_token):
        return hashlib.sha256(raw_token.encode('ascii')).hexdigest()

    @classmethod
    def issue(cls, *, user, target_path, lifetime_seconds=90):
        now = timezone.now()
        cls.objects.filter(expires_at__lte=now).delete()
        raw_token = f'drill_{secrets.token_urlsafe(32)}'
        handoff = cls.objects.create(
            user=user,
            token_digest=cls.digest(raw_token),
            target_path=target_path,
            expires_at=now + datetime.timedelta(seconds=lifetime_seconds),
        )
        return handoff, raw_token
