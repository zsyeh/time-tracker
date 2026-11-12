"""Parameterized SQL expression compiler. JSON keys are data, never SQL names."""
from django.db.models import BooleanField, Expression, F, IntegerField
from django.db.models.fields.json import KeyTextTransform

FIELDS = (('labels_norm',1,6),('book_norm',2,4),('topics_norm',4,1),('body_norm',8,3),('formula_norm',16,3),('direct_topics_norm',64,5))


class SearchExpression(Expression):
    def __init__(self, plan, operation='matches', prefix='search_document__'):
        super().__init__(output_field=BooleanField() if operation == 'matches' else IntegerField())
        self.plan, self.operation = plan, operation
        self.parts = [F(prefix+'terms'), *[KeyTextTransform('direct_topics_norm',F(prefix+'coverage'))
            if name=='direct_topics_norm' else F(prefix+name) for name, _, _ in FIELDS]]

    def get_source_expressions(self):
        return self.parts

    def set_source_expressions(self, expressions):
        self.parts = expressions

    def as_sql(self, compiler, connection):
        # JSON path params are fixed component metadata, never user input. Use a
        # fixed quoted key here to avoid repeating F-expression bind parameters
        # each time a scoring expression references this generated column.
        columns=[]
        for part in self.parts:
            if isinstance(part,KeyTextTransform):
                base,_=compiler.compile(part.lhs)
                columns.append(f"({base}->>'direct_topics_norm')" if connection.vendor=='postgresql' else f"json_extract({base}, '$.direct_topics_norm')")
            else:
                columns.append(compiler.compile(part)[0])
        terms = columns[0]
        def mask(key, bit):
            if connection.vendor == 'postgresql':
                return f"((COALESCE(({terms}->>%s)::integer,0) & {bit}) <> 0)", [key]
            return f"((COALESCE(json_extract({terms}, %s),0) & {bit}) <> 0)", ['$.'+'"'+key.replace('"','\\"')+'"']
        def variant_sql(variant, bit=None, col=None):
            if variant.field=='formula' and bit is not None and bit!=16:
                return 'FALSE',[]
            params, clauses = [], []
            if bit is None:
                if connection.vendor == 'postgresql':
                    clauses.append(f'{terms} ?& %s::text[]'); params.append(list(variant.keys))
                else:
                    for key in variant.keys:
                        sql, args = mask(key, 63); clauses.append(sql); params.extend(args)
            else:
                for key in variant.keys:
                    sql,args=mask(key,bit);clauses.append(sql);params.extend(args)
            if variant.phrase:
                selected = [col] if col else ([columns[1+[f[0] for f in FIELDS].index('formula_norm')]] if variant.field=='formula' else columns[1:])
                checks=[]
                for column in selected:
                    checks.append(f'position(%s in {column}) > 0' if connection.vendor == 'postgresql' else f'instr({column}, %s) > 0')
                    params.append(variant.phrase)
                clauses.append('('+' OR '.join(checks)+')')
            return '('+' AND '.join(clauses)+')', params
        if not self.plan.groups:
            return ('FALSE' if self.operation == 'matches' else '0'), []
        groups, group_params, tier_parts, tier_params, scores, score_params = [], [], [], [], [], []
        for group in self.plan.groups:
            variants, vp, tiers, tp, scored, sp = [], [], [], [], [], []
            for variant in sorted(group,key=lambda v:v.tier):
                condition,args = variant_sql(variant)
                variants.append(condition);vp.extend(args)
                tiers.append(f'WHEN {condition} THEN {variant.tier}');tp.extend(args)
                # Tier is evaluated first; within a tier choose the best matching field.
                field_scores, fp = [], []
                quality = (100,90,75,65,60)[variant.tier]
                if variant.keys and all(k.startswith('id:') for k in variant.keys):
                    cond, args = variant_sql(variant,32)
                    field_scores.append(f'WHEN {cond} THEN {8*quality}'); fp.extend(args)
                for (name,bit,weight), col in sorted(zip(FIELDS,columns[1:]),key=lambda p:-p[0][2]):
                    cond, args = variant_sql(variant,bit,col)
                    field_scores.append(f'WHEN {cond} THEN {weight*quality}');fp.extend(args)
                scored.append(f'WHEN {condition} THEN (CASE '+ ' '.join(field_scores)+' ELSE 0 END)')
                _, cp = variant_sql(variant); sp.extend(cp);sp.extend(fp)
            groups.append('('+' OR '.join(variants)+')'); group_params.extend(vp)
            tier_parts.append('(CASE '+' '.join(tiers)+' ELSE 9 END)');tier_params.extend(tp)
            scores.append('(CASE '+' '.join(scored)+' ELSE 0 END)');score_params.extend(sp)
        if self.operation == 'matches':
            return ' AND '.join(groups), group_params
        if self.operation == 'tier':
            func = 'GREATEST' if connection.vendor == 'postgresql' else 'MAX'
            return (tier_parts[0] if len(tier_parts)==1 else func+'('+','.join(tier_parts)+')'),tier_params
        if self.operation == 'identifier':
            if not self.plan.exact_identifier:
                return 'CAST(0 AS INTEGER)',[]
            cond,args=mask('id:'+self.plan.exact_identifier,32)
            return f'(CASE WHEN {cond} THEN 1 ELSE 0 END)',args
        if self.plan.exact_identifier:
            condition,args=mask('id:'+self.plan.exact_identifier,32)
            scores.append(f'(CASE WHEN {condition} THEN 10000 ELSE 0 END)');score_params.extend(args)
        # Phrase boosts are bounded and occur after match_tier in ordering.
        for name, boost in [('direct_topics_norm',1200),('topics_norm',100),('book_norm',800),('labels_norm',600),('body_norm',400)]:
            col=columns[1+[f[0] for f in FIELDS].index(name)]
            check=f'position(%s in {col}) > 0' if connection.vendor=='postgresql' else f'instr({col}, %s) > 0'
            scores.append(f'(CASE WHEN {check} THEN {boost} ELSE 0 END)');score_params.append(self.plan.normalized)
        # Exact readable labels cannot match across the U+001F field delimiter.
        col=columns[1]
        check=f'position(%s in (%s || {col} || %s)) > 0' if connection.vendor=='postgresql' else f'instr((%s || {col} || %s), %s) > 0'
        scores.append(f'(CASE WHEN {check} THEN 4000 ELSE 0 END)')
        needle='\x1f'+self.plan.normalized+'\x1f'
        score_params.extend([needle,'\x1f','\x1f'] if connection.vendor=='postgresql' else ['\x1f','\x1f',needle])
        return '('+'+'.join(scores)+')',score_params
