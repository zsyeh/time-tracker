import datetime

from django.utils import timezone
from rest_framework import serializers

from .models import ExamBlueprint, Question, QuestionAttempt, QuestionAttemptError, QuestionMarker
from .ei_selected_pdf_pages import pdf_pages_for
from .notes import MAX_QUESTION_NOTE_LENGTH


class QuestionSummarySerializer(serializers.ModelSerializer):
    document = serializers.SerializerMethodField()
    topic = serializers.SerializerMethodField()
    source_category_label = serializers.CharField(source='get_source_category_display', read_only=True)
    state = serializers.SerializerMethodField()
    can_undo = serializers.SerializerMethodField()
    attempt_count = serializers.IntegerField(read_only=True, default=0)
    latest_result = serializers.CharField(read_only=True, allow_null=True, default=None)
    is_favorite = serializers.BooleanField(read_only=True, default=False)
    review_later = serializers.BooleanField(read_only=True, default=False)
    saved_note = serializers.CharField(read_only=True, allow_blank=True, allow_null=True, default='')
    review_overdue = serializers.SerializerMethodField()
    pdf_pages = serializers.SerializerMethodField()

    def get_pdf_pages(self, obj):
        return pdf_pages_for(obj)

    def get_document(self, obj):
        return obj.document.display_title or obj.document.title

    def get_topic(self, obj):
        topic = obj.similarity_topic
        return (topic.display_title or topic.title) if topic else ''

    def get_state(self, obj):
        if obj.latest_result == 'review':
            return 'review'
        if obj.latest_result in {'done', 'correct'}:
            return 'mastered'
        return 'unattempted'

    def get_can_undo(self, obj):
        return bool(getattr(obj, 'state_change_count', 0))

    def get_review_overdue(self, obj):
        attempted_at = getattr(obj, 'latest_attempted_at', None)
        return bool(
            obj.latest_result == 'review'
            and attempted_at
            and attempted_at <= timezone.now() - datetime.timedelta(days=5)
        )

    class Meta:
        model = Question
        fields = (
            'uuid', 'document', 'question_order', 'source_label', 'display_label',
            'topic', 'is_past_exam', 'source_category', 'source_category_label',
            'record_kind', 'exam_year', 'exam_variant', 'attempt_count',
            'latest_result', 'state', 'can_undo',
            'is_favorite', 'review_later', 'saved_note', 'review_overdue', 'pdf_pages',
        )


