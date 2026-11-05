"""One-off, source-verified repair for production errata 59–63.

Run with ``ERRATA_MODE=backup`` first, copy the generated directory off the
container, then run with ``ERRATA_MODE=apply``. All original assets are retained
as superseded revisions. This file is executed through ``manage.py shell``.
"""

import hashlib
import json
import os
import struct
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from drill.models import Question, QuestionAsset, QuestionAttempt, QuestionErratum, QuestionRevision, QuestionUserState
from drill.pdf_import import stable_source_id


MODE = os.environ.get('ERRATA_MODE', '')
BACKUP = Path('/tmp/errata-20261105-backup')
IMAGES = Path('/tmp/errata-20261105-images')
EXPECTED = {
    59: (6645, '1ef112c463cb831a983700382d7aea401d54e96b0a74e0c4656e3179809d51e8', 'drill'),
    60: (8786, '2957b37830bab51ee32814bec9a4674a90106cfee9c7e5383405269056cde412', 'drill'),
    61: (7284, 'bb8cb5020c6282e91992f706425adafc9b9b00323b31215e614d6ff3e457d66e', 'ei'),
    62: (6230, 'fc4a23af5fc5f9dcaee2cc936c8969a0336fe5a0bc65f5ec4ce550ffc5f6b4a7', 'ei'),
    63: (6213, '092c841c3d9f28a22725763b91d62e058197a7aff768d3cc7b4ee745d2397daa', 'ei'),
}
DOCUMENT_SHA = {
    59: 'e9d89671876708dff2e0f5539fcbe8ff264b73dbec2cbb87013ebdcafea9079c',
    60: 'd3f78eb73684cc01abb224f076fb082a31a4f79ac5dd6a1ee089ed1c6ede6042',
    61: '0563a14dedba0e10eab09686b158233a0111a4ea57c19bcf51b7ba5c2827f115',
    62: '1b118a8a445d2782f17e72dabe1b1317ba39f590b5d5ab1383d08f48e1216469',
    63: '1b118a8a445d2782f17e72dabe1b1317ba39f590b5d5ab1383d08f48e1216469',
}
NEW_SHA = {
    '59-answer-corrected.png': 'de6f3ec72a99057bcf4d9212573bb6ae8c807ccb47c313c1545f50a2d9c8929b',
    '60-question-original.png': 'b0b3971df9a9dcbb3582401e413500540c8c59b5e61979eb36ec3c137e120ede',
    '62-question-diagram.png': 'b5ef133eeb703beca744f44c87ee945bfc03f336554311f1d854722371ae0792',
    '62-question-text.png': '0df494722c02fc14b3e36369712a2760795a533701b1b430eb66f2b16d844874',
    '63-question-full.png': '697bacb839771869de663330de4d0534d073ec4c92904dd61b45d213cdee5492',
}
OLD_ASSETS = {
    59: (28207, '164c49713dc9e46a17a6c33045b676fb8d38c7a52864cb569ac9a6b5a30d3c63', 'answer_crop'),
    60: (31071, '82e2fd16b699ccebc632676e004a3680eee743130cc8725090561d99b36ad769', 'question_crop'),
    62: (34316, 'ec4675c23c031441737886466a4710cf3e5a33d742d6d11bafb9bbfb7552dac8', 'question_crop'),
    63: (26981, '07ed4fd8f7f77a3a7caccec8c21cc1bac658ad9352d3577db8659bd7ca8c63db', 'question_crop'),
}
NEW_ASSETS = {
    59: [('59-answer-corrected.png', 'answer_crop', 0, None)],
    60: [('60-question-original.png', 'question_crop', 0, None)],
    62: [
        ('62-question-text.png', 'question_crop', 0, (240, 15, 440, 278, 518, 180)),
        ('62-question-diagram.png', 'question_crop', 1, (241, 65, 190, 265, 365, 180)),
    ],
    63: [('63-question-full.png', 'question_crop', 0, (61, 0, 189.8, 489.54, 346, 180))],
}
RESOLUTIONS = {
    59: 'Corrected the answer to pi/32; the previous pi/16 omitted the outer factor 1/2. The derivation is shown below the new answer image.',
    60: 'Restored the complete five-row determinant and both requested cofactor sums from the original solution source; the generated question sheet had omitted a row.',
    61: 'Verified against the source PDF: the system diagram is present in the question and all three output plots are present in the answer images.',
    62: 'Restored the complete question text and the referenced circuit diagram 6.3.4 from the source PDF.',
    63: 'Extended the source PDF crop to include the full circuit and the remaining question text.',
}
MATH_ANSWER = (
    '### 已核对勘误\n\n'
    '原答案图中的 π/16 漏乘了外层积分的 1/2。令 u = r cos θ，则\n\n'
    r'\[I=\left(\int_0^{\pi/4}\frac{\sin\theta}{\cos^3\theta}\,d\theta\right)'
    r'\left(\int_0^1u^2\sqrt{1-u^2}\,du\right)'
    r'=\frac12\cdot\frac{\pi}{16}=\boxed{\frac{\pi}{32}}.\]' + '\n'
)


