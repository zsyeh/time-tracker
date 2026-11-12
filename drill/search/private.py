"""Lossless ephemeral PostgreSQL prefilter for owner-scoped plaintext archives.

This is NOT a text index or the final matcher. ASCII and basic Han source text
cannot invent a query's required literal characters when Markdown is removed.
Anything outside that proven alphabet (including fullwidth/casefold expansions),
or containing HTML entities, passes unchanged to the Python Unicode matcher.
Formula/identifier variants also pass through. False positives are intentional;
there are no candidate caps and encrypted values never enter this expression.
"""
from django.db.models import BooleanField, Expression, F
from .normalize import aliases, compact
import re

# Choosing two necessary characters reduces work, never changes membership.
RARE_ASCII = 'zqxjkvbpfwyghmducrolnetsa0123456789-.'
UNSAFE_PRIVATE_SOURCE = re.compile(r'[^\x01-\x7f一-鿿]|&')


def necessary_character_groups(plan):
    """Query-only necessary conditions; None means no safe exclusion."""
    concepts={row['canonical']:[*row['equivalents'], *[' '.join(group) for group in row.get('cooccurrence',[])]] for row in aliases()}
    result=[]
    for group in plan.groups:
        choices=[]
        uncertain=False
        for variant in group:
            texts=['']
            for key in variant.keys:
                kind,token=key.split(':',1)
                if kind=='concept':
                    texts=[compact(alias) for alias in concepts[token]]
                    break
                if kind not in {'en','enpre','en3','zh1','zh2'}:
                    uncertain=True;break
                texts=[text+token for text in texts]
            if uncertain:break
            for text in texts:
                chars={c for c in text if c.isascii() and c.isalnum() or '\u4e00'<=c<='\u9fff'}
                if not chars:
                    uncertain=True;break
                choices.append(tuple(sorted(chars,key=lambda c:(0 if '\u4e00'<=c<='\u9fff' else 1,RARE_ASCII.find(c) if c in RARE_ASCII else 99,c))[:2]))
            if uncertain:break
        result.append(None if uncertain else choices)
    return result


def private_candidate(plan,values):
    """Ephemeral post-decryption superset; no private plaintext is retained."""
    source=' '.join(str(value) for value in values if value)
    if UNSAFE_PRIVATE_SOURCE.search(source):
        return True
    anchors=getattr(plan,'_private_anchors',None)
    if anchors is None:
        anchors=necessary_character_groups(plan)
        plan._private_anchors=anchors
    folded=source.lower()
    return all(choices is None or any(all(char in folded for char in required) for required in choices) for choices in anchors)


class PrivateTextCandidate(Expression):
    def __init__(self,plan,fields):
        super().__init__(output_field=BooleanField())
        self.plan=plan
        self.parts=[F(field) for field in fields]
    def get_source_expressions(self):return self.parts
    def set_source_expressions(self,parts):self.parts=parts
    def as_sql(self,compiler,connection):
        if connection.vendor!='postgresql' or not self.plan.groups:
            return 'TRUE',[]
        columns=[compiler.compile(part)[0] for part in self.parts]
        joined="concat_ws(' ',"+','.join(columns)+')'
        folded=f'lower({joined} COLLATE "C")'
        concept_map={row['canonical']:[*row['equivalents'], *[' '.join(group) for group in row.get('cooccurrence',[])]] for row in aliases()}
        groups,params=[],[]
        for group in self.plan.groups:
            choices=[]
            group_params=[]
            for variant in group:
                texts=['']
                for key in variant.keys:
                    kind,token=key.split(':',1)
                    if kind=='concept':
                        texts=[compact(alias) for alias in concept_map[token]]
                        break
                    if kind not in {'en','enpre','en3','zh1','zh2'}:
                        texts=None;break
                    texts=[text+token for text in texts]
                if texts is None:
                    choices=['TRUE'];group_params=[];break
                for text in texts:
                    chars=set(c for c in text if c.isascii() and c.isalnum() or '\u4e00'<=c<='\u9fff')
                    if not chars:
                        choices=['TRUE'];group_params=[];break
                    required=sorted(chars,key=lambda c:(0 if '\u4e00'<=c<='\u9fff' else 1,RARE_ASCII.find(c) if c in RARE_ASCII else 99,c))[:2]
                    choices.append('('+' AND '.join(f'strpos({folded}, %s)>0' for _ in required)+')')
                    group_params.extend(required)
            groups.append('('+' OR '.join(choices)+')')
            params.extend(group_params)
        # The regexp is a constant alphabet check, never user-supplied regexp.
        unsafe=f"(({joined} COLLATE \"C\") ~ '[^\\x01-\\x7f一-鿿]' OR strpos({joined}, '&')>0)"
        return '('+unsafe+' OR ('+' AND '.join(groups)+'))',params
