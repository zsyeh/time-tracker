from django.contrib import admin

from .models import (
    Question,
    QuestionAsset,
    QuestionAttempt,
    QuestionDocument,
    QuestionMarker,
    QuestionTopic,
    QuestionUserState,
)


@admin.register(QuestionDocument)
class QuestionDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'workspace', 'display_title', 'title', 'author', 'page_count', 'parser_strategy', 'imported_at',
    )
    list_filter = ('workspace',)
    search_fields = ('display_title', 'title', 'author', 'attribution', 'filename', 'sha256')


@admin.register(QuestionTopic)
class QuestionTopicAdmin(admin.ModelAdmin):
    list_display = ('display_title', 'title', 'document', 'level', 'sort_order')
    list_filter = ('document', 'level')
    search_fields = ('display_title', 'title', 'normalized_title')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        'display_label', 'document', 'question_order', 'source_category',
        'record_kind', 'is_practiceable', 'exam_year', 'content_mode', 'answer_source',
    )
    list_filter = (
        'document', 'source_category', 'record_kind', 'is_practiceable',
        'is_past_exam', 'exam_year', 'content_mode',
    )
    search_fields = (
        'display_label', 'source_label', 'prompt_text', 'answer_markdown', 'fingerprint',
    )
    readonly_fields = (
        'uuid', 'fingerprint', 'answer_generated_at',
        'topic_classification_source', 'topic_classification_confidence',
    )


@admin.register(QuestionAttempt)
class QuestionAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'result', 'created_at')
    list_filter = ('result', 'created_at')
    search_fields = ('user__username', 'question__source_label')


@admin.register(QuestionUserState)
class QuestionUserStateAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'is_favorite', 'review_later', 'updated_at')
    list_filter = ('is_favorite', 'review_later', 'updated_at')
    search_fields = ('user__username', 'question__source_label', 'note')


@admin.register(QuestionMarker)
class QuestionMarkerAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'code', 'created_at')
    list_filter = ('code', 'created_at')
    search_fields = ('user__username', 'question__source_label')


@admin.register(QuestionAsset)
class QuestionAssetAdmin(admin.ModelAdmin):
    list_display = (
        'source_id', 'question', 'position', 'width', 'height', 'render_dpi', 'mime_type',
    )
    fields = (
        'source_id', 'question', 'position', 'asset_type', 'sha256', 'mime_type',
        'width', 'height', 'render_dpi', 'source_page_index',
        'source_x0', 'source_y0', 'source_x1', 'source_y1',
    )
    readonly_fields = fields
