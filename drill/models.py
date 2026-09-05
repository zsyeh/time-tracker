import hashlib
import json
import secrets
import uuid as uuid_lib

import datetime

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class QuestionDocument(models.Model):
    """One imported source book. Its content is shared by every account."""

    WORKSPACE_CHOICES = [
        ('drill', 'Mathematics drill'),
        ('ei', 'Electronic information'),
    ]

    source_id = models.PositiveBigIntegerField(unique=True)
    workspace = models.CharField(
        max_length=16,
        choices=WORKSPACE_CHOICES,
        default='drill',
        db_index=True,
    )
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
    SUBJECT_CHOICES = [
        ('math2', 'Mathematics II'),
        ('ei', 'Electronic information'),
        ('other', 'Other'),
    ]
    QUESTION_TYPE_CHOICES = [
        ('unknown', 'Unclassified'),
        ('single_choice', 'Single choice'),
        ('fill_blank', 'Fill in the blank'),
        ('solution', 'Solution'),
    ]
    QUESTION_TYPE_SOURCE_CHOICES = [
        ('', 'Not classified'),
        ('rule', 'Rule-assisted batch'),
        ('agent', 'Agent batch'),
        ('human', 'Human verified'),
        ('import', 'Source metadata'),
    ]

    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)
    subject = models.CharField(
        max_length=16,
        choices=SUBJECT_CHOICES,
        blank=True,
        default='',
        db_index=True,
    )
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
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        default='unknown',
        db_index=True,
    )
    question_type_source = models.CharField(
        max_length=12,
        choices=QUESTION_TYPE_SOURCE_CHOICES,
        blank=True,
        default='',
    )
    question_type_confidence = models.FloatField(null=True, blank=True)
    question_type_human_verified = models.BooleanField(default=False, db_index=True)
    difficulty = models.PositiveSmallIntegerField(null=True, blank=True)
    estimated_time_minutes = models.PositiveSmallIntegerField(null=True, blank=True)

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

    def save(self, *args, **kwargs):
        if not self.subject and self.document_id:
            workspace = self.document.workspace if 'document' in self._state.fields_cache else (
                QuestionDocument.objects.only('workspace').get(pk=self.document_id).workspace
            )
            self.subject = 'math2' if workspace == 'drill' else 'ei'
        super().save(*args, **kwargs)


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


