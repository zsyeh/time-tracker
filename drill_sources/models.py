from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class SourceQuestionAnchor(models.Model):
    """An independently tracked question pointing into an existing full-page image."""

    question = models.OneToOneField('drill.Question', on_delete=models.CASCADE, related_name='source_anchor')
    source_question = models.ForeignKey('drill.Question', on_delete=models.CASCADE, related_name='source_question_anchors')
    asset = models.ForeignKey('drill.QuestionAsset', on_delete=models.PROTECT, related_name='source_question_anchors')
    key = models.CharField(max_length=96)
    label = models.CharField(max_length=160)
    y = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(1)])
    position = models.PositiveIntegerField()
    confidence = models.FloatField(default=1.0)

    class Meta:
        ordering = ('source_question_id', 'position')
        constraints = [
            models.UniqueConstraint(fields=('source_question', 'key'), name='drill_source_anchor_key_unique'),
            models.UniqueConstraint(fields=('source_question', 'position'), name='drill_source_anchor_pos_unique'),
            models.CheckConstraint(check=models.Q(y__gte=0, y__lte=1), name='drill_source_anchor_y_range'),
        ]

    def clean(self):
        super().clean()
        if self.question_id == self.source_question_id:
            raise ValidationError('An indexed question cannot be its own source.')
        if self.question.document_id != self.source_question.document_id:
            raise ValidationError('Question and source must belong to the same document.')
        if self.asset.question_id != self.source_question_id or self.asset.asset_type != 'question_crop':
            raise ValidationError('The locator must point to a question image owned by the source.')
