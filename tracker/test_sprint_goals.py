import datetime
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from .models import TimeLog,UserPreferences,StudyTag
from .sprint_goals import build_sprint_progress
from .services import finish_session,start_session
from .user_preferences import _value
from .time_intervals import study_seconds_between

@override_settings(SECURE_SSL_REDIRECT=False)
class SprintGoalTests(TestCase):
    def setUp(self):
        self.u=get_user_model().objects.create_user('sprint-fixture')
        self.day=datetime.date(2026,11,26)
        self.now=timezone.make_aware(datetime.datetime(2026,11,26,23,0))
        self.config={'mode':'sprint20','start_date':self.day.isoformat()}
        UserPreferences.objects.create(user=self.u,values={'timer.goal_plan':self.config})
    def log(self,subject,minutes,day=None,title='',grade='A'):
        a=timezone.make_aware(datetime.datetime.combine(day or self.day,datetime.time(1)))
        return TimeLog.objects.create(user=self.u,category=subject,status='completed',start_time=a,end_time=a+datetime.timedelta(minutes=minutes),title=title,efficiency_grade=grade)
    def test_subject_surplus_never_covers_another_subject(self):
        for key,n in [('math',400),('major',200),('english',100),('training',20)]:self.log(key,n)
        p=build_sprint_progress(self.u,self.now)
        self.assertEqual(p['today']['actual_minutes'],720)
        self.assertEqual(p['today']['credited_minutes'],620)
        self.assertEqual(p['today']['remaining_minutes'],61)
        self.assertEqual(p['today']['subjects'][0]['completion_percent'],133.3)
        self.assertFalse(p['today']['complete'])
        self.assertEqual(p['cumulative']['target_minutes'],13620)
    def test_extra_tasks_and_efficiency_are_separate_from_net_base(self):
        self.log('english',111,grade='F');self.log('english',40,title='英语作文')
        self.log('math',50,title='数学错题订正');self.log('major',30,title='旧知识复测')
        tag=StudyTag.objects.create(user=self.u,name='冲刺额外任务')
        l=self.log('major',20);l.tags.add(tag)
        p=build_sprint_progress(self.u,self.now)
        self.assertEqual(p['today']['extra_minutes'],110)
        self.assertEqual(p['today']['credited_minutes'],141)
        self.assertEqual(p['today']['subjects'][2]['base_minutes'],111)
        self.assertEqual(p['today']['actual_minutes'],251)
    def test_pauses_are_split_at_midnight_and_excluded_from_all_net_time(self):
        start=self.now.replace(hour=23,minute=30)-datetime.timedelta(days=1)
        pause=start+datetime.timedelta(minutes=20)
        l=TimeLog.objects.create(user=self.u,category='math',status='completed',start_time=start,end_time=start+datetime.timedelta(hours=1),pause_intervals=[{'start':pause.isoformat(),'end':(pause+datetime.timedelta(minutes=20)).isoformat()}],efficiency_grade='F')
        self.assertEqual(l.duration_minutes,40);self.assertEqual(l.credited_duration_minutes,30)
        self.assertEqual(build_sprint_progress(self.u,self.now)['today']['subjects'][0]['base_minutes'],20)
        with self.assertNumQueries(2):build_sprint_progress(self.u,self.now,config=self.config)
    def test_cumulative_caps_each_day_and_does_not_import_outside_window(self):
        self.config['start_date']=(self.day-datetime.timedelta(days=1)).isoformat()
        self.log('math',600,day=self.day-datetime.timedelta(days=1))
        self.log('major',480);self.log('english',200,day=self.day-datetime.timedelta(days=2))
        p=build_sprint_progress(self.u,self.now,config=self.config)
        self.assertEqual(p['cumulative']['credited_minutes'],540)
        self.assertEqual(p['cumulative']['actual_minutes'],1080)
        self.assertEqual(p['cumulative']['completed_days'],0)
        self.assertEqual(len(p['calendar']),20)
    def test_short_and_over_twelve_hour_sprint_sessions_are_kept(self):
        for minutes in [15,13*60]:
            l=TimeLog.objects.create(user=self.u,category='english',status='running',start_time=timezone.now()-datetime.timedelta(minutes=minutes))
            returned,reused=start_session(self.u,'english');self.assertEqual(returned.pk,l.pk);self.assertTrue(reused)
            ended,changed,reason=finish_session(l,{})
            self.assertIsNone(reason);self.assertIsNotNone(ended);self.assertTrue(changed)
    def test_pause_api_is_owned_idempotent_and_resume_preserves_identity(self):
        l=TimeLog.objects.create(user=self.u,category='math',start_time=timezone.now()-datetime.timedelta(minutes=10))
        c=APIClient();c.force_authenticate(self.u)
        url=f'/api/sessions/{l.pk}/pause/'
        for _ in range(2):self.assertEqual(c.post(url,{'action':'pause'},format='json').status_code,200)
        l.refresh_from_db();self.assertEqual(len(l.pause_intervals),1);self.assertTrue(l.is_paused)
        fixed=study_seconds_between(l,l.start_time,timezone.now())
        self.assertEqual(study_seconds_between(l,l.start_time,timezone.now()+datetime.timedelta(minutes=5)),fixed)
        self.assertEqual(c.post(url,{'action':'resume'},format='json').status_code,200)
        l.refresh_from_db();self.assertFalse(l.is_paused)
        other=get_user_model().objects.create_user('sprint-other');UserPreferences.objects.create(user=other,values={'timer.goal_plan':self.config});c.force_authenticate(other)
        self.assertEqual(c.post(url,{'action':'pause'},format='json').status_code,404)
    def test_configuration_validation(self):
        self.assertEqual(_value('timer.goal_plan',self.config),self.config)
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):_value('timer.goal_plan',{'mode':'sprint20','start_date':'2026-02-30'})
