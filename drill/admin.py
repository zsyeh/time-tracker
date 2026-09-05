from django.contrib import admin

from .models import (
    ExamBlueprint,
    ExamBlueprintSection,
    ExamPaper,
    ExamPaperItem,
    Question,
    QuestionAsset,
    QuestionAttempt,
    QuestionDocument,
    QuestionMarker,
    QuestionRevision,
    QuestionRevisionAsset,
    QuestionTopic,
    QuestionUserState,
)


class QuestionTypeConfidenceFilter(admin.SimpleListFilter):
    title = 'question type confidence'
    parameter_name = 'question_type_confidence_band'

    def lookups(self, request, model_admin):
        return (
            ('low', 'Low confidence (< 0.75)'),
            ('strong', 'Strong evidence (≥ 0.85)'),
            ('unclassified', 'No classification'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(
                question_type_confidence__lt=0.75,
                question_type_human_verified=False,
            )
        if self.value() == 'strong':
            return queryset.filter(question_type_confidence__gte=0.85)
        if self.value() == 'unclassified':
            return queryset.filter(question_type='unknown')
        return queryset


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
        'record_kind', 'question_type', 'question_type_source',
        'question_type_confidence', 'question_type_human_verified',
        'is_practiceable', 'exam_year', 'content_mode', 'answer_source',
    )
    list_filter = (
        'document', 'subject', 'source_category', 'record_kind', 'question_type',
        'question_type_source', QuestionTypeConfidenceFilter,
        'question_type_human_verified', 'is_practiceable',
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


class QuestionRevisionAssetInline(admin.TabularInline):
    model = QuestionRevisionAsset
    extra = 0
    can_delete = False
    readonly_fields = ('asset', 'asset_type', 'position')


@admin.register(QuestionRevision)
class QuestionRevisionAdmin(admin.ModelAdmin):
    list_display = ('question', 'number', 'question_type', 'document_title', 'created_at')
    list_filter = ('question_type', 'source_category', 'created_at')
    search_fields = ('question__uuid', 'source_label', 'display_label', 'content_hash')
    readonly_fields = tuple(
        field.name for field in QuestionRevision._meta.fields
    )
    inlines = (QuestionRevisionAssetInline,)


class ExamBlueprintSectionInline(admin.TabularInline):
    model = ExamBlueprintSection
    extra = 0


@admin.register(ExamBlueprint)
class ExamBlueprintAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'mode', 'version', 'duration_minutes', 'total_score', 'is_active')
    list_filter = ('subject', 'mode', 'is_active')
    search_fields = ('title', 'code')
    readonly_fields = ('uuid', 'created_at')
    inlines = (ExamBlueprintSectionInline,)


class ExamPaperItemInline(admin.TabularInline):
    model = ExamPaperItem
    extra = 0
    readonly_fields = (
        'section', 'question', 'question_revision', 'position', 'score', 'selected_fingerprint',
    )


@admin.register(ExamPaper)
class ExamPaperAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'user', 'blueprint', 'mode', 'status', 'created_at', 'completed_at')
    list_filter = ('mode', 'status', 'created_at')
    search_fields = ('uuid', 'user__username', 'blueprint__title')
    readonly_fields = ('uuid', 'seed', 'created_at')
    inlines = (ExamPaperItemInline,)
