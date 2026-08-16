from rest_framework import serializers

from .models import Question, QuestionAttempt


class QuestionSummarySerializer(serializers.ModelSerializer):
    document = serializers.SerializerMethodField()
    topic = serializers.SerializerMethodField()
    source_category_label = serializers.CharField(source='get_source_category_display', read_only=True)
    state = serializers.SerializerMethodField()
    can_undo = serializers.SerializerMethodField()
    attempt_count = serializers.IntegerField(read_only=True, default=0)
    latest_result = serializers.CharField(read_only=True, allow_null=True, default=None)

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
        )


class QuestionAttemptCreateSerializer(serializers.Serializer):
    result = serializers.ChoiceField(
        choices=[choice[0] for choice in QuestionAttempt.RESULT_CHOICES],
        default='correct',
    )