class QuestionRevision(models.Model):
    """Lightweight immutable snapshot used by persisted exam papers.

    Text fields are snapshotted once. Binary crops remain deduplicated in
    ``QuestionAsset`` and are pinned through protected revision references.
    """

    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name='revisions',
    )
    number = models.PositiveIntegerField()
    content_hash = models.CharField(max_length=64)
    document_title = models.CharField(max_length=240)
    topic_title = models.TextField(blank=True)
    source_label = models.TextField(blank=True)
    display_label = models.TextField(blank=True)
    prompt_text = models.TextField(blank=True)
    latex_text = models.TextField(blank=True)
    content_mode = models.CharField(max_length=12)
    question_type = models.CharField(max_length=20, choices=Question.QUESTION_TYPE_CHOICES)
    source_category = models.CharField(max_length=20, choices=Question.SOURCE_CATEGORY_CHOICES)
    exam_year = models.PositiveSmallIntegerField(null=True, blank=True)
    exam_variant = models.CharField(max_length=16, blank=True)
    difficulty = models.PositiveSmallIntegerField(null=True, blank=True)
    estimated_time_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    answer_markdown = models.TextField(blank=True)
    answer_source = models.CharField(max_length=32, blank=True)
    answer_confidence = models.FloatField(null=True, blank=True)
    assets = models.ManyToManyField(
        QuestionAsset, through='QuestionRevisionAsset', related_name='question_revisions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('question_id', '-number')
        constraints = [
            models.UniqueConstraint(
                fields=('question', 'number'), name='drill_revision_question_number_unique',
            ),
            models.UniqueConstraint(
                fields=('question', 'content_hash'), name='drill_revision_question_hash_unique',
            ),
        ]
        indexes = [models.Index(fields=('question', '-number'), name='drill_revision_latest_idx')]

    def __str__(self):
        return f'{self.question_id} · revision {self.number}'

    @classmethod
    def capture(cls, question):
        """Return the matching immutable revision, creating it atomically."""
        with transaction.atomic():
            # Keep nullable topic joins out of the FOR UPDATE statement:
            # PostgreSQL rejects row locks on the nullable side of an outer join.
            locked = Question.objects.select_for_update().get(pk=question.pk)
            assets = list(locked.assets.order_by('asset_type', 'position', 'pk'))
            topic = locked.similarity_topic or locked.topic
            values = {
                'document_title': locked.document.display_title or locked.document.title,
                'topic_title': (topic.display_title or topic.title) if topic else '',
                'source_label': locked.source_label,
                'display_label': locked.display_label,
                'prompt_text': locked.prompt_text,
                'latex_text': locked.latex_text,
                'content_mode': locked.content_mode,
                'question_type': locked.question_type,
                'source_category': locked.source_category,
                'exam_year': locked.exam_year,
                'exam_variant': locked.exam_variant,
                'difficulty': locked.difficulty,
                'estimated_time_minutes': locked.estimated_time_minutes,
                'answer_markdown': locked.answer_markdown,
                'answer_source': locked.answer_source,
                'answer_confidence': locked.answer_confidence,
            }
            digest_payload = {
                **values,
                'assets': [
                    [asset.pk, asset.sha256, asset.asset_type, asset.position]
                    for asset in assets
                ],
            }
            content_hash = hashlib.sha256(json.dumps(
                digest_payload, ensure_ascii=False, sort_keys=True,
                separators=(',', ':'), default=str,
            ).encode('utf-8')).hexdigest()
            existing = cls.objects.filter(
                question=locked, content_hash=content_hash,
            ).first()
            if existing:
                return existing
            latest_number = cls.objects.filter(question=locked).aggregate(
                models.Max('number'),
            )['number__max'] or 0
            revision = cls.objects.create(
                question=locked, number=latest_number + 1,
                content_hash=content_hash, **values,
            )
            QuestionRevisionAsset.objects.bulk_create([
                QuestionRevisionAsset(
                    revision=revision, asset=asset,
                    position=asset.position, asset_type=asset.asset_type,
                )
                for asset in assets
            ])
            return revision


class QuestionRevisionAsset(models.Model):
    revision = models.ForeignKey(
        QuestionRevision, on_delete=models.CASCADE, related_name='revision_assets',
    )
    asset = models.ForeignKey(
        QuestionAsset, on_delete=models.PROTECT, related_name='revision_links',
    )
    position = models.PositiveSmallIntegerField()
    asset_type = models.CharField(max_length=24)

    class Meta:
        ordering = ('revision_id', 'asset_type', 'position', 'pk')
        constraints = [
            models.UniqueConstraint(
                fields=('revision', 'asset'), name='drill_revision_asset_unique',
            ),
        ]

    def __str__(self):
        return f'{self.revision_id} · {self.asset_type} · {self.position}'


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


class ExamBlueprint(models.Model):
    """Immutable-by-convention, versioned composition rules for one paper mode."""

    MODE_CHOICES = [
        ('standard', 'Standard mock'),
        ('intensive', 'Intensive'),
        ('weak', 'Weak-point training'),
    ]

    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)
    code = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=160)
    subject = models.CharField(max_length=16, choices=Question.SUBJECT_CHOICES, db_index=True)
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, db_index=True)
    version = models.PositiveSmallIntegerField(default=1)
    duration_minutes = models.PositiveSmallIntegerField()
    total_score = models.PositiveSmallIntegerField()
    cooldown_days = models.PositiveSmallIntegerField(default=14)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('subject', 'mode', '-version')
        constraints = [
            models.UniqueConstraint(
                fields=('subject', 'mode', 'version'),
                name='drill_blueprint_subject_mode_version_unique',
            ),
        ]

    def __str__(self):
        return f'{self.title} v{self.version}'


