from django.contrib import admin

from .models import (
    Question,
    QuestionAsset,
    QuestionAttempt,
    QuestionDocument,
    QuestionTopic,
)


@admin.register(QuestionDocument)
class QuestionDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'page_count', 'parser_strategy', 'imported_at')
    search_fields = ('title', 'filename', 'sha256')


@admin.register(QuestionTopic)
class QuestionTopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'document', 'level', 'sort_order')
    list_filter = ('document', 'level')
    search_fields = ('title', 'normalized_title')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        'source_label', 'document', 'question_order', 'is_past_exam',
        'exam_year', 'content_mode',
    )
    list_filter = ('document', 'is_past_exam', 'exam_year', 'content_mode')
    search_fields = ('source_label', 'prompt_text', 'fingerprint')
    readonly_fields = ('uuid', 'fingerprint')


@admin.register(QuestionAttempt)
class QuestionAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'result', 'created_at')
    list_filter = ('result', 'created_at')
    search_fields = ('user__username', 'question__source_label')


@admin.register(QuestionAsset)
class QuestionAssetAdmin(admin.ModelAdmin):
    list_display = ('source_id', 'question', 'position', 'width', 'height', 'mime_type')
    fields = ('source_id', 'question', 'position', 'asset_type', 'sha256', 'mime_type', 'width', 'height')
    readonly_fields = fields
