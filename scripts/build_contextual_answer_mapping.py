#!/usr/bin/env python3
"""Generate conservative answer-PDF mappings without trusting list order.

The answer books primarily contain rendered solutions, but retain source labels
next to each solution.  This command indexes those labels and compares them to
the imported question label *and* a short prompt anchor.  It deliberately emits
only unique high-confidence matches; the rest remain in an audit report.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from statistics import median
from pathlib import Path

import django
import pymupdf


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time_server.settings")
sys.path.insert(0, str(ROOT))

SOURCE_ROOT = ROOT / "work" / "answer_sources"
OUT = ROOT / "work" / "answer_mapping_contextual.jsonl"
AUDIT = ROOT / "reports" / "contextual_answer_mapping_report.json"
DOCUMENT_PDFS = {
    1: "极限答案册.pdf",
    2: "一元积分题库-答案.pdf",
    3: "线代1000题参考答案.pdf",
    4: "二重积分题库答案.pdf",
    5: "多元微分大观-答案.pdf",
    6: "微分方程大观-答案.pdf",
    7: "反常积分-答案.pdf",
    9: "一元微分大观-答案.pdf",
}

LABEL_MARKER = re.compile(r">>")
LEADING_ENUMERATOR = re.compile(
    r"^\s*(?:[a-zivxlcdm]+\s*\)|\(?\s*\d+\s*\)?[.、)]?)\s*",
    re.IGNORECASE,
)
SOURCE_ANCHOR = re.compile(
    r"(?:(?:19|20)\d{2}\s*数\s*[一二三]|"
    r"(?:25|26)\s*版?\s*(?:🐙)?\s*(?:0\.1w|880|900|660|1000)[^;；>>]{0,28}|"
    r"姜晓千[^;；>>]{0,28}|李艳芳[^;；>>]{0,28})",
    re.IGNORECASE,
)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    value = value.replace("✖", "x").replace("×", "x").replace("∞", "infty")
    value = value.replace("数=", "数二").replace("0.1w", "01w")
    return "".join(re.findall(r"[a-z0-9\u4e00-\u9fff]+", value))


def label_variants(value: str) -> set[str]:
    raw = (value or "").replace(">>", " ").strip()
    variants = {normalize(raw)}
    stripped = LEADING_ENUMERATOR.sub("", raw)
    variants.add(normalize(stripped))
    # Labels copied from the compact question PDF occasionally carry a second
    # source in one record.  Each source is valid evidence independently.
    for part in re.split(r"[;；]", stripped):
        variants.add(normalize(part))
    for anchor in SOURCE_ANCHOR.findall(stripped):
        variants.add(normalize(anchor))
    return {item for item in variants if len(item) >= 5}


def prompt_anchor(value: str) -> str:
    value = normalize(value)
    # Math glyph extraction is frequently corrupt.  Keep Chinese/ASCII prose
    # around the beginning of the prompt as supporting, never sole, evidence.
    return value[:80] if len(value) >= 12 else ""


def similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    sequence = difflib.SequenceMatcher(None, left, right, autojunk=False).ratio()
    left_grams = {left[index:index + 3] for index in range(max(1, len(left) - 2))}
    right_grams = {right[index:index + 3] for index in range(max(1, len(right) - 2))}
    grams = len(left_grams & right_grams) / max(1, len(left_grams | right_grams))
    return 0.72 * sequence + 0.28 * grams


def page_labels(document: pymupdf.Document):
    """Return solution-label blocks, excluding each book's table of contents."""
    labels = []
    for page_index, page in enumerate(document):
        page_text = page.get_text("text", sort=True)
        if "目录" in page_text and page_text.count(">>") >= 2:
            continue
        for block in page.get_text("blocks", sort=True):
            text = block[4].strip().replace("\n", " ")
            if not LABEL_MARKER.search(text):
                continue
            compact = normalize(text)
            if len(compact) < 5:
                continue
            labels.append({
                "page_index": page_index + 1,
                "y0": round(float(block[1]), 3),
                "text": text,
                "variants": label_variants(text),
                "prompt": prompt_anchor(text),
                "page_context": normalize(page_text),
                "height": float(page.rect.height),
                "width": float(page.rect.width),
            })
    return labels


def topic_terms(question) -> set[str]:
    terms = set()
    topic = question.topic
    visited = set()
    while topic is not None and topic.pk not in visited:
        visited.add(topic.pk)
        term = normalize(topic.display_title or topic.title)
        if len(term) >= 4:
            terms.add(term)
        topic = topic.parent
    return terms


def build_label_index(candidates):
    index = defaultdict(set)
    for position, candidate in enumerate(candidates):
        for variant in candidate["variants"]:
            for offset in range(max(1, len(variant) - 4)):
                index[variant[offset:offset + 5]].add(position)
    return index


