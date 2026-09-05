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
EXPLICIT_CHOICE_PATTERN = re.compile(r'(?:选择|单选|多选)', re.I)
EXPLICIT_FILL_PATTERN = re.compile(r'(?:填空|填入空格|应填|横线上)', re.I)
EXPLICIT_SOLUTION_PATTERN = re.compile(r'(?:解答|证明|试证|计算题|大题)', re.I)
OPTION_MARKER_PATTERN = re.compile(
    r'(?:^|[\s;；])(?:[（(\[]\s*)?([ABCDＡＢＣＤ])\s*(?:[）)\].．、:]|(?=\s))',
    re.M,
)
ANSWER_CHOICE_PATTERN = re.compile(r'^\s*(?:#{1,6}\s*)?(?:\*\*)?([ABCD])(?:[.．、:：)]|\*\*)', re.I)


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


def classify_question_type_evidence(
    metadata_text,
    *,
    ocr_text='',
    answer_markdown='',
    question_ratio=0.0,
    answer_ratio=0.0,
    neighbor_type='',
    neighbor_span=0,
):
    """Combine source metadata, OCR structure and answer layout.

    The final low-confidence branches are deliberately explicit and remain
    reviewable through ``question_type_confidence``. They avoid leaving the
    generator with an opaque ``unknown`` pool while never presenting a weak
    inference as human-verified truth.
    """
    metadata = ' '.join((metadata_text or '').split())
    ocr = ocr_text or ''
    combined = f'{metadata}\n{ocr}'

    if EXPLICIT_CHOICE_PATTERN.search(metadata):
        return QuestionTypeDecision('single_choice', 0.99, 'Source metadata explicitly identifies a choice question.')
    if EXPLICIT_FILL_PATTERN.search(metadata):
        return QuestionTypeDecision('fill_blank', 0.99, 'Source metadata explicitly identifies a fill-in question.')
    if EXPLICIT_SOLUTION_PATTERN.search(metadata):
        return QuestionTypeDecision('solution', 0.97, 'Source metadata explicitly identifies an open solution question.')

    option_markers = {
        marker.translate(str.maketrans('ＡＢＣＤ', 'ABCD')).upper()
        for marker in OPTION_MARKER_PATTERN.findall(ocr)
    }
    if len(option_markers) >= 3:
        return QuestionTypeDecision('single_choice', 0.98, 'OCR found at least three distinct A-D option markers.')
    if len(option_markers) == 2:
        return QuestionTypeDecision('single_choice', 0.86, 'OCR found two distinct option markers.')
    if ANSWER_CHOICE_PATTERN.search(answer_markdown or ''):
        return QuestionTypeDecision('single_choice', 0.95, 'Stored answer begins with an A-D choice key.')

    direct = classify_question_type(combined)
    if direct.label != 'unknown':
        return QuestionTypeDecision(direct.label, direct.confidence, f'OCR/text evidence: {direct.reason}')

    if neighbor_type in {'single_choice', 'fill_blank', 'solution'} and 0 < neighbor_span <= 16:
        return QuestionTypeDecision(
            neighbor_type, 0.87,
            'The nearest classified questions on both sides share this type within the same topic.',
        )

    # Layout is supporting evidence only. It is never treated as a verified
    # label, and low-confidence results remain easy to audit or overwrite.
    if question_ratio and question_ratio <= 0.14 and answer_ratio <= 0.9:
        return QuestionTypeDecision(
            'fill_blank', 0.62,
            'Compact prompt and compact answer layout suggest a fill-in response; review recommended.',
        )
    if answer_ratio >= 1.2 or len(answer_markdown or '') >= 180:
        return QuestionTypeDecision(
            'solution', 0.68,
            'Long answer/explanation layout suggests an open solution; review recommended.',
        )
    return QuestionTypeDecision(
        'solution', 0.55,
        'No option or blank structure was found; provisionally classified as open response.',
    )
