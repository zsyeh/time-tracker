"""Deterministic, explainable Mathematics II paper generation."""

import datetime
import random
import secrets
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef, Q, Subquery
from django.utils import timezone

from .models import (
    ExamBlueprint, ExamPaper, ExamPaperItem, Question, QuestionAttempt,
    QuestionMarker, QuestionUserState,
)


class PaperGenerationError(ValueError):
    def __init__(self, message, *, section=None, required=None, available=None):
        super().__init__(message)
        self.section = section
        self.required = required
        self.available = available


@dataclass(frozen=True)
class RankedCandidate:
    question: Question
    score: float


class PaperGenerator:
    """Select questions once, persist references, and preserve their order."""

    MASTERED_RESULTS = ('done', 'correct')

    def generate(self, *, user, blueprint, seed=None, include_mastered=False, cooldown_days=None):
        if not isinstance(blueprint, ExamBlueprint) or not blueprint.is_active:
            raise PaperGenerationError('The selected blueprint is not active.')
        seed = seed if seed is not None else secrets.randbits(63)
        if seed < 0 or seed >= 2 ** 63:
            raise PaperGenerationError('Seed must be between 0 and 2^63-1.')
        rng = random.Random(seed)
        sections = list(blueprint.sections.all().order_by('order'))
        if not sections:
            raise PaperGenerationError('The selected blueprint has no sections.')
        cooldown = blueprint.cooldown_days if cooldown_days is None else cooldown_days
        selected_ids = set()
        selected = []
        for section in sections:
            candidates = self.candidate_pool(
                user=user,
                blueprint=blueprint,
                question_type=section.question_type,
                include_mastered=include_mastered,
                cooldown_days=cooldown,
                excluded_ids=selected_ids,
            )
            if len(candidates) < section.question_count:
                raise PaperGenerationError(
                    f'Not enough eligible {section.get_question_type_display().lower()} questions '
                    f'for “{section.title}”: need {section.question_count}, found {len(candidates)}.',
                    section=section.title,
                    required=section.question_count,
                    available=len(candidates),
                )
            chosen = self.choose_for_section(candidates, section, blueprint.mode, rng)
            selected.extend((section, question) for question in chosen)
            selected_ids.update(question.pk for question in chosen)

        with transaction.atomic():
            paper = ExamPaper.objects.create(
                user=user,
                blueprint=blueprint,
                seed=seed,
                mode=blueprint.mode,
            )
            ExamPaperItem.objects.bulk_create([
                ExamPaperItem(
                    paper=paper,
                    section=section,
                    question=question,
                    position=position,
                    score=section.score_per_question,
                    selected_fingerprint=question.fingerprint,
                )
                for position, (section, question) in enumerate(selected, 1)
            ])
        return paper

    def candidate_pool(
        self, *, user, blueprint, question_type, include_mastered,
        cooldown_days, excluded_ids,
    ):
        latest = QuestionAttempt.objects.filter(
            user=user, question_id=OuterRef('pk'),
        ).order_by('-created_at', '-pk')
        state = QuestionUserState.objects.filter(user=user, question_id=OuterRef('pk'))
        queryset = Question.objects.filter(
            subject=blueprint.subject,
            document__workspace='drill',
            is_practiceable=True,
            record_kind='question',
            question_type=question_type,
        ).exclude(pk__in=excluded_ids).select_related('document', 'similarity_topic').annotate(
            latest_result_for_paper=Subquery(latest.values('result')[:1]),
            latest_attempt_at=Subquery(latest.values('created_at')[:1]),
            paper_attempt_count=Count('attempts', filter=Q(attempts__user=user), distinct=True),
            paper_error_count=Count(
                'attempts', filter=Q(attempts__user=user, attempts__result='review'), distinct=True,
            ),
            paper_marker_count=Count(
                'markers', filter=Q(markers__user=user), distinct=True,
            ),
            paper_review_later=Exists(state.filter(review_later=True)),
            prior_paper_time=Max(
                'paper_items__time_spent_seconds',
                filter=Q(paper_items__paper__user=user),
            ),
        )
        if not include_mastered:
            queryset = queryset.filter(
                Q(latest_result_for_paper__isnull=True)
                | ~Q(latest_result_for_paper__in=self.MASTERED_RESULTS),
            )
        if cooldown_days:
            cutoff = timezone.now() - datetime.timedelta(days=cooldown_days)
            queryset = queryset.filter(
                Q(latest_attempt_at__isnull=True) | Q(latest_attempt_at__lt=cutoff),
            )
        return list(queryset.order_by('document_id', 'question_order', 'pk'))

    def choose_for_section(self, candidates, section, mode, rng):
        ranked = [
            RankedCandidate(question=item, score=self.rank(item, section, mode, rng))
            for item in candidates
        ]
        ranked.sort(key=lambda item: (-item.score, item.question.pk))
        chosen = []
        chosen_ids = set()
        topic_counts = {}
        topic_cap = section.max_per_topic
        for candidate in ranked:
            topic_id = candidate.question.similarity_topic_id or candidate.question.topic_id
            if topic_cap and topic_id and topic_counts.get(topic_id, 0) >= topic_cap:
                continue
            chosen.append(candidate.question)
            chosen_ids.add(candidate.question.pk)
            if topic_id:
                topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1
            if len(chosen) == section.question_count:
                return chosen
        # The diversity cap is a soft constraint. Relax it only after every
        # available topic has had a fair chance; question-type counts stay hard.
        for candidate in ranked:
            if candidate.question.pk in chosen_ids:
                continue
            chosen.append(candidate.question)
            if len(chosen) == section.question_count:
                return chosen
        return chosen

    @staticmethod
    def rank(question, section, mode, rng):
        random_tie_breaker = rng.random()
        topic = question.similarity_topic
        topic_key = str(topic.pk) if topic else ''
        topic_title = (topic.display_title or topic.title) if topic else ''
        chapter_weight = float(
            section.chapter_weights.get(topic_key, section.chapter_weights.get(topic_title, 1.0)),
        )
        difficulty_weight = float(
            section.difficulty_weights.get(str(question.difficulty), 1.0)
            if question.difficulty is not None else 1.0
        )
        latest_at = getattr(question, 'latest_attempt_at', None)
        days_idle = min(365, (timezone.now() - latest_at).days) if latest_at else 365
        staleness = days_idle / 365
        if mode == 'weak':
            attempts = getattr(question, 'paper_attempt_count', 0)
            errors = getattr(question, 'paper_error_count', 0)
            error_rate = errors / attempts if attempts else 0
            slow = min(1.0, (getattr(question, 'prior_paper_time', 0) or 0) / 1200)
            weak_score = (
                4.0 * error_rate
                + 1.5 * errors
                + 1.0 * slow
                + 0.8 * getattr(question, 'paper_marker_count', 0)
                + 1.2 * bool(getattr(question, 'paper_review_later', False))
                + 0.7 * staleness
            )
            return weak_score * chapter_weight * difficulty_weight + random_tie_breaker * 0.05
        if mode == 'intensive':
            return chapter_weight * difficulty_weight + staleness * 0.6 + random_tie_breaker * 0.2
        return chapter_weight * difficulty_weight + staleness * 0.25 + random_tie_breaker * 0.5
