from rest_framework import serializers

from .models import KnowledgePoint, LaunchToken, LearningIssue, TimeLog
from .services import normalize_subject


class StudySessionSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source='category')
    subject_label = serializers.CharField(source='get_category_display', read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = TimeLog
        fields = (
            'id',
            'subject',
            'subject_label',
            'chapter',
            'topic',
            'start_time',
            'end_time',
            'duration_minutes',
            'status',
            'learning_mode',
            'difficulty',
            'energy_level',
            'focus_level',
            'confidence_before',
            'confidence_after',
            'title',
            'details',
            'breakthrough',
            'problems',
            'next_action',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'start_time',
            'end_time',
            'duration_minutes',
            'status',
            'created_at',
            'updated_at',
        )

    def validate_subject(self, value):
        return normalize_subject(value)


class StudySessionSummarySerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source='category')
    subject_label = serializers.CharField(source='get_category_display', read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = TimeLog
        fields = (
            'id', 'subject', 'subject_label', 'start_time', 'end_time',
            'duration_minutes', 'status', 'title',
        )


class StartSessionSerializer(serializers.Serializer):
    subject = serializers.ChoiceField(choices=('math', 'english', 'professional', 'major', 'training'))
    chapter = serializers.CharField(max_length=200, required=False, allow_blank=True)
    topic = serializers.CharField(max_length=200, required=False, allow_blank=True)
    learning_mode = serializers.ChoiceField(
        choices=[choice[0] for choice in TimeLog.LEARNING_MODE_CHOICES],
        required=False,
        allow_blank=True,
    )
    confidence_before = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)


class FinishSessionSerializer(serializers.Serializer):
    chapter = serializers.CharField(max_length=200, required=False, allow_blank=True)
    topic = serializers.CharField(max_length=200, required=False, allow_blank=True)
    learning_mode = serializers.ChoiceField(
        choices=[choice[0] for choice in TimeLog.LEARNING_MODE_CHOICES],
        required=False,
        allow_blank=True,
    )
    difficulty = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    energy_level = serializers.ChoiceField(
        choices=[choice[0] for choice in TimeLog.ENERGY_CHOICES],
        required=False,
        allow_blank=True,
    )
    focus_level = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    confidence_after = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    # Service-level validation runs after duration validation so invalid-length
    # sessions can be deleted without forcing the user to fill out a form.
    title = serializers.CharField(required=False, allow_blank=True)
    details = serializers.CharField(required=False, allow_blank=True)


class LearningIssueSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source='category')

    class Meta:
        model = LearningIssue
        fields = (
            'id', 'subject', 'topic', 'study_session', 'issue_type', 'description',
            'solution', 'resolved', 'repeat_count', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_study_session(self, value):
        if value and value.user_id != self.context['request'].user.pk:
            raise serializers.ValidationError('session does not belong to this user')
        return value

    def validate_subject(self, value):
        return normalize_subject(value)


class KnowledgePointSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source='category')

    class Meta:
        model = KnowledgePoint
        fields = (
            'id', 'subject', 'name', 'parent', 'importance', 'mastery_score',
            'status', 'last_reviewed_at', 'review_count', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_parent(self, value):
        if value and value.user_id != self.context['request'].user.pk:
            raise serializers.ValidationError('parent does not belong to this user')
        return value

    def validate_subject(self, value):
        return normalize_subject(value)


class LaunchTokenSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source='category')
    usable = serializers.BooleanField(read_only=True)

    class Meta:
        model = LaunchToken
        fields = (
            'id', 'name', 'subject', 'is_active', 'expires_at', 'max_uses',
            'created_at', 'last_used_at', 'usage_count', 'source_label', 'notes', 'usable',
        )
        read_only_fields = ('id', 'created_at', 'last_used_at', 'usage_count', 'usable')


class LaunchTokenCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    subject = serializers.ChoiceField(choices=('math', 'english', 'professional', 'major', 'training'))
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    max_uses = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    source_label = serializers.CharField(max_length=120, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
