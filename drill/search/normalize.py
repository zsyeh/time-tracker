"""Pure Unicode/educational-text normalization; no TeX execution or source writes."""
import hashlib
import html
import json
import re
import unicodedata
import uuid
from functools import lru_cache
from pathlib import Path

NORMALIZER_VERSION = 2
SEPARATOR = '\x1f'
HAN = r'\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0003134f'
TOKEN_RE = re.compile(rf'[{HAN}]+|[a-z0-9]+(?:[.\-][a-z0-9]+)*')
LATIN_RE = re.compile(r'[a-z]+')
SUPERSCRIPTS = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ', '0123456789+-=()ni')
SUBSCRIPTS = str.maketrans('₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎', '0123456789+-=()')
MATH_MACROS = {'frac':'frac','dfrac':'frac','tfrac':'frac','partial':'∂','int':'∫','sum':'∑','infty':'∞',
 'pi':'π','Pi':'Π','alpha':'α','beta':'β','gamma':'γ','Gamma':'Γ','theta':'θ','Theta':'Θ',
 'delta':'δ','Delta':'Δ','omega':'ω','Omega':'Ω','sigma':'σ','Sigma':'Σ','lambda':'λ','mu':'μ'}


def prose(value):
    value = html.unescape(str(value or ''))
    value = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', value)
    value = re.sub(r'<[^>]*>', ' ', value)
    value = value.replace('`', '').replace('**', '').replace('__', '')
    value = unicodedata.normalize('NFKC', value).casefold()
    value = ''.join(c for c in value if unicodedata.category(c) != 'Cf')
    return re.sub(r'\s+', ' ', value).strip()


def compact(value):
    # Only remove whitespace between Han characters; Latin word boundaries remain.
    return re.sub(f'(?<=[{HAN}])\\s+(?=[{HAN}])', '', prose(value))


def identifier(value):
    value = unicodedata.normalize('NFKC', str(value or '')).strip()
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError):
        return re.sub(r'\s*([.\-])\s*', r'\1', value).casefold()


def formula(value):
    value = str(value or '').replace('−', '-')
    value = re.sub(r'[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ]+', lambda m: '^{'+m[0].translate(SUPERSCRIPTS)+'}', value)
    value = re.sub(r'[₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎]+', lambda m: '_{'+m[0].translate(SUBSCRIPTS)+'}', value)
    value = re.sub(r'\\(?:left|right|displaystyle|textstyle)\b|\\[,;! ]', '', value)
    value = re.sub(r'\\(?:mathrm|operatorname|text)\s*\{([^{}]*)\}', r'\1', value)
    value = re.sub(r'\\([a-zA-Z]+)', lambda m: ('\\frac' if MATH_MACROS.get(m[1], m[1]) == 'frac' else MATH_MACROS.get(m[1], '\\'+m[1])), value)
    value = re.sub(r'([_^])\s*([a-zA-Z0-9])\b', r'\1{\2}', value)
    return re.sub(r'\s+', '', value).strip('$')


def formula_terms(value):
    raw = str(value or '')
    result = set()
    for macro in re.findall(r'\\([a-zA-Z]+)', raw):
        if macro in {'left','right','mathrm','operatorname','text','displaystyle','textstyle'}:
            continue
        result.add('math:'+MATH_MACROS[macro] if macro in MATH_MACROS else 'macro:'+macro)
    for symbol in '∂∫∑∞πΠαβγΓθΘδΔωΩσΣλμ':
        if symbol in raw:
            result.add('math:'+symbol)
    for part in re.findall(r'\${1,2}([^$]+)\${1,2}|([a-zA-Z](?:\s*[_^]\s*(?:\{[^}]+\}|\w)|[⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉])+)|([a-zA-Z]\s*\(\s*[a-zA-Z]\s*\))', raw):
        result.add('expr:'+formula(next(p for p in part if p)))
    # Independently index atoms inside math blocks; the block alternative above
    # otherwise consumes x^2 inside $x^2+1$. Do not take the tail of a TeX macro
    # (for example a_p from \omega_p) as an independent Latin variable.
    atom=r'(?<![a-zA-Z\\])(?:\\[a-zA-Z]+|[a-zA-Z])(?:\s*[_^]\s*(?:\{[^}]+\}|\w)|[⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉])+'
    for part in re.findall(atom,raw):
        result.add('expr:'+formula(part))
    for part in re.findall(r'(?<![a-zA-Z\\])[a-zA-Z]\s*\(\s*[a-zA-Z]\s*\)',raw):
        result.add('expr:'+formula(part))
    return result


@lru_cache(maxsize=1)
def aliases():
    return json.loads((Path(__file__).resolve().parent.parent/'data/search_aliases_v1.json').read_text())['concepts']


def aliases_hash():
    return hashlib.sha256(json.dumps(aliases(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def phrase_present(text, phrase):
    phrase = compact(phrase)
    if not phrase:
        return False
    # Latin aliases must be complete words; 'z' must not match a random word.
    left = r'(?<![a-z0-9])' if phrase[0].isascii() and phrase[0].isalnum() else ''
    right = r'(?![a-z0-9])' if phrase[-1].isascii() and phrase[-1].isalnum() else ''
    return bool(re.search(left+re.escape(phrase)+right, text))


def text_terms(value):
    norm = compact(value)
    terms = set()
    for token in TOKEN_RE.findall(norm):
        if re.fullmatch(f'[{HAN}]+', token):
            terms.update('zh1:'+c for c in token)
            terms.update('zh2:'+token[i:i+2] for i in range(len(token)-1))
        else:
            terms.add('en:'+token)
            terms.update('enpre:'+token[:n] for n in range(2, min(len(token), 48)+1))
            terms.update('en3:'+token[i:i+3] for i in range(len(token)-2))
            # Hyphenated ordinary words have both exact and constituent terms.
            terms.update('en:'+word for word in re.findall(r'[a-z0-9]+', token))
    for row in aliases():
        if any(phrase_present(norm, alias) for alias in row['equivalents']) or any(
                all(phrase_present(norm, term) for term in group) for group in row.get('cooccurrence', [])):
            terms.add('concept:'+row['canonical'])
    terms.update(formula_terms(value))
    return terms


def edit_distance(a, b):
    """Optimal string alignment distance, including adjacent transposition."""
    rows = [list(range(len(b)+1))]
    for i, ca in enumerate(a, 1):
        row = [i]
        for j, cb in enumerate(b, 1):
            value = min(row[j-1]+1, rows[-1][j]+1, rows[-1][j-1]+(ca != cb))
            if i > 1 and j > 1 and ca == b[j-2] and a[i-2] == cb:
                value = min(value, rows[-2][j-2]+1)
            row.append(value)
        rows.append(row)
    return rows[-1][-1]
