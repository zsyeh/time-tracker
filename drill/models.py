import uuid as uuid_lib

from django.conf import settings
from django.db import models
from django.utils import timezone


class QuestionDocument(models.Model):
    """One imported source book. Its content is shared by every account."""

    source_id = models.PositiveBigIntegerField(unique=True)
    filename = models.TextField()
    title = models.CharField(max_length=240)
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
    prompt_text = models.TextField(blank=True)
    latex_text = models.TextField(blank=True)
    content_mode = models.CharField(max_length=12)
    fingerprint = models.CharField(max_length=64, unique=True)
    confidence = models.FloatField(default=1.0)
    is_past_exam = models.BooleanField(default=False, db_index=True)
    exam_year = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    exam_variant = models.CharField(max_length=16, blank=True)

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
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='question_attempts',
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='attempts')
    result = models.CharField(max_length=12, choices=RESULT_CHOICES, default='done')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('user', 'question'), name='drill_attempt_user_q_idx'),
            models.Index(fields=('user', 'created_at'), name='drill_attempt_user_time_idx'),
        ]

    def __str__(self):
        return f'{self.user_id} · {self.question_id} · {self.result}'