class QuestionAttemptCreateSerializer(serializers.Serializer):
    result = serializers.ChoiceField(
        choices=[choice[0] for choice in QuestionAttempt.RESULT_CHOICES],
        default='correct',
    )
    confidence = serializers.IntegerField(min_value=0, max_value=100, required=False, allow_null=True)
    note = serializers.CharField(max_length=MAX_QUESTION_NOTE_LENGTH, required=False, allow_blank=True, allow_null=True)
    time_spent_seconds = serializers.IntegerField(
        min_value=1, max_value=43200, required=False, allow_null=True,
    )
    outcome = serializers.ChoiceField(
        choices=[choice[0] for choice in QuestionAttempt.OUTCOME_CHOICES], required=False,
    )
    knowledge_level = serializers.ChoiceField(
        choices=[choice[0] for choice in QuestionAttempt.KNOWLEDGE_CHOICES], required=False, allow_null=True,
    )
    method_level = serializers.ChoiceField(
        choices=[choice[0] for choice in QuestionAttempt.METHOD_CHOICES], required=False, allow_null=True,
    )
    execution_level = serializers.ChoiceField(
        choices=[choice[0] for choice in QuestionAttempt.EXECUTION_CHOICES], required=False, allow_null=True,
    )
    used_hint = serializers.BooleanField(required=False, allow_null=True)
    viewed_answer = serializers.BooleanField(required=False, allow_null=True)
    is_independent = serializers.BooleanField(required=False, allow_null=True)
    judgement_source = serializers.ChoiceField(
        choices=[choice[0] for choice in QuestionAttempt.JUDGEMENT_CHOICES], required=False,
    )
    # Accepted for older clients only. New free text is stored exclusively in
    # QuestionUserState.note by the view.
    correction_note = serializers.CharField(max_length=MAX_QUESTION_NOTE_LENGTH, required=False, allow_blank=True)
    knowledge_note = serializers.CharField(max_length=MAX_QUESTION_NOTE_LENGTH, required=False, allow_blank=True)
    first_step_note = serializers.CharField(max_length=MAX_QUESTION_NOTE_LENGTH, required=False, allow_blank=True)
    error_codes = serializers.ListField(
        child=serializers.ChoiceField(choices=[choice[0] for choice in QuestionAttemptError.ERROR_CHOICES]),
        required=False, allow_empty=True, max_length=len(QuestionAttemptError.ERROR_CHOICES),
    )
    primary_error = serializers.ChoiceField(
        choices=[choice[0] for choice in QuestionAttemptError.ERROR_CHOICES], required=False, allow_null=True,
    )
    submission_key = serializers.UUIDField(required=False, allow_null=True)
    state_version = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    timing_key = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs.get('result') not in {'correct', 'review'}:
            attrs.pop('time_spent_seconds', None)
        result = attrs.get('result')
        attrs.setdefault('outcome', {
            'correct': 'correct', 'review': 'incorrect', 'done': 'incomplete',
        }.get(result, 'unknown'))
        if attrs.get('used_hint') is True or attrs.get('viewed_answer') is True:
            attrs['is_independent'] = False
        errors = attrs.get('error_codes', [])
        if len(errors) != len(set(errors)):
            raise serializers.ValidationError({'error_codes': 'Error codes must be unique.'})
        primary = attrs.get('primary_error')
        if primary and primary not in errors:
            errors.append(primary)
            attrs['error_codes'] = errors
        if errors and not primary:
            attrs['primary_error'] = errors[0]
        if attrs['outcome'] == 'correct' and errors:
            raise serializers.ValidationError({'error_codes': 'A correct attempt cannot carry error labels.'})
        return attrs


class QuestionUserStateSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=MAX_QUESTION_NOTE_LENGTH, required=False, allow_blank=True)
    is_favorite = serializers.BooleanField(required=False)
    review_later = serializers.BooleanField(required=False)
    version = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if not any(key in attrs for key in ('note', 'is_favorite', 'review_later')):
            raise serializers.ValidationError('Provide note, is_favorite, or review_later.')
        return attrs


class QuestionTimingSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=('begin', 'cancel'), default='begin')
    timing_key = serializers.UUIDField(required=False, allow_null=True)


class QuestionMarkerSelectionSerializer(serializers.Serializer):
    codes = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[choice[0] for choice in QuestionMarker.MARKER_CHOICES],
        ),
        allow_empty=True,
        max_length=len(QuestionMarker.MARKER_CHOICES),
    )

    def validate_codes(self, codes):
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError('Marker codes must be unique.')
        return codes


class PaperGenerateSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=1, max_value=100, default=20)
    document = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    topic = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    source_category = serializers.ChoiceField(
        choices=[choice[0] for choice in Question.SOURCE_CATEGORY_CHOICES],
        required=False,
        allow_blank=True,
    )
    unattempted = serializers.BooleanField(required=False, default=False)


class ExamPaperCreateSerializer(serializers.Serializer):
    blueprint = serializers.SlugRelatedField(
        slug_field='code',
        queryset=ExamBlueprint.objects.filter(is_active=True, subject='math2'),
    )
    seed = serializers.IntegerField(min_value=0, max_value=2 ** 63 - 1, required=False)
    include_mastered = serializers.BooleanField(required=False, default=False)
    cooldown_days = serializers.IntegerField(min_value=0, max_value=365, required=False)


class ExamPaperStatusSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=('start', 'complete'))


class ExamPaperItemUpdateSerializer(serializers.Serializer):
    user_answer = serializers.CharField(required=False, allow_blank=True, max_length=10000)
    result = serializers.ChoiceField(
        choices=('unanswered', 'correct', 'incorrect', 'review'), required=False,
    )
    time_spent_seconds = serializers.IntegerField(min_value=0, max_value=10800, required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Provide an answer, result, or time spent.')
        return attrs
