from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import (
    DrillContentShare,
    ExamPaperItem,
    QuestionAsset,
    QuestionRevisionAsset,
)


def public_share(raw_token, workspace):
    if len(raw_token) > 128:
        raise Http404
    return get_object_or_404(
        DrillContentShare.objects.select_related(
            'question__document', 'question__similarity_topic', 'paper__blueprint',
        ),
        token_digest=DrillContentShare.digest(raw_token),
        workspace=workspace,
        is_active=True,
        revoked_at__isnull=True,
    )


def _asset_payload(request, raw_token, asset):
    return {
        'id': asset.pk,
        'url': request.build_absolute_uri(f'/share/{raw_token}/assets/{asset.pk}'),
        'width': asset.width,
        'height': asset.height,
    }


def public_share_context(request, share, raw_token):
    if share.question_id:
        question = share.question
        assets = list(question.assets.only(
            'id', 'question_id', 'position', 'asset_type', 'width', 'height', 'sha256',
        ).order_by('position', 'source_id'))
        question_assets = [asset for asset in assets if asset.asset_type == 'question_crop']
        answer_assets = [asset for asset in assets if asset.asset_type == 'answer_crop']
        answer_markdown = question.answer_markdown
        if not question_assets or (not answer_assets and not answer_markdown):
            from drill_sources.models import SourceQuestionAnchor

            anchor = SourceQuestionAnchor.objects.select_related('source_question').filter(
                question=question,
            ).first()
            if anchor:
                source = anchor.source_question
                source_assets = list(source.assets.only(
                    'id', 'question_id', 'position', 'asset_type', 'width', 'height', 'sha256',
                ).order_by('position', 'source_id'))
                if not question_assets:
                    question_assets = [
                        asset for asset in source_assets if asset.asset_type == 'question_crop'
                    ]
                if not answer_assets and not answer_markdown:
                    answer_assets = [
                        asset for asset in source_assets if asset.asset_type == 'answer_crop'
                    ]
                    answer_markdown = source.answer_markdown
        topic = question.similarity_topic
        items = [{
            'position': 1,
            'label': question.display_label or question.source_label or f'Question {question.question_order}',
            'document': question.document.display_title or question.document.title,
            'topic': (topic.display_title or topic.title) if topic else '',
            'prompt_text': question.prompt_text,
            'latex_text': question.latex_text,
            'question_assets': [
                _asset_payload(request, raw_token, asset)
                for asset in question_assets
            ],
            'answer_markdown': answer_markdown,
            'answer_assets': [
                _asset_payload(request, raw_token, asset)
                for asset in answer_assets
            ],
        }]
        return {
            'kind': 'question',
            'title': items[0]['label'],
            'subtitle': items[0]['document'],
            'workspace': share.workspace,
            'items': items,
            'open_path': f'/practice/{question.uuid}',
        }

    revision_assets = QuestionRevisionAsset.objects.select_related('asset').order_by('position')
    paper_items = ExamPaperItem.objects.filter(paper=share.paper).select_related(
        'question_revision',
    ).prefetch_related(Prefetch(
        'question_revision__revision_assets', queryset=revision_assets,
    )).order_by('position')
    items = []
    for paper_item in paper_items:
        revision = paper_item.question_revision
        assets = list(revision.revision_assets.all())
        question_assets = [link.asset for link in assets if link.asset_type == 'question_crop']
        answer_assets = [link.asset for link in assets if link.asset_type == 'answer_crop']
        items.append({
            'position': paper_item.position,
            'label': f'Question {paper_item.position:02d}',
            'document': revision.document_title,
            'topic': revision.topic_title,
            'prompt_text': '' if question_assets else revision.prompt_text,
            'latex_text': '' if question_assets else revision.latex_text,
            'question_assets': [
                _asset_payload(request, raw_token, asset) for asset in question_assets
            ],
            'answer_markdown': revision.answer_markdown,
            'answer_assets': [
                _asset_payload(request, raw_token, asset) for asset in answer_assets
            ],
        })
    return {
        'kind': 'paper',
        'title': share.paper.blueprint.title,
        'subtitle': f'{len(items)} questions · {share.paper.blueprint.total_score} points',
        'workspace': share.workspace,
        'items': items,
        'open_path': f'/papers/{share.paper.uuid}/review',
    }


def share_markdown(context):
    lines = [f'# {context["title"]}', '', context['subtitle'], '']
    for item in context['items']:
        lines.extend([
            f'## {item["label"]}',
            '',
            '### Question',
            '',
        ])
        if item['prompt_text']:
            lines.extend([item['prompt_text'], ''])
        if item['latex_text'] and item['latex_text'] != item['prompt_text']:
            lines.extend(['```tex', item['latex_text'], '```', ''])
        for index, asset in enumerate(item['question_assets'], 1):
            lines.extend([f'![Question image {index}]({asset["url"]})', ''])
        lines.extend(['### Answer and explanation', ''])
        if item['answer_markdown']:
            lines.extend([item['answer_markdown'], ''])
        for index, asset in enumerate(item['answer_assets'], 1):
            lines.extend([f'![Answer image {index}]({asset["url"]})', ''])
        if not item['answer_markdown'] and not item['answer_assets']:
            lines.extend(['No answer is currently available.', ''])
    return '\n'.join(lines).strip() + '\n'


def share_contains_asset(share, asset_id):
    if share.question_id:
        question_ids = [share.question_id]
        from drill_sources.models import SourceQuestionAnchor

        source_id = SourceQuestionAnchor.objects.filter(
            question_id=share.question_id,
        ).values_list('source_question_id', flat=True).first()
        if source_id:
            question_ids.append(source_id)
        return QuestionAsset.objects.filter(pk=asset_id, question_id__in=question_ids).exists()
    return QuestionRevisionAsset.objects.filter(
        asset_id=asset_id,
        revision__paper_items__paper_id=share.paper_id,
    ).exists()
