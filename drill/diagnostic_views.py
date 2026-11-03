import datetime

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .diagnostics import DEFAULT_REVIEW_DAYS, attempt_payload, diagnostic_dashboard, review_plan_payload
from .models import QuestionAttempt, QuestionAttemptError, QuestionReviewPlan, QuestionUserState
from .notes import MAX_QUESTION_NOTE_LENGTH, merge_note_values
from .views import request_workspace


ERROR_CODES = {choice[0] for choice in QuestionAttemptError.ERROR_CHOICES}


def _date_range(request):
    today = timezone.localdate()
    try:
        if request.query_params.get('start') and request.query_params.get('end'):
            start = datetime.date.fromisoformat(request.query_params['start'])
            end = datetime.date.fromisoformat(request.query_params['end'])
        else:
            days = int(request.query_params.get('days', 7))
            if days not in {7, 14, 30, 50, 90}:
                raise ValueError
            start, end = today - datetime.timedelta(days=days - 1), today
        if start > end or (end - start).days > 365:
            raise ValueError
    except (TypeError, ValueError):
        return None, None
    return start, end


class DiagnosticDashboardView(APIView):
    def get(self, request):
        start, end = _date_range(request)
        if not start:
            return Response({'detail': 'Use days=7/14/30/50/90 or a valid start/end range up to 366 days.'}, status=400)
        return Response(diagnostic_dashboard(request.user, request_workspace(request), start, end))


class DiagnosticQuestionListView(APIView):
    def get(self, request):
        workspace = request_workspace(request)
        plans = QuestionReviewPlan.objects.filter(
            user=request.user, question__document__workspace=workspace,
        ).select_related('question__document', 'question__similarity_topic')
        codes = {value for value in request.query_params.get('error', '').split(',') if value}
        if codes:
            if not codes <= ERROR_CODES:
                return Response({'detail': 'Unknown error code.'}, status=400)
            question_ids = QuestionAttemptError.objects.filter(
                attempt__user=request.user,
                attempt__question__document__workspace=workspace,
                code__in=codes,
            ).values('attempt__question_id')
            plans = plans.filter(question_id__in=question_ids)
        queue = request.query_params.get('queue', '')
        if queue == 'due':
            plans = plans.filter(status='active', next_review_at__lte=timezone.now())
        elif queue == 'active':
            plans = plans.filter(status='active')
        elif queue:
            return Response({'detail': 'queue must be due or active.'}, status=400)
        rows = []
        for plan in plans.order_by('next_review_at', 'pk')[:200]:
            question = plan.question
            topic = question.similarity_topic or question.topic
            rows.append({
                'uuid': str(question.uuid),
                'label': question.display_label or question.source_label,
                'document': question.document.display_title or question.document.title,
                'topic': (topic.display_title or topic.title) if topic else '',
                'plan': review_plan_payload(plan),
            })
        return Response({'count': len(rows), 'results': rows})


class AttemptDiagnosisView(APIView):
    def patch(self, request, attempt_id):
        workspace = request_workspace(request)
        with transaction.atomic():
            attempt = get_object_or_404(
                QuestionAttempt.objects.select_for_update().prefetch_related('error_tags'),
                pk=attempt_id, user=request.user, question__document__workspace=workspace,
            )
            codes = request.data.get('error_codes')
            primary = request.data.get('primary_error')
            if codes is not None:
                if not isinstance(codes, list) or len(codes) != len(set(codes)) or not set(codes) <= ERROR_CODES:
                    return Response({'error_codes': ['Choose unique supported error codes.']}, status=400)
                if primary and primary not in codes:
                    return Response({'primary_error': ['Primary error must be selected.']}, status=400)
                if codes and not primary:
                    primary = codes[0]
                attempt.error_tags.all().delete()
                QuestionAttemptError.objects.bulk_create([
                    QuestionAttemptError(attempt=attempt, code=code, is_primary=code == primary)
                    for code in codes
                ])
            field_choices = {
                'knowledge_level': {item[0] for item in QuestionAttempt.KNOWLEDGE_CHOICES},
                'method_level': {item[0] for item in QuestionAttempt.METHOD_CHOICES},
                'execution_level': {item[0] for item in QuestionAttempt.EXECUTION_CHOICES},
            }
            changed = []
            for field, choices in field_choices.items():
                if field in request.data:
                    value = request.data[field]
                    if value is not None and value not in choices:
                        return Response({field: ['Unsupported value.']}, status=400)
                    setattr(attempt, field, value)
                    changed.append(field)
            for field in ('used_hint', 'viewed_answer', 'is_independent'):
                if field in request.data:
                    value = request.data[field]
                    if value is not None and not isinstance(value, bool):
                        return Response({field: ['Use true, false, or null.']}, status=400)
                    setattr(attempt, field, value)
                    changed.append(field)
            if attempt.used_hint is True or attempt.viewed_answer is True:
                attempt.is_independent = False
                if 'is_independent' not in changed:
                    changed.append('is_independent')
            legacy_values = [
                str(request.data[field]).strip()
                for field in ('correction_note', 'knowledge_note', 'first_step_note')
                if field in request.data and str(request.data[field]).strip()
            ]
            if legacy_values:
                state, _ = QuestionUserState.objects.select_for_update().get_or_create(
                    user=request.user, question=attempt.question,
                )
                merged_note = merge_note_values(state.note, *legacy_values)
                if len(merged_note) > MAX_QUESTION_NOTE_LENGTH:
                    return Response({
                        'note': [f'题目笔记不能超过 {MAX_QUESTION_NOTE_LENGTH} 字。'],
                    }, status=400)
                if merged_note != state.note:
                    state.note = merged_note
                    state.version += 1
                    state.save(update_fields=['note', 'version', 'updated_at'])
            if changed:
                attempt.save(update_fields=changed)
        attempt.refresh_from_db()
        return Response(attempt_payload(attempt))


class ReviewPlanView(APIView):
    def patch(self, request, question_uuid):
        workspace = request_workspace(request)
        plan = get_object_or_404(
            QuestionReviewPlan.objects.select_related('question'),
            user=request.user, question__uuid=question_uuid,
            question__document__workspace=workspace,
        )
        action = request.data.get('action')
        if action == 'pause':
            plan.status = 'paused'
        elif action == 'resume':
            plan.status = 'active'
            plan.next_review_at = timezone.now()
        elif action == 'snooze':
            days = request.data.get('days', 1)
            if not isinstance(days, int) or not 1 <= days <= 30:
                return Response({'days': ['Choose 1–30 days.']}, status=400)
            plan.status = 'active'
            plan.next_review_at = timezone.now() + datetime.timedelta(days=days)
        elif action == 'schedule':
            schedule = request.data.get('schedule_days')
            if (
                not isinstance(schedule, list) or not schedule or len(schedule) > 12
                or any(not isinstance(day, int) or day < 0 or day > 365 for day in schedule)
                or schedule != sorted(set(schedule))
            ):
                return Response({'schedule_days': ['Provide sorted unique day offsets from 0 to 365.']}, status=400)
            plan.schedule_days = schedule
            plan.step = min(plan.step, len(schedule) - 1)
        else:
            return Response({'detail': 'action must be pause, resume, snooze, or schedule.'}, status=400)
        plan.save()
        return Response(review_plan_payload(plan))