def fields(instance, skip=()):
    return {field.attname: getattr(instance, field.attname) for field in instance._meta.concrete_fields if field.attname not in skip}


def checked_rows():
    rows = {}
    for erratum_id, (question_id, fingerprint, workspace) in EXPECTED.items():
        erratum = QuestionErratum.objects.select_related('question', 'question__document').get(pk=erratum_id)
        question = erratum.question
        assert erratum.status == 'open', (erratum_id, erratum.status)
        assert (question.pk, question.fingerprint, question.document.workspace) == (question_id, fingerprint, workspace)
        assert question.document.sha256 == DOCUMENT_SHA[erratum_id]
        rows[erratum_id] = (erratum, question)
    for erratum_id, (asset_id, sha, asset_type) in OLD_ASSETS.items():
        asset = QuestionAsset.objects.get(pk=asset_id, question=rows[erratum_id][1])
        assert (asset.sha256, asset.asset_type) == (sha, asset_type)
        assert hashlib.sha256(bytes(asset.image_data)).hexdigest() == sha
    signal = rows[61][1]
    linear_answer = rows[60][1].assets.get(pk=31072)
    assert linear_answer.sha256 == '0ad9a95c9d10e5c6b088ff85e05ea457b0a9601e97d5d3a0d8b373d41605e000'
    assert hashlib.sha256(bytes(linear_answer.image_data)).hexdigest() == linear_answer.sha256
    for asset_id, sha in (
        (29709, 'ed4de2a5531c883127bbf5620b8ccd7d0d716d607cc75012e0473065032e2ee9'),
        (29711, '4214b99f28eaba31bddf85cfe0c0a391f09ea51a4dfc4896ddd41ff06fc33c93'),
    ):
        asset = signal.assets.get(pk=asset_id)
        assert asset.sha256 == sha and hashlib.sha256(bytes(asset.image_data)).hexdigest() == sha
    return rows


