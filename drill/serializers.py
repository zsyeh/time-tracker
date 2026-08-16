from rest_framework import serializers

from .models import Question, QuestionAttempt


class QuestionSummarySerializer(serializers.ModelSerializer):
    document = serializers.CharField(source='document.title', read_only=True)
    topic = serializers.CharField(source='similarity_topic.title', read_only=True, default='')
    attempt_count = serializers.IntegerField(read_only=True, default=0)
    latest_result = serializers.CharField(read_only=True, allow_null=True, default=None)

    class Meta:
        model = Question
        fields = (
            'uuid', 'document', 'question_order', 'source_label', 'topic',
            'is_past_exam', 'exam_year', 'exam_variant', 'attempt_count',
            'latest_result',
        )


class QuestionAttemptCreateSerializer(serializers.Serializer):
    result = serializers.ChoiceField(
        choices=[choice[0] for choice in QuestionAttempt.RESULT_CHOICES],
        default='done',
    )

