#!/usr/bin/env python3
"""Opt-in isolated fixture generator. Never point it at a production database."""
import argparse
import datetime
import json
import os
from pathlib import Path
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','time_server.settings')
import django
django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model, SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.core.management import call_command
from django.utils import timezone
from drill.models import Question,QuestionDocument,QuestionAttempt,QuestionUserState
from tracker.models import TimeLog


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--questions',type=int,default=9300)
    parser.add_argument('--private',type=int,default=10000);parser.add_argument('--session-file',required=True)
    args=parser.parse_args()
    if os.environ.get('SEARCH_FIXTURE_ALLOW_WRITE')!='1' or 'precision_search' not in str(settings.DATABASES['default']['NAME']):
        parser.error('Requires explicit isolated precision_search database and SEARCH_FIXTURE_ALLOW_WRITE=1.')
    if Question.objects.exists() or get_user_model().objects.filter(username='search-fixture-owner').exists():
        parser.error('Use an empty disposable fixture database; no existing content is overwritten.')
    owner=get_user_model().objects.create_user('search-fixture-owner')
    other=get_user_model().objects.create_user('search-fixture-other')
    doc=QuestionDocument.objects.create(workspace='drill',source_id=899001,filename='M2.pdf',title='数学二严选练习册',sha256='fixture-math',page_count=100,relation_type='selected_question_book')
    ei=QuestionDocument.objects.create(workspace='ei',source_id=899002,filename='EI.pdf',title='EI synthetic collection',sha256='fixture-ei',page_count=100)
    titles=['多元微分 隐函数求偏导数','傅里叶变换 Fourier transform','傅里叶级数 Fourier series','Z 变换 Z-transform',
        '拉普拉斯变换 Laplace transform','卡诺图 Karnaugh map','RS 触发器 逻辑','负反馈 negative feedback',
        'Bode 波特图','数学二严选练习册',r'\partial f ∂',r'\dfrac{x}{y}',r'x^2','x(t)',r'\customMacro',r'x_1']
    items=[]
    for n in range(args.questions):
        text=titles[n] if n<len(titles) else 'Synthetic unrelated exercise '+str(n)
        if n>=len(titles) and n%20==0:text='导数 合成练习 '+str(n)
        if n>=len(titles) and n%23==0:text='Fourier series 合成练习 '+str(n)
        items.append(Question(uuid=uuid.uuid5(uuid.NAMESPACE_URL,'precision-search-fixture/'+str(n)),document=doc if n%4!=3 or n<len(titles) else ei,
            question_order=n,source_label=f'{n+1}-2',prompt_text=text if n%11!=0 or n<len(titles) else '',
            fingerprint=f'synthetic-fixture-{n}',is_practiceable=True,question_type='single_choice' if n%2==0 else 'solution'))
    Question.objects.bulk_create(items,batch_size=500)
    QuestionAttempt.objects.bulk_create([QuestionAttempt(user=owner,question=q,result=('done','review','reset')[n%3]) for n,q in enumerate(items[:1000])],batch_size=500)
    QuestionUserState.objects.bulk_create([QuestionUserState(user=owner,question=q,is_favorite=True) for q in items[:10]],batch_size=500)
    now=timezone.now()
    for user in (owner,other):
        TimeLog.objects.bulk_create([TimeLog(user=user,category='math',status='completed',title='Private synthetic archive '+str(n),
            details='Ｆｏｕｒｉｅｒ 变换' if n==0 else 'Synthetic ordinary private text',
            start_time=now-datetime.timedelta(minutes=n+1),end_time=now-datetime.timedelta(minutes=n)) for n in range(args.private)],batch_size=500)
    call_command('rebuild_question_search',workspace='all',batch_size=500,verify=True)
    session=SessionStore();session[SESSION_KEY]=str(owner.pk);session[BACKEND_SESSION_KEY]='django.contrib.auth.backends.ModelBackend';session[HASH_SESSION_KEY]=owner.get_session_auth_hash();session.save()
    fd=os.open(args.session_file,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as file:file.write('sessionid='+session.session_key)
    print(json.dumps({'fixture_user_id':owner.pk,'questions':args.questions,'private_per_user':args.private,'session_file_written':True}))

if __name__=='__main__':main()
