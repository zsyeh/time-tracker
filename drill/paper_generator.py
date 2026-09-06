"""Deterministic, explainable Mathematics II paper generation."""

import datetime
import random
import secrets
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef, Q, Subquery
from django.db.models.functions import Length
from django.utils import timezone

from .models import (
    ExamBlueprint, ExamPaper, ExamPaperItem, Question, QuestionAttempt,
    QuestionAsset, QuestionMarker, QuestionRevision, QuestionUserState,
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
        selected_topic_counts = {}
        selected_document_counts = {}
        selected = []
        candidate_cache = {}
        for section in sections:
            if section.question_type not in candidate_cache:
                candidate_cache[section.question_type] = self.candidate_pool(
                    user=user,
                    blueprint=blueprint,
                    question_type=section.question_type,
                    include_mastered=include_mastered,
                    cooldown_days=cooldown,
                    excluded_ids=set(),
                )
            candidates = [
                question for question in candidate_cache[section.question_type]
                if question.pk not in selected_ids
            ]
            if len(candidates) < section.question_count:
                raise PaperGenerationError(
                    f'Not enough eligible {section.get_question_type_display().lower()} questions '
                    f'for “{section.title}”: need {section.question_count}, found {len(candidates)}.',
                    section=section.title,
                    required=section.question_count,
                    available=len(candidates),
                )
            chosen = self.choose_for_section(
                candidates, section, blueprint.mode, rng,
                prior_topic_counts=selected_topic_counts,
                prior_document_counts=selected_document_counts,
            )
            selected.extend((section, question) for question in chosen)
            selected_ids.update(question.pk for question in chosen)
            for question in chosen:
                selected_document_counts[question.document_id] = (
                    selected_document_counts.get(question.document_id, 0) + 1
                )
                topic_id = question.similarity_topic_id or question.topic_id
                if topic_id:
                    selected_topic_counts[topic_id] = selected_topic_counts.get(topic_id, 0) + 1

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
                    question_revision=QuestionRevision.capture(question),
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
        trusted_type = (
            Q(question_type_human_verified=True)
            | Q(
                question_type_source__in=('neighbor', 'import'),
                question_type_confidence__gte=0.85,
            )
        )
        # OCR confidence has different meaning for each structure. One stray
        # ``A.`` is enough for the first-pass classifier to call a choice 0.91,
        # which is useful for review but unsafe for a formal paper. Require the
        # strongest structural evidence for choices while retaining explicit
        # blank/open-solution rules at their native confidence levels.
        if question_type == 'single_choice':
            trusted_type |= (
                Q(question_type_source='rule', question_type_confidence__gte=0.98)
                | Q(question_type_source='agent', question_type_confidence__gte=0.98)
            )
        elif question_type == 'fill_blank':
            trusted_type |= (
                Q(question_type_source='rule', question_type_confidence__gte=0.94)
                | Q(question_type_source='agent', question_type_confidence__gte=0.94)
            )
        else:
            trusted_type |= (
                Q(question_type_source='rule', question_type_confidence__gte=0.88)
                | Q(question_type_source='agent', question_type_confidence__gte=0.97)
            )
        latest = QuestionAttempt.objects.filter(
            user=user, question_id=OuterRef('pk'),
        ).order_by('-created_at', '-pk')
        state = QuestionUserState.objects.filter(user=user, question_id=OuterRef('pk'))
        readable_question_crop = QuestionAsset.objects.filter(
            question_id=OuterRef('pk'), asset_type='question_crop', height__gte=120,
        )
        any_question_crop = QuestionAsset.objects.filter(
            question_id=OuterRef('pk'), asset_type='question_crop',
        )
        answer_crop = QuestionAsset.objects.filter(
            question_id=OuterRef('pk'), asset_type='answer_crop', height__gte=60,
        )
        queryset = Question.objects.filter(
            subject=blueprint.subject,
            document__workspace='drill',
            is_practiceable=True,
            record_kind='question',
            question_type=question_type,
        ).filter(
            # Explicit applicability always wins, including adapted questions.
            Q(exam_variant='') | Q(exam_variant__contains='二'),
        ).filter(trusted_type).exclude(
            pk__in=excluded_ids,
        ).exclude(
            Q(topic__display_title__regex=r'数[一三].*专项')
            | Q(topic__title__regex=r'数[一三].*专项')
            | Q(similarity_topic__display_title__regex=r'数[一三].*专项')
            | Q(similarity_topic__title__regex=r'数[一三].*专项'),
        ).exclude(
            # A second source-style roman marker inside one parsed prompt is a
            # strong signal that adjacent exercises were joined into one row.
            prompt_text__regex=(
                r'\n\s*\(?[a-zivx]{1,5}\)?\s*'
                r'(?:19|20|2[0-9]\s*版|660|880|900|1000|姜)'
            ),
        ).exclude(
            # A bare bookmark such as ``d) >>`` has no stable question
            # identity and commonly points at a joined continuation crop.
            source_label__regex=r'^\s*\(?[a-zivx]{1,5}\)?\s*(?:>>)?\s*$',
        ).exclude(
            # The legacy Daguan batch currently mixes worked-solution images
            # into ``question_crop`` rows. Keep it available for manual
            # practice, but quarantine it from timed papers until recropped.
            source_label__contains='大观',
        ).select_related('document', 'similarity_topic').annotate(
            has_readable_question_crop=Exists(readable_question_crop),
            has_any_question_crop=Exists(any_question_crop),
            has_answer_crop=Exists(answer_crop),
            paper_prompt_length=Length('prompt_text'),
            paper_answer_length=Length('answer_markdown'),
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
        ).filter(
            Q(has_readable_question_crop=True)
            | Q(has_any_question_crop=False, paper_prompt_length__gte=24),
        ).filter(
            # A timed paper must remain reviewable. Questions without either a
            # source answer crop or a written solution stay available in
            # ordinary practice, but cannot enter a generated paper.
            Q(has_answer_crop=True) | Q(paper_answer_length__gte=8),
        )
        if not include_mastered:
            queryset = queryset.filter(
                Q(latest_result_for_paper__isnull=True)
                | ~Q(latest_result_for_paper__in=self.MASTERED_RESULTS),
            )
        if cooldown_days:
            cutoff = timezone.now() - datetime.timedelta(days=cooldown_days)
            recently_selected = ExamPaperItem.objects.filter(
                paper__user=user,
                paper__created_at__gte=cutoff,
                question_id=OuterRef('pk'),
            )
            queryset = queryset.annotate(
                recently_selected_for_paper=Exists(recently_selected),
            ).filter(
                Q(latest_attempt_at__isnull=True) | Q(latest_attempt_at__lt=cutoff),
                recently_selected_for_paper=False,
            )
        return list(queryset.order_by('document_id', 'question_order', 'pk'))

    def choose_for_section(
        self, candidates, section, mode, rng, prior_topic_counts=None,
        prior_document_counts=None,
    ):
        prior_topic_counts = prior_topic_counts or {}
        prior_document_counts = prior_document_counts or {}
        ranked = [
            RankedCandidate(question=item, score=self.rank(item, section, mode, rng))
            for item in candidates
        ]
        chosen = []
        chosen_ids = set()
        topic_counts = {}
        document_counts = {}
        topic_cap = section.max_per_topic
        while len(chosen) < section.question_count:
            available = [item for item in ranked if item.question.pk not in chosen_ids]
            capped = [
                item for item in available
                if not topic_cap
                or not (item.question.similarity_topic_id or item.question.topic_id)
                or topic_counts.get(
                    item.question.similarity_topic_id or item.question.topic_id, 0,
                ) < topic_cap
            ]
            # Topic caps are soft, but only relax after all compliant choices
            # have been exhausted. Question-type counts remain hard.
            pool = capped or available
            if not pool:
                break
            pool.sort(key=lambda item: self.paper_balance_key(
                item, section, prior_document_counts, document_counts,
                prior_topic_counts, topic_counts,
            ))
            selected = pool[0].question
            chosen.append(selected)
            chosen_ids.add(selected.pk)
            document_counts[selected.document_id] = (
                document_counts.get(selected.document_id, 0) + 1
            )
            topic_id = selected.similarity_topic_id or selected.topic_id
            if topic_id:
                topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1
        return chosen

    @staticmethod
    def paper_balance_key(
        candidate, section, prior_document_counts, document_counts,
        prior_topic_counts, topic_counts,
    ):
        question = candidate.question
        document_title = question.document.display_title or question.document.title
        desired_weight = max(0.1, float(section.chapter_weights.get(
            f'document:{document_title}', 1.0,
        )))
        document_load = (
            prior_document_counts.get(question.document_id, 0)
            + document_counts.get(question.document_id, 0)
        ) / desired_weight
        topic_id = question.similarity_topic_id or question.topic_id
        topic_load = (
            prior_topic_counts.get(topic_id, 0) + topic_counts.get(topic_id, 0)
            if topic_id else 0
        )
        return document_load, topic_load, -candidate.score, question.pk

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
