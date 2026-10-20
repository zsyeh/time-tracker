"""Read-only full-paper presentation for independently tracked source questions."""
from django.db.models import OuterRef, Subquery

from drill.models import QuestionAttempt
from .models import SourceQuestionAnchor


def attach_source_context(payload, question, request):
    def asset_payload(asset):
        return {'id': asset.pk, 'url': f'/api/drill/assets/{asset.pk}/?v={asset.sha256[:16]}',
                'width': asset.width, 'height': asset.height, 'position': asset.position}

    anchor = SourceQuestionAnchor.objects.select_related('source_question', 'asset').filter(question=question).first()
    # A reviewed individual crop supersedes shared-page presentation. Keep
    # anchors as provenance, without forcing neighbouring questions on screen.
    if anchor and question.assets.filter(asset_type='question_crop').exists():
        source = anchor.source_question
        payload['original_source'] = {'uuid': str(source.uuid), 'label': source.display_label}
        if not payload.get('answer_assets') and not question.answer_markdown:
            payload['answer_assets'] = [asset_payload(a) for a in source.assets.filter(asset_type='answer_crop').only(
                'id', 'position', 'width', 'height', 'sha256')]
            payload['has_answer'] = bool(payload['answer_assets'])
            payload['answer_markdown'] = source.answer_markdown
            payload['answer_source'] = source.answer_source
            payload['answer_confidence'] = source.answer_confidence
            if payload['has_answer'] or source.answer_markdown:
                payload['answer_scope'] = 'source_paper'
        return
    source = anchor.source_question if anchor else question
    latest = QuestionAttempt.objects.filter(user=request.user, question_id=OuterRef('question_id')).order_by('-created_at', '-pk')
    siblings = list(SourceQuestionAnchor.objects.filter(source_question=source).select_related('question').annotate(
        latest_result=Subquery(latest.values('result')[:1]),
    ).order_by('position'))
    if not siblings:
        return
    assets = list(source.assets.only('id', 'question_id', 'position', 'asset_type', 'width', 'height', 'sha256'))

    payload['question_assets'] = [asset_payload(a) for a in assets if a.asset_type == 'question_crop']
    payload['assets'] = payload['question_assets']
    payload['answer_assets'] = [asset_payload(a) for a in assets if a.asset_type == 'answer_crop']
    payload['has_answer'] = bool(payload['answer_assets'])
    if anchor and not question.answer_markdown:
        payload['answer_markdown'] = source.answer_markdown
        payload['answer_source'] = source.answer_source
        payload['answer_confidence'] = source.answer_confidence
    payload['source_context'] = {
        'source_uuid': str(source.uuid), 'source_label': source.display_label,
        'answer_scope': 'source_paper',
        'index_complete': not source.is_practiceable,
        'anchor': {'asset_id': anchor.asset_id, 'y': anchor.y} if anchor else None,
        'anchors': [
            {'uuid': str(item.question.uuid), 'label': item.label, 'asset_id': item.asset_id,
             'y': item.y, 'position': item.position,
             'state': 'mastered' if item.latest_result in ('done', 'correct') else 'review' if item.latest_result == 'review' else 'unattempted'}
            for item in siblings
        ],
    }
