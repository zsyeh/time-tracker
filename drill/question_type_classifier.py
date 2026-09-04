"""Explainable first-pass classification for Mathematics II question types."""

import re
from dataclasses import dataclass


CHOICE_PATTERNS = (
    re.compile(r'(?:\(|（)\s*[AaＡ]\s*(?:\)|）|[.．、])'),
    re.compile(r'(?:^|\s)[AaＡ]\s*[.．、].{0,500}(?:^|\s)[BbＢ]\s*[.．、]', re.S),
    re.compile(r'(?:下列|以下).{0,80}(?:正确|错误|成立|不成立|收敛|发散).{0,20}(?:是|为)?\s*[（(]', re.S),
)
FILL_PATTERNS = (
    re.compile(r'_{3,}|＿{2,}|…{3,}'),
    re.compile(r'(?:填空|填入空格|应填|横线上).{0,30}', re.S),
)
SOLUTION_PATTERNS = (
    re.compile(r'(?:^|[。；;\s])(?:求|计算|证明|试证|讨论|解(?:方程|不等式)|判定|确定)(?!值为)[^，。]{0,80}'),
    re.compile(r'(?:\([一二三四五六七八九十IVXivx]+\)|（[一二三四五六七八九十IVXivx]+）).{0,80}(?:求|证明|计算)', re.S),
)


@dataclass(frozen=True)
class QuestionTypeDecision:
    label: str
    confidence: float
    reason: str


def classify_question_type(text):
    """Return a conservative label; ambiguous records remain reviewable."""
    normalized = ' '.join((text or '').split())
    if not normalized:
        return QuestionTypeDecision('unknown', 0.0, 'No searchable question text.')
    choice_hits = sum(bool(pattern.search(normalized)) for pattern in CHOICE_PATTERNS)
    if choice_hits >= 2:
        return QuestionTypeDecision('single_choice', 0.98, 'Option structure and choice stem detected.')
    if choice_hits == 1:
        return QuestionTypeDecision('single_choice', 0.91, 'Choice option structure detected.')
    if any(pattern.search(normalized) for pattern in FILL_PATTERNS):
        return QuestionTypeDecision('fill_blank', 0.94, 'Blank or fill-in instruction detected.')
    if any(pattern.search(normalized) for pattern in SOLUTION_PATTERNS):
        return QuestionTypeDecision('solution', 0.88, 'Open solution instruction detected.')
    return QuestionTypeDecision('unknown', 0.35, 'No reliable type-specific structure detected.')
