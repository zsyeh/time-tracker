import datetime

from django.utils import timezone
from rest_framework import serializers

from .models import InviteCode, KnowledgePoint, LaunchToken, LearningIssue, TimeLog
from .services import normalize_subject


class StudySessionSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source='category')
    subject_label = serializers.CharField(source='get_category_display', read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = TimeLog
        fields = (
            'id',
            'uuid',
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
            'review_count',
            'last_reviewed_at',
            'disturbance_count',
            'last_disturbance_at',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'uuid',
            'start_time',
            'end_time',
            'duration_minutes',
            'status',
            'created_at',
            'updated_at',
            'review_count',
            'last_reviewed_at',
            'disturbance_count',
            'last_disturbance_at',
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
            'id', 'uuid', 'subject', 'subject_label', 'start_time', 'end_time',
            'duration_minutes', 'status', 'title',
            'review_count', 'last_reviewed_at',
        )


class SessionShareCreateSerializer(serializers.Serializer):
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError('expiry must be in the future')
        return value


class PublicSharedSessionSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    subject = serializers.CharField(source='category')
    duration_minutes = serializers.IntegerField(read_only=True)
    markdown = serializers.CharField(source='details', read_only=True)

    class Meta:
        model = TimeLog
        fields = (
            'title', 'subject', 'start_time', 'end_time',
            'duration_minutes', 'markdown',
        )

    def get_title(self, obj):
        return obj.title or obj.topic or obj.chapter or 'Untitled session'


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
    credential_valid = serializers.BooleanField(read_only=True)
    within_schedule = serializers.BooleanField(read_only=True)
    has_disturbance_uri = serializers.BooleanField(read_only=True)

    class Meta:
        model = LaunchToken
        fields = (
            'id', 'name', 'subject', 'is_active', 'is_paused',
            'available_from', 'available_until', 'expires_at', 'max_uses',
            'created_at', 'last_used_at', 'usage_count', 'source_label', 'notes',
            'usable', 'credential_valid', 'within_schedule', 'has_disturbance_uri',
        )
        read_only_fields = (
            'id', 'created_at', 'last_used_at', 'usage_count', 'usable',
            'credential_valid', 'within_schedule', 'has_disturbance_uri',
        )


class LaunchTokenCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    subject = serializers.ChoiceField(choices=('math', 'english', 'professional', 'major', 'training'))
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    max_uses = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    source_label = serializers.CharField(max_length=120, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    available_from = serializers.TimeField(default=datetime.time(6, 0))
    available_until = serializers.TimeField(default=datetime.time(22, 0))

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError('Expiry must be in the future.')
        return value


class LaunchTokenConfigureSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    available_from = serializers.TimeField()
    available_until = serializers.TimeField()
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    max_uses = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    source_label = serializers.CharField(max_length=120, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError('Expiry must be in the future.')
        return value


class RuntimeSettingsSerializer(serializers.Serializer):
    homepage_content = serializers.CharField(max_length=500, allow_blank=True, trim_whitespace=True)
    study_room_code = serializers.CharField(max_length=120, allow_blank=True, trim_whitespace=True)
    tracking_start_date = serializers.DateField()
    exam_date = serializers.DateField()
    countdown_label = serializers.CharField(max_length=80, allow_blank=False, trim_whitespace=True)

    def validate(self, attrs):
        if attrs['tracking_start_date'] > attrs['exam_date']:
            raise serializers.ValidationError({
                'tracking_start_date': 'Tracking start date must not be later than the exam date.',
            })
        return attrs


class UserDataEncryptionSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()


class InviteCodeSerializer(serializers.ModelSerializer):
    usable = serializers.BooleanField(read_only=True)
    remaining_uses = serializers.IntegerField(read_only=True)
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    visitors = serializers.SerializerMethodField()

    def get_visitors(self, obj):
        return [
            {
                'username': redemption.user.get_username(),
                'redeemed_at': redemption.redeemed_at,
            }
            for redemption in obj.redemptions.all()
        ]

    class Meta:
        model = InviteCode
        fields = (
            'id', 'name', 'created_by', 'is_active', 'max_uses', 'use_count',
            'remaining_uses', 'expires_at', 'last_used_at', 'created_at', 'usable',
            'is_self_service', 'issued_local_date', 'visitors',
        )


class InviteCodeCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    max_uses = serializers.IntegerField(min_value=1, max_value=100, default=1)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError('Expiry must be in the future.')
        return value
