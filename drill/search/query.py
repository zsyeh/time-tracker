"""Small, parameter-only query AST shared by PostgreSQL and the reference matcher."""
from dataclasses import dataclass, field
import re
import uuid
from .normalize import HAN, TOKEN_RE, aliases, compact, identifier, formula, formula_terms, prose


class SearchQueryError(ValueError):
    code = 'SEARCH_QUERY_TOO_COMPLEX'


@dataclass(frozen=True)
class Variant:
    keys: tuple
    tier: int = 0
    phrase: str = ''
    field: str = ''


@dataclass(eq=False)
class QueryPlan:
    raw: str
    normalized: str
    groups: list = field(default_factory=list)
    exact_identifier: str = ''
    corrected_terms: list = field(default_factory=list)

    @property
    def empty(self):
        return not self.groups


def literal_variant(token, tier=0):
    if re.fullmatch(f'[{HAN}]+', token):
        keys = ('zh1:'+token,) if len(token) == 1 else tuple('zh2:'+token[i:i+2] for i in range(len(token)-1))
        return Variant(keys, tier, token if len(token) >= 3 else '')
    return Variant(('en:'+token,), tier)


def parse_query(raw):
    raw = str(raw or '').strip()
    if '\x00' in raw or any(0xD800 <= ord(c) <= 0xDFFF for c in raw):
        raise SearchQueryError('Invalid Unicode query.')
    if len(raw) > 120:
        raise SearchQueryError('Queries are limited to 120 Unicode characters.')
    plan = QueryPlan(raw, compact(raw))
    try:
        parsed_uuid = str(uuid.UUID(raw))
    except ValueError:
        parsed_uuid = ''
    if parsed_uuid:
        plan.exact_identifier = parsed_uuid
        plan.groups = [[Variant(('id:'+parsed_uuid,))]]
        return plan
    possible_id=identifier(raw)
    if re.fullmatch(r'[\w]+(?:[.\-][\w]+)*', possible_id, re.UNICODE) and any(c.isdigit() for c in possible_id):
        plan.exact_identifier = possible_id
        plan.normalized = compact(possible_id)
    math_terms = formula_terms(raw)
    # A single mathematical query is exact, with macro/symbol equivalence.
    if math_terms and (re.search(r'\\|[_^⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉∂∫∑∞πΠ]', raw) or re.fullmatch(r'\w\s*\(\s*\w\s*\)', raw)):
        plan.exact_identifier=''
        plan.normalized=formula(raw)
        # Coarse macro/symbol/atom recall plus exact normalized expression
        # containment. Never replace a complete formula with an incidental atom.
        coarse = sorted(t for t in math_terms if not t.startswith('expr:')) or sorted(math_terms)
        plan.groups = [[Variant(tuple(coarse), phrase=plan.normalized, field='formula')]]
        return plan
    # Explicit query whitespace separates concepts; only indexed PDF text uses
    # Han whitespace compaction. This also allows concepts in separate tags.
    remaining = prose(possible_id if plan.exact_identifier else raw)
    # Longest aliases first prevents Fourier transform from becoming a generic Fourier query.
    candidates = sorted([(compact(a), row) for row in aliases() for a in row['equivalents']], key=lambda item: -len(item[0]))
    while remaining.strip():
        remaining = remaining.lstrip()
        hit = None
        for term, row in candidates:
            if remaining.startswith(term) and not (term[-1].isascii() and term[-1].isalnum() and len(remaining) > len(term) and remaining[len(term)].isascii() and remaining[len(term)].isalnum()):
                hit = (term, row)
                break
        if hit:
            term, row = hit
            # The literal phrase and alias concept use different tiers.
            literal_keys = tuple(k for token in TOKEN_RE.findall(term) for k in literal_variant(token).keys)
            plan.groups.append([Variant(literal_keys, 0, term), Variant(('concept:'+row['canonical'],), 1)])
            remaining = remaining[len(term):]
        else:
            match = TOKEN_RE.match(remaining)
            if not match:
                remaining = remaining[1:]
                continue
            token = match[0]
            # Split unknown Chinese at an upcoming known concept, without losing the prefix.
            if re.fullmatch(f'[{HAN}]+', token):
                starts = [token.find(term) for term, _ in candidates if token.find(term) > 0]
                if starts:
                    token = token[:min(starts)]
            variants = [literal_variant(token)]
            # Only explicitly reviewed Chinese misspellings auto-expand, at the
            # lowest tier. Arbitrary short Han terms retain exact semantics.
            for concept in aliases():
                if token in {compact(typo) for typo in concept.get('common_typos',[])} and re.fullmatch(f'[{HAN}]+',token):
                    variants.append(Variant(('concept:'+concept['canonical'],),4))
                    plan.corrected_terms.append(next((compact(alias) for alias in concept['equivalents'] if re.fullmatch(f'[{HAN}]+',compact(alias))),compact(concept['equivalents'][0])))
            if token.isascii() and len(token) >= 2:
                if len(token) <= 48:
                    variants.append(Variant(('enpre:'+token,), 2))
                else:
                    variants.append(Variant(tuple('en3:'+token[i:i+3] for i in range(len(token)-2)), 2, token))
                if len(token) >= 3:
                    variants.append(Variant(tuple('en3:'+token[i:i+3] for i in range(len(token)-2)), 3, token))
            plan.groups.append(variants)
            remaining = remaining[len(token):]
        if len(plan.groups) > 12:
            raise SearchQueryError('Queries are limited to 12 concepts.')
    # A printed identifier is an alternative to prose, never question_order.
    if plan.exact_identifier and len(plan.groups) == 1:
        plan.groups[0].insert(0, Variant(('id:'+plan.exact_identifier,)))
    return plan