class ExamBlueprintSection(models.Model):
    blueprint = models.ForeignKey(
        ExamBlueprint,
        on_delete=models.CASCADE,
        related_name='sections',
    )
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=120)
    question_type = models.CharField(max_length=20, choices=Question.QUESTION_TYPE_CHOICES)
    question_count = models.PositiveSmallIntegerField()
    score_per_question = models.DecimalField(max_digits=5, decimal_places=2)
    chapter_weights = models.JSONField(default=dict, blank=True)
    difficulty_weights = models.JSONField(default=dict, blank=True)
    max_per_topic = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ('blueprint_id', 'order')
        constraints = [
            models.UniqueConstraint(
                fields=('blueprint', 'order'),
                name='drill_blueprint_section_order_unique',
            ),
        ]

    def __str__(self):
        return f'{self.blueprint.code} · {self.title}'


class ExamPaper(models.Model):
    STATUS_CHOICES = [
        ('generated', 'Generated'),
        ('in_progress', 'In progress'),
        ('completed', 'Completed'),
    ]

    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_papers',
    )
    blueprint = models.ForeignKey(
        ExamBlueprint,
        on_delete=models.PROTECT,
        related_name='papers',
    )
    seed = models.PositiveBigIntegerField()
    mode = models.CharField(max_length=16, choices=ExamBlueprint.MODE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='generated', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        indexes = [models.Index(fields=('user', 'created_at'), name='drill_paper_user_time_idx')]

    def __str__(self):
        return f'{self.user_id} · {self.blueprint.code} · {self.uuid}'


class ExamPaperItem(models.Model):
    RESULT_CHOICES = [
        ('unanswered', 'Unanswered'),
        ('correct', 'Correct'),
        ('incorrect', 'Incorrect'),
        ('review', 'Needs review'),
    ]

    paper = models.ForeignKey(ExamPaper, on_delete=models.CASCADE, related_name='items')
    section = models.ForeignKey(ExamBlueprintSection, on_delete=models.PROTECT, related_name='+')
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name='paper_items')
    question_revision = models.ForeignKey(
        QuestionRevision, on_delete=models.PROTECT, related_name='paper_items',
    )
    position = models.PositiveSmallIntegerField()
    score = models.DecimalField(max_digits=5, decimal_places=2)
    selected_fingerprint = models.CharField(max_length=64)
    user_answer = models.TextField(blank=True)
    result = models.CharField(max_length=16, choices=RESULT_CHOICES, default='unanswered', db_index=True)
    time_spent_seconds = models.PositiveIntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('paper_id', 'position')
        constraints = [
            models.UniqueConstraint(fields=('paper', 'position'), name='drill_paper_item_position_unique'),
            models.UniqueConstraint(fields=('paper', 'question'), name='drill_paper_item_question_unique'),
        ]
        indexes = [models.Index(fields=('paper', 'position'), name='drill_paper_item_order_idx')]

    def __str__(self):
        return f'{self.paper_id} · {self.position} · {self.question_id}'


class DrillLoginHandoff(models.Model):
    """Short-lived, one-time authentication handoff from Timer to Drill."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='+',
    )
    token_digest = models.CharField(max_length=64, unique=True, db_index=True)
    target_path = models.CharField(max_length=500, default='/practice')
    target_site = models.CharField(
        max_length=16,
        choices=QuestionDocument.WORKSPACE_CHOICES,
        default='drill',
    )
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    @staticmethod
    def digest(raw_token):
        return hashlib.sha256(raw_token.encode('ascii')).hexdigest()

    @classmethod
    def issue(cls, *, user, target_path, target_site='drill', lifetime_seconds=90):
        now = timezone.now()
        cls.objects.filter(expires_at__lte=now).delete()
        raw_token = f'drill_{secrets.token_urlsafe(32)}'
        handoff = cls.objects.create(
            user=user,
            token_digest=cls.digest(raw_token),
            target_path=target_path,
            target_site=target_site,
            expires_at=now + datetime.timedelta(seconds=lifetime_seconds),
        )
        return handoff, raw_token
