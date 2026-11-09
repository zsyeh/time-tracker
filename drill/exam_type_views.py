"""Authenticated, workspace-scoped human corrections; public shares stay read-only."""
import uuid

from django.db import transaction
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .exam_types import LEGACY, TYPES, type_group, digest_for_question
from .models import Question, QuestionExamType, QuestionExamTypeEdit


def snapshot(record):
    if record is None:
        return None
    data = model_to_dict(record, exclude=('id', 'question'))
    data['updated_at'] = record.updated_at.isoformat()
    return data


def payload(question, record):
    label = record.question_type if record else LEGACY.get(question.question_type, 'unknown')
    return {'question_type': label, 'type_group': type_group(label), 'classification': snapshot(record)}


class QuestionExamTypeView(APIView):
    permission_classes = [IsAuthenticated]

    def question(self, request, question_uuid, lock=False):
        from .views import request_workspace
        qs = Question.objects.filter(document__workspace=request_workspace(request))
        if lock:
            qs = qs.select_for_update()
        return get_object_or_404(qs, uuid=question_uuid)

    def get(self, request, question_uuid):
        question = self.question(request, question_uuid)
        return Response(payload(question, getattr(question, 'exam_type', None)))

    @transaction.atomic
    def patch(self, request, question_uuid):
        question = self.question(request, question_uuid, lock=True)
        workspace = question.document.workspace
        label = request.data.get('question_type')
        allowed = TYPES if workspace == 'ei' else ('choice', 'fill', 'large', 'unknown')
        if label not in allowed:
            return Response({'detail': 'Invalid question type for this workspace.'}, status=400)
        record = QuestionExamType.objects.filter(question=question).select_for_update().first()
        before = snapshot(record)
        expected = before['updated_at'] if before else None
        if 'expected_updated_at' not in request.data or request.data['expected_updated_at'] != expected:
            return Response({'detail': 'Classification changed. Reopen the format selector and retry.'}, status=409)
        if record and record.question_type == label:
            return Response(payload(question, record))
        if record is None:
            record = QuestionExamType(question=question, source_system=workspace,
                                      content_hash=digest_for_question(question))
        record.question_type = label
        record.classification_source = 'human'
        record.classification_version = 'manual-v1'
        record.model_id = ''
        record.review_required = label == 'unknown'
        record.review_reasons = ['unknown_type'] if label == 'unknown' else []
        record.reason = 'Explicit human correction'
        record.evidence_missing = ''
        record.batch_id = 'manual_' + uuid.uuid4().hex
        record.save()
        QuestionExamTypeEdit.objects.create(question=question, actor=request.user,
                                           before=before or {'legacy_question_type': question.question_type},
                                           after=snapshot(record))
        return Response(payload(question, record))