def best_match(question, candidates, label_index, topic_page_priors):
    variants = label_variants(question.source_label)
    if not variants:
        return None
    candidate_positions = set()
    for variant in variants:
        for offset in range(max(1, len(variant) - 4)):
            candidate_positions.update(label_index.get(variant[offset:offset + 5], ()))
    # Do not compare a question to every label in a 600-page book.  A shared
    # five-character source anchor is necessary evidence for a fuzzy match.
    if not candidate_positions:
        return None
    question_prompt = prompt_anchor(question.prompt_text)
    scored = []
    for position in candidate_positions:
        candidate = candidates[position]
        label_score = max(
            (similarity(left, right) for left in variants for right in candidate["variants"]),
            default=0.0,
        )
        prompt_score = similarity(question_prompt, candidate["prompt"]) if question_prompt else 0.0
        # Prompt score is supporting only, since most answer PDFs omit it.
        score = label_score + min(0.025, prompt_score * 0.025)
        scored.append((score, label_score, candidate))
    scored.sort(key=lambda row: row[0], reverse=True)
    if not scored:
        return None
    best = scored[0]
    runner_up = scored[1] if len(scored) > 1 else None
    margin = best[0] - (runner_up[0] if runner_up else 0.0)
    # Exact normalized source-label match is safe.  Fuzzy candidates need both
    # a stronger score and a clear margin from their next nearest label.
    exact_positions = [
        position for position in candidate_positions
        if any(left == right for left in variants for right in candidates[position]["variants"])
    ]
    terms = topic_terms(question)
    contextual_exact_positions = [
        candidate_position for candidate_position in exact_positions
        if any(term in candidates[candidate_position]["page_context"] for term in terms)
    ]
    topic_prior = topic_page_priors.get(question.topic_id)
    prior_unique = False
    if len(exact_positions) > 1 and topic_prior is not None:
        center, spread = topic_prior
        distances = sorted(
            (abs(candidates[candidate_position]["page_index"] - center), candidate_position)
            for candidate_position in exact_positions
        )
        if (
            spread <= 18
            and distances[0][0] <= 28
            and distances[1][0] - distances[0][0] >= 10
            and candidates[distances[0][1]] is best[2]
        ):
            prior_unique = True
    # An exact year/source anchor is useful only when it occurs once in this
    # answer book.  Repeated labels must remain for review.
    exact_unique = len(exact_positions) == 1 and candidates[exact_positions[0]] is best[2]
    contextual_exact_unique = (
        len(contextual_exact_positions) == 1
        and candidates[contextual_exact_positions[0]] is best[2]
    )
    accepted = exact_unique or contextual_exact_unique or prior_unique or (best[1] >= 0.965 and margin >= 0.055)
    return {
        "accepted": accepted,
        "score": round(best[0], 4),
        "label_score": round(best[1], 4),
        "margin": round(margin, 4),
        "candidate": best[2],
    }


def regions_for(candidate, boundaries, page_counts):
    start = (candidate["page_index"], candidate["y0"])
    following = next((item for item in boundaries if item > start), None)
    end_page, end_y = following or (page_counts, candidate["height"])
    regions = []
    for page_number in range(start[0], end_page + 1):
        y0 = start[1] if page_number == start[0] else 0.0
        y1 = end_y if page_number == end_page else candidate["height"]
        if y1 - y0 > 2:
            regions.append({
                "page_index": page_number,
                "x0": 0.0,
                "y0": round(y0, 3),
                "x1": round(candidate["width"], 3),
                "y1": round(y1, 3),
            })
    return regions


def main():
    django.setup()
    from drill.models import Question, QuestionAsset

    answered = QuestionAsset.objects.filter(asset_type="answer_crop").values_list("question_id", flat=True)
    pages_by_topic = defaultdict(list)
    for topic_id, page_index in QuestionAsset.objects.filter(
        asset_type="answer_crop", question__topic__isnull=False,
    ).values_list("question__topic_id", "source_page_index"):
        if page_index is not None:
            pages_by_topic[topic_id].append(page_index + 1)
    topic_page_priors = {
        topic_id: (median(pages), max(pages) - min(pages))
        for topic_id, pages in pages_by_topic.items()
        if len(pages) >= 3
    }
    questions = list(
        Question.objects.exclude(id__in=answered)
        .filter(document_id__in=DOCUMENT_PDFS, record_kind="question")
        .select_related("document")
        .order_by("document_id", "question_order")
    )
    labels_by_document = {}
    label_indices = {}
    page_counts = {}
    for document_id, filename in DOCUMENT_PDFS.items():
        with pymupdf.open(SOURCE_ROOT / filename) as source:
            labels_by_document[document_id] = page_labels(source)
            label_indices[document_id] = build_label_index(labels_by_document[document_id])
            page_counts[document_id] = len(source)

    rows = []
    rejected = []
    used_starts = set()
    for question in questions:
        result = best_match(
            question,
            labels_by_document[question.document_id],
            label_indices[question.document_id],
            topic_page_priors,
        )
        if not result or not result["accepted"]:
            rejected.append({
                "question_uuid": str(question.uuid),
                "document": question.document.display_title,
                "order": question.question_order,
                "label": question.source_label,
                "best_score": result["score"] if result else 0,
                "margin": result["margin"] if result else 0,
            })
            continue
        candidate = result["candidate"]
        start_key = (question.document_id, candidate["page_index"], candidate["y0"])
        if start_key in used_starts:
            rejected.append({
                "question_uuid": str(question.uuid), "document": question.document.display_title,
                "order": question.question_order, "label": question.source_label,
                "best_score": result["score"], "margin": result["margin"], "reason": "duplicate_solution_start",
            })
            continue
        used_starts.add(start_key)
        all_boundaries = sorted({(item["page_index"], item["y0"]) for item in labels_by_document[question.document_id]})
        rows.append({
            "question_uuid": str(question.uuid),
            "source_pdf": DOCUMENT_PDFS[question.document_id],
            "crop_regions": regions_for(candidate, all_boundaries, page_counts[question.document_id]),
            "match_confidence": 0.99 if result["label_score"] >= 0.999 else 0.985,
            "review_required": False,
            "match_method": "contextual_label_and_prompt_unique",
            "matched_answer_label": candidate["text"],
            "label_score": result["label_score"],
            "score_margin": result["margin"],
        })

    OUT.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")
    AUDIT.write_text(json.dumps({
        "eligible_unanswered_questions": len(questions),
        "accepted": len(rows),
        "unmatched_or_ambiguous": len(rejected),
        "rejected_sample": rejected[:100],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"accepted": len(rows), "rejected": len(rejected), "output": str(OUT), "audit": str(AUDIT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