def private_matches(plan, *values, _prefilter=True):
    """Request-local compiled matcher. No cross-request plaintext/result cache."""
    from .normalize import formula_terms
    if not plan.groups:
        return False
    if _prefilter:
        from .private import private_candidate
        if not private_candidate(plan,values):
            return False
    compiled = getattr(plan, '_private_groups', None)
    if compiled is None:
        concept_map = {row['canonical']: row for row in aliases()}
        def phrase_regex(term, prefix=False):
            term = compact(term)
            left = r'(?<![a-z0-9])' if term and term[0].isascii() and term[0].isalnum() else ''
            right = r'(?![a-z0-9])' if not prefix and term and term[-1].isascii() and term[-1].isalnum() else ''
            return re.compile(left+re.escape(term)+right)
        compiled=[]
        for group in plan.groups:
            variants=[]
            for variant in group:
                checks=[]
                for key in variant.keys:
                    kind, token = key.split(':', 1)
                    if kind in ('zh1','zh2','en3'):
                        checks.append(('contains',token))
                    elif kind in ('en','enpre'):
                        checks.append(('regex',phrase_regex(token,kind=='enpre')))
                    elif kind=='concept':
                        concept=concept_map[token]
                        checks.append(('concept',([phrase_regex(alias) for alias in concept['equivalents']],
                            [[phrase_regex(term) for term in group] for group in concept.get('cooccurrence',[])])))
                    elif kind=='id':
                        checks.append(('id',token))
                    else:
                        checks.append(('math',key))
                variants.append((variant.phrase,checks,variant.field))
            compiled.append(variants)
        plan._private_groups=compiled
    fields = [(compact(value), value) for value in values if value]
    def matches_variant(variant, norm, raw):
        phrase,checks,field_name=variant
        if phrase and phrase not in (formula(raw) if field_name=='formula' else norm):
            return False
        for kind, value in checks:
            if kind=='contains':matched=value in norm
            elif kind=='regex':matched=bool(value.search(norm))
            elif kind=='concept':matched=any(regex.search(norm) for regex in value[0]) or any(
                all(regex.search(norm) for regex in group) for group in value[1])
            elif kind=='id':matched=identifier(raw)==value
            else:matched=value in formula_terms(raw)
            if not matched:return False
        return True
    return all(any(matches_variant(variant,norm,raw) for variant in group for norm,raw in fields)
               for group in compiled)