def backup():
    assert not BACKUP.exists(), 'Backup directory already exists; keep the first copy.'
    rows = checked_rows()
    BACKUP.mkdir(mode=0o700)
    payload = {'questions': {}, 'errata': {}, 'assets': {}, 'created_at': timezone.now().isoformat()}
    for erratum_id, (erratum, question) in rows.items():
        payload['questions'][str(question.pk)] = fields(question)
        payload['errata'][str(erratum_id)] = fields(erratum)
        for asset in question.assets.all():
            blob = bytes(asset.image_data)
            actual = hashlib.sha256(blob).hexdigest()
            assert actual == asset.sha256, asset.pk
            filename = f'asset-{asset.pk}.bin'
            (BACKUP / filename).write_bytes(blob)
            payload['assets'][str(asset.pk)] = {**fields(asset, skip=('image_data',)), 'file': filename}
    (BACKUP / 'rows.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({'mode': 'backup', 'dir': str(BACKUP), 'questions': len(rows), 'assets': len(payload['assets'])}))


def image(name):
    data = (IMAGES / name).read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    assert hashlib.sha256(data).hexdigest() == NEW_SHA[name]
    width, height = struct.unpack('>II', data[16:24])
    assert 100 <= width <= 3000 and 40 <= height <= 3000
    return data, hashlib.sha256(data).hexdigest(), width, height


def apply():
    assert (BACKUP / 'rows.json').exists(), 'Verified backup required.'
    saved = json.loads((BACKUP / 'rows.json').read_text(encoding='utf-8'))
    for item in saved['assets'].values():
        assert hashlib.sha256((BACKUP / item['file']).read_bytes()).hexdigest() == item['sha256']
    rows = checked_rows()
    prepared = {erratum_id: [(name, asset_type, position, source, *image(name))
                             for name, asset_type, position, source in specs]
                for erratum_id, specs in NEW_ASSETS.items()}
    with transaction.atomic():
        locked_questions = list(Question.objects.select_for_update().filter(pk__in=[q.pk for _, q in rows.values()]).order_by('pk'))
        assert len(locked_questions) == 5
        locked_errata = list(QuestionErratum.objects.select_for_update().filter(pk__in=EXPECTED).order_by('pk'))
        assert len(locked_errata) == 5 and all(item.status == 'open' for item in locked_errata)
        before = {q.pk: (
            QuestionAttempt.objects.filter(question=q).count(), QuestionUserState.objects.filter(question=q).count()
        ) for q in locked_questions}
        for erratum_id in NEW_ASSETS:
            question = rows[erratum_id][1]
            QuestionRevision.capture(question)
            old_id, old_sha, old_type = OLD_ASSETS[erratum_id]
            old = QuestionAsset.objects.select_for_update().get(pk=old_id, question=question)
            assert (old.sha256, old.asset_type) == (old_sha, old_type)
            old.asset_type = old_type + '_superseded'
            old.save(update_fields=['asset_type'])
            for name, asset_type, position, source, blob, sha, width, height in prepared[erratum_id]:
                sid = stable_source_id('verified-errata-20261105', question.uuid, name, sha)
                assert not QuestionAsset.objects.filter(source_id=sid).exists()
                assert not question.assets.filter(sha256=sha).exists()
                assert not question.assets.filter(asset_type=asset_type, position=position).exists()
                kwargs = {}
                if source is not None:
                    page, x0, y0, x1, y1, dpi = source
                    kwargs = dict(source_page_index=page, source_x0=x0, source_y0=y0,
                                  source_x1=x1, source_y1=y1, render_dpi=dpi)
                QuestionAsset.objects.create(
                    source_id=sid, question=question, position=position, asset_type=asset_type,
                    sha256=sha, mime_type='image/png', image_data=blob,
                    width=width, height=height, **kwargs,
                )
            if erratum_id == 59:
                question.answer_markdown = MATH_ANSWER
                question.answer_source = 'provided-reference'
                question.answer_confidence = 1.0
                question.answer_generated_at = timezone.now()
                question.save(update_fields=['answer_markdown', 'answer_source', 'answer_confidence', 'answer_generated_at'])
            QuestionRevision.capture(question)
        now = timezone.now()
        for erratum_id, (erratum, _) in rows.items():
            erratum.status = 'resolved'
            erratum.resolution = RESOLUTIONS[erratum_id]
            erratum.resolved_at = now
            erratum.save(update_fields=['status', 'resolution', 'resolved_at', 'updated_at'])
        after = {q.pk: (
            QuestionAttempt.objects.filter(question=q).count(), QuestionUserState.objects.filter(question=q).count()
        ) for q in locked_questions}
        assert before == after, 'User learning records changed.'
    print(json.dumps({'mode': 'apply', 'resolved': sorted(rows), 'new_assets': sum(map(len, prepared.values())),
                      'attempts_and_states_preserved': True}))


if MODE == 'backup':
    backup()
elif MODE == 'apply':
    apply()
else:
    raise RuntimeError('Set ERRATA_MODE=backup or ERRATA_MODE=apply.')
