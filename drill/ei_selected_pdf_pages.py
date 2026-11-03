"""Absolute page references for the immutable 2026-10-29 EI selected PDF set."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _pages():
    path = Path(__file__).parent / 'data/ei_selected_pdf_pages_v1.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    if data['schema_version'] != 1:
        raise ValueError('Unsupported EI PDF page map')
    return data['questions']


def pdf_pages_for(question):
    """Return only a page map whose UUID and fingerprint match the live question."""
    row = _pages().get(str(question.uuid))
    if not row or row['fingerprint'] != question.fingerprint:
        return None
    return {
        'course': row['course'],
        'question': row['question'],
        'answer': row['answer'],
        'paired': row['paired'],
    }


COURSE_LABELS = {
    'circuit': '电路',
    'signal': '信号与系统',
    'analog': '模拟电子技术',
    'digital': '数字电子技术',
    'communication': '通信原理',
}


def pdf_page_catalog():
    """Describe the immutable source workbooks without exposing question data."""
    rows = list(_pages().values())
    result = []
    for code, label in COURSE_LABELS.items():
        course_rows = [row for row in rows if row['course'] == code]
        result.append({
            'code': code,
            'label': label,
            'question_max_page': max((row['question'] for row in course_rows), default=0),
            'paired_max_page': max((row['paired'] for row in course_rows), default=0),
        })
    return result


@lru_cache(maxsize=1)
def selected_question_fingerprints():
    """Authoritative allowlist: page import is never available to the standard bank."""
    from . import (
        analog_selected, circuit_selected, communication_selected,
        digital_selected, signal_selected,
    )
    modules = {
        'circuit': circuit_selected,
        'signal': signal_selected,
        'analog': analog_selected,
        'digital': digital_selected,
        'communication': communication_selected,
    }
    return {
        course: {
            row['uuid']: row['fingerprint']
            for row in module.manifest()['questions']
            if row.get('status') == 'included'
        }
        for course, module in modules.items()
    }


def pdf_page_rows(course, question_pages, paired_pages):
    """Return rows selected independently from question and paired Q&A books."""
    selected = {}
    question_hits = set()
    paired_hits = set()
    allowlist = selected_question_fingerprints().get(course, {})
    for question_uuid, row in _pages().items():
        if row['course'] != course:
            continue
        # The UUID and fingerprint must both occur in that course's immutable
        # selected manifest. A standard-bank row can never be imported here.
        if allowlist.get(question_uuid) != row['fingerprint']:
            continue
        matched_by = []
        if row['question'] in question_pages:
            matched_by.append({'book': 'question', 'page': row['question']})
            question_hits.add(row['question'])
        if row['paired'] in paired_pages:
            matched_by.append({'book': 'paired', 'page': row['paired']})
            paired_hits.add(row['paired'])
        if matched_by:
            selected[question_uuid] = {'row': row, 'matched_by': matched_by}
    return selected, question_hits, paired_hits
