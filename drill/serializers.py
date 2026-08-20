from rest_framework import serializers

from .models import Question, QuestionAttempt, QuestionMarker


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

    class Meta:
        model = Question
        fields = (
            'uuid', 'document', 'question_order', 'source_label', 'display_label',
            'topic', 'is_past_exam', 'source_category', 'source_category_label',
            'record_kind', 'exam_year', 'exam_variant', 'attempt_count',
            'latest_result', 'state', 'can_undo',
            'is_favorite', 'review_later', 'saved_note',
        )


class QuestionAttemptCreateSerializer(serializers.Serializer):
    result = serializers.ChoiceField(
        choices=[choice[0] for choice in QuestionAttempt.RESULT_CHOICES],
        default='correct',
    )
    confidence = serializers.IntegerField(min_value=0, max_value=100, required=False, allow_null=True)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, allow_null=True)


class QuestionUserStateSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    is_favorite = serializers.BooleanField(required=False)
    review_later = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Provide note, is_favorite, or review_later.')
        return attrs


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
