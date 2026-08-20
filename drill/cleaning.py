"""Deterministic, reversible cleanup for the imported question bank.

The source labels and topic titles remain untouched.  These helpers only build
display metadata, so rules can be improved later without losing provenance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


YEAR = r'(?:19\d{2}|20\d{2})'
PAST_EXAM_RE = re.compile(
    rf'(?<!\d)(?P<year>{YEAR})\s*[,，、]?\s*'
    r'(?:数(?:学)?\s*)(?P<variants>[一二三](?:\s*(?:[、,，]|数)?\s*[一二三])*)'
)
GENERIC_PAST_EXAM_RE = re.compile(rf'(?<!\d)(?P<year>{YEAR})\s*(?:年)?\s*真题')
MOCK_RE = re.compile(
    r'(?:模拟(?:题|卷|套)?|预测(?:题|卷|套)?|押题(?:题|卷|套)?|'
    r'(?:张宇|李永乐|李艳芳|李林|余丙森|汤家凤|王式安|武忠祥|合工大|超越|共创)'
    r'.{0,24}?(?:三|四|五|六|八)套)'
)
WORKBOOK_RE = re.compile(
    r'(?:(?<!\d)(?:660|880|900|1000|1800|330)(?!\d)|'
    r'(?:真题同源|基础例题|强化例题|基础选择|基础填空|基础解答|'
    r'综合选择|综合填空|综合解答|A\s*类|B\s*类|C\s*类|A\s*组|B\s*组|C\s*组))',
    re.IGNORECASE,
)
CONTEXT_MOCK_RE = re.compile(
    r'(?:[二三四五六七八九十]|[2-9])套(?:数|试|卷)|'
    r'(?:张宇|李林|李永乐|汤家凤|余丙森|合工大|超越|共创).{0,20}(?:四|五|六|八)套'
)
CONTEXT_WORKBOOK_RE = re.compile(
    r'(?:0[.]?1w|魔法练习册|练习册|姜晓千|郭伟|线代\s*9\s*讲|张老师\s*1000|大观)',
    re.IGNORECASE,
)
COMPETITION_RE = re.compile(r'(?:竞赛|奥林匹克)')
ADAPTED_RE = re.compile(r'(?:改编|改造|变式)')
OUTLINE_PREFIX_RE = re.compile(
    r'^\s*(?:(?:\(?\d+\)?|\(?[A-Za-z]{1,3}\)?|'
    r'[ivxlcdmIVXLCDM]+|[一二三四五六七八九十]+)[.、)）]\s*)'
)
LEADER_RE = re.compile(
    r'\s*(?:>{2,}|[.．·…]{3,}|[\uE000-\uF8FF]{3,}|[-—–_]{4,}).*$',
)
EMOJI_RE = re.compile(r'[\U0001F300-\U0001FAFF]')
KNOWN_OUTLINE_LABEL_RE = re.compile(
    r'^\s*\d+[.、]\s*(?:'
    r'逆|伴随矩阵|秩|高次幂|初等变换与初等矩阵|分块矩阵|矩阵分解|其他题型|'
    r'向量有关计算|线性表示|向量组等价|线性相关与无关|极大无关组|'
    r'解的判定|方程组求解|解的关系|矩阵方程|特征值特征向量|相似|'
    r'相似对角化|实对称矩阵|标准型|规范形|求二次型的解|求二次型最值|'
    r'正负惯性指数|合同|正定'
    r')\s*$',
)


SOURCE_LABELS = {
    'past_exam': 'Past exam',
    'adapted_exam': 'Adapted past exam',
    'mock_exam': 'Mock paper',
    'workbook': 'Workbook',
    'competition': 'Competition',
    'other_practice': 'Other practice',
    'unclassified': 'Unclassified',
}

REFERENCE_SOURCE_CATEGORIES = {
    'past_exam',
    'adapted_exam',
    'mock_exam',
    'workbook',
    'competition',
}
REFERENCE_TOPIC_RE = re.compile(
    r'^(?:\([A-Za-z]+\)\s*)?'
    r'(?:姜晓千(?:真题同源)?(?:基础|强化)?|[\u4e00-\u9fff]{2,12}大学)$'
)


@dataclass(frozen=True)
class SourceClassification:
    category: str
    is_past_exam: bool
    year: int | None
    variant: str
    display_label: str
    reason: str
    confidence: float


def _normalize_space(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()


def _strip_outline_prefix(value: str) -> str:
    return OUTLINE_PREFIX_RE.sub('', value, count=1).strip()


def _plain_source_label(value: str) -> str:
    value = LEADER_RE.sub('', value or '')
    value = value.replace('>>', ' ')
    value = _normalize_space(value)
    return _strip_outline_prefix(value) or value or 'Unlabelled question'


def _keep_emoji(raw: str, normalized_label: str) -> str:
    """Keep source-authored emoji when a past-exam label is normalized."""

    emoji = ''.join(EMOJI_RE.findall(raw or ''))
    return f'{emoji} {normalized_label}' if emoji else normalized_label


def _exam_metadata(label: str) -> tuple[int | None, str]:
    match = PAST_EXAM_RE.search(label or '')
    if match:
        variants = ''.join(dict.fromkeys(re.findall(r'[一二三]', match.group('variants'))))
        return int(match.group('year')), f'数{variants}'
    match = GENERIC_PAST_EXAM_RE.search(label or '')
    if match:
        return int(match.group('year')), ''
    return None, ''


def classify_source(label: str) -> SourceClassification:
    """Classify provenance conservatively; never infer an official exam from a book name."""

    raw = _normalize_space(label)
    year, variant = _exam_metadata(raw)
    display = _plain_source_label(raw)

    if COMPETITION_RE.search(raw):
        return SourceClassification(
            'competition', False, year, variant, display, 'competition marker', 0.98,
        )
    if MOCK_RE.search(raw):
        return SourceClassification(
            'mock_exam', False, year, variant, display, 'mock-paper marker', 0.96,
        )
    if year is not None and ADAPTED_RE.search(raw):
        exam_name = _keep_emoji(raw, f'{year} · {variant or "Past exam"} · Adapted')
        return SourceClassification(
            'adapted_exam', False, year, variant, exam_name, 'exam year plus adaptation marker', 0.98,
        )
    if year is not None:
        exam_name = _keep_emoji(raw, f'{year} · {variant or "Past exam"}')
        return SourceClassification(
            'past_exam', True, year, variant, exam_name, 'official exam year and variant', 0.99,
        )
    if WORKBOOK_RE.search(raw):
        return SourceClassification(
            'workbook', False, None, '', display, 'workbook or exercise-set marker', 0.96,
        )
    return SourceClassification(
        'unclassified', False, None, '', display, 'no reliable provenance marker', 0.35,
    )


def is_question_reference_topic(title: str) -> bool:
    """Return whether a TOC leaf names a question source rather than knowledge.

    Some answer-book bookmarks contain one leaf per exercise, for example
    ``880 ... #7`` or ``2019 Math I``.  They remain valuable provenance, but
    using them as similarity topics creates one heatmap cell per question.
    """

    value = clean_topic_title(title)
    if classify_source(value).category in REFERENCE_SOURCE_CATEGORIES:
        return True
    return bool(REFERENCE_TOPIC_RE.fullmatch(value))


def classify_source_with_context(label: str, topic_title: str = '') -> SourceClassification:
    """Classify visible practice rows using reviewed contextual evidence.

    This deliberately keeps the strict source-label classifier unchanged because
    the PDF parser uses its unclassified result to distinguish labels from body
    text. Context can promote an otherwise unknown row to a clearly marked mock
    set or workbook; the honest fallback is Other practice, never Past exam.
    """

    strict = classify_source(label)
    if strict.category != 'unclassified':
        return strict
    evidence = _normalize_space(f'{label} {topic_title}')
    if CONTEXT_MOCK_RE.search(evidence):
        return SourceClassification(
            'mock_exam', False, None, '', strict.display_label,
            'agent-reviewed mock-set marker in source/topic context', 0.92,
        )
    if WORKBOOK_RE.search(evidence) or CONTEXT_WORKBOOK_RE.search(evidence):
        return SourceClassification(
            'workbook', False, None, '', strict.display_label,
            'agent-reviewed workbook marker in source/topic context', 0.93,
        )
    return SourceClassification(
        'other_practice', False, None, '', strict.display_label,
        'agent-reviewed fallback: practice source without official provenance', 0.68,
    )


def clean_document_title(filename: str) -> str:
    """Return a concise subject name while retaining filename as provenance."""

    value = Path(filename).stem
    if '反常积分' in value:
        return '反常积分'
    if '一元积分' in value:
        return '一元积分'
    if '二重积分' in value:
        return '二重积分'
    if '多元微分' in value:
        return '多元微分'
    if '一元微分' in value:
        return '一元微分'
    if '微分方程' in value:
        return '微分方程'
    if '极限' in value:
        return '极限'
    if '线代' in value or '线性代数' in value:
        return '线性代数'
    value = re.sub(r'[（(]\d+[）)]$', '', value)
    value = re.sub(r'^【[^】]+】', '', value)
    return _normalize_space(value).strip('【】 ') or filename


def clean_topic_title(title: str) -> str:
    """Remove table-of-contents leaders/page numbers without changing raw title."""

    raw = _normalize_space(title)
    value = LEADER_RE.sub('', raw).replace('>>', ' ')
    value = re.sub(r'[\uE000-\uF8FF]+', ' ', value)
    value = _strip_outline_prefix(_normalize_space(value))
    compact = re.sub(r'\s+', '', value)
    if compact in {'框框dx框框dy', '□□dx□□dy'}:
        return '含 dx、dy 的微分方程（原目录符号未识别）'
    if compact in {'框框y撇', '□□y撇'}:
        return '含 y′ 的微分方程（原目录符号未识别）'
    return value or 'Unlabelled topic'


def classify_record_kind(
    *,
    source_category: str,
    source_label: str,
    prompt_text: str,
    asset_count: int,
    max_asset_height: int | None,
) -> tuple[str, bool, str, float]:
    """Separate high-confidence outline rows while keeping uncertain rows visible."""

    def comparable(value: str) -> str:
        return re.sub(r'[\s>]+', '', value or '').lower()

    label = comparable(source_label)
    prompt = comparable(prompt_text)
    same_heading = bool(label) and (label == prompt or prompt.startswith(label))
    small_single_crop = asset_count == 1 and (max_asset_height or 10_000) <= 95
    has_outline_marker = '>>' in (source_label or '') or '>>' in (prompt_text or '')
    short_multipage_heading = (
        same_heading
        and has_outline_marker
        and len(prompt) <= 32
        and asset_count <= 2
    )

    if KNOWN_OUTLINE_LABEL_RE.match(source_label or ''):
        return 'section', False, 'recognized source-outline heading', 0.99

    if (
        source_category == 'unclassified'
        and same_heading
        and (
            (small_single_crop and (has_outline_marker or len(label) <= 32))
            or short_multipage_heading
        )
    ):
        return 'section', False, 'small source-outline row without question provenance', 0.93
    if asset_count >= 4:
        return 'grouped', True, 'source parser grouped four or more crops', 0.9
    return 'question', True, 'atomic or conservatively retained question row', 0.8
