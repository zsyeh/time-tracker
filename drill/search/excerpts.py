"""Optional public-source excerpts; offsets are Unicode codepoints, never HTML.

Excerpts use the same normalized public text as the projection, so offsets stay
correct after NFKC/casefold/LaTeX normalization. No answer, Note or OCR invention.
"""
from .normalize import aliases, compact
from .postgres import FIELDS

KINDS = ('literal', 'alias', 'prefix', 'contains', 'spelling')


def search_match(plan, document):
    terms = document.terms
    concept_map = {row['canonical']: [*row['equivalents'], *[term for group in row.get('cooccurrence',[]) for term in group]] for row in aliases()}
    matched_fields, choices, tiers = [], [], []
    names = {'labels_norm': 'label', 'book_norm': 'book', 'topics_norm': 'topic',
             'body_norm': 'body', 'formula_norm': 'formula','direct_topics_norm':'topic'}
    def source(name):
        return document.coverage.get(name,'') if name=='direct_topics_norm' else getattr(document,name)
    for group in plan.groups:
        for variant in sorted(group, key=lambda item: item.tier):
            if not all(key in terms for key in variant.keys):
                continue
            if variant.phrase and not any(variant.phrase in source(name) for name, _, _ in FIELDS):
                continue
            tiers.append(variant.tier)
            if all(key.startswith('id:') for key in variant.keys):
                value = variant.keys[0][3:]
                matched_fields.append('identifier')
                choices.append((0, value, [(0, len(value))]))
            for name, bit, weight in FIELDS:
                text = source(name)
                if variant.field=='formula' and bit!=16:
                    continue
                if not all(terms[key] & bit for key in variant.keys) or (variant.phrase and variant.phrase not in text):
                    continue
                matched_fields.append(names[name])
                needles = [variant.phrase] if variant.phrase else []
                for key in variant.keys:
                    kind, token = key.split(':', 1)
                    if kind == 'concept':
                        needles.extend(compact(alias) for alias in concept_map[token])
                    elif kind == 'macro':
                        needles.append('\\' + token)
                    elif kind == 'math' and token == 'frac':
                        needles.append('\\frac')
                    elif kind != 'id':
                        needles.append(token)
                # Replace only the separator, preserving codepoint positions.
                text = text.replace('\x1f', ' ')
                spans = []
                for needle in set(needles):
                    start = text.find(needle) if needle else -1
                    if start >= 0:
                        spans.append((start, start + len(needle)))
                if spans:
                    choices.append((6 - weight, text, spans))
            break
    coverage = 'text' if document.coverage.get('has_prompt') or document.coverage.get('has_latex') else 'metadata'
    result = {'fields': list(dict.fromkeys(matched_fields)), 'kind': KINDS[max(tiers, default=0)],
              'excerpt': '', 'highlights': [], 'coverage': coverage}
    if choices:
        _, text, spans = min(choices, key=lambda item: item[0])
        start = max(0, min(span[0] for span in spans) - 40)
        excerpt = text[start:start + 160]
        ranges = sorted((max(0, left-start), min(len(excerpt), right-start)) for left, right in spans
                        if right > start and left < start + len(excerpt))
        merged = []
        for left, right in ranges:
            if merged and left <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], right)
            else:
                merged.append([left, right])
        result.update(excerpt=excerpt, highlights=merged)
    return result
