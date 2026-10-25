from unittest.mock import patch

from django.test import SimpleTestCase

from .signal_selected import manifest, review_manifest
from .signal_selected_views import SignalSelectedView
from .signal_selection_rules import classify
from .test_circuit_selected import CircuitCollectionTests as CircuitFixture
from .views import DrillQuestionDetailView
from .web_views import _safe_drill_target


class SignalRuleTests(SimpleTestCase):
    def test_manifest_partitions_inventory_without_duplicates(self):
        m, review = manifest(), review_manifest()['records']
        ids = [q['uuid'] for q in m['questions']] + [q['uuid'] for q in review]
        self.assertEqual(len(ids), 974)
        self.assertEqual(len(set(ids)), 974)
        self.assertEqual(len(m['questions']), 317)
        self.assertEqual(sum(q['status'] == 'review' for q in review), 419)
        self.assertEqual(sum(q['status'] == 'excluded' for q in review), 238)
        self.assertEqual({q['bucket'] for q in m['questions']}, {b['key'] for b in m['buckets']})
        self.assertTrue(all(q['evidence'] and q['reason'] for q in m['questions']))
        self.assertEqual(_safe_drill_target('/signal-selected?kind=calculation', site='ei'), '/signal-selected?kind=calculation')

    def test_core_methods_and_initial_conditions(self):
        row = classify('用单边z变换解差分方程 y(n)-0.5y(n-1)=u(n), y(-1)=2')
        self.assertEqual(row['bucket'], 'z_transform'); self.assertTrue(row['combined_z_initial'])
        self.assertEqual(classify('用拉氏变换求H(s)、h(t)和阶跃响应')['bucket'], 'laplace')
        self.assertEqual(classify('傅里叶变换求频谱，通过H(jω)求系统输出')['bucket'], 'fourier')
        self.assertEqual(classify('求有限时宽信号的卷积积分，写出分段波形')['bucket'], 'convolution')
        self.assertEqual(classify('根据零极点判断稳定性和频率响应')['bucket'], 'system_function')

    def test_common_false_positives_and_secondary_priorities(self):
        self.assertNotEqual(classify('利用冲激函数的抽样性质计算积分')['status'], 'included')
        self.assertEqual(classify('什么是佩利–维纳准则')['status'], 'review')
        self.assertEqual(classify('同态滤波中利用z变换解卷积')['status'], 'review')
        self.assertEqual(classify('计算傅里叶级数并画频谱')['bucket'], 'fourier_series')
        self.assertEqual(classify('由维纳–辛钦定理求相关函数')['bucket'], 'correlation')
        self.assertEqual(classify('卷积性质是否正确', label='2020年 · 判断3')['tier'], 'foundation')
        self.assertEqual(classify('说明Z变换和单位圆的关系', label='SIG-SA-12')['tier'], 'foundation')
        self.assertEqual(classify('', topic='z变换')['status'], 'review')
        self.assertEqual(classify('求z变换', scope='out_of_scope')['status'], 'review')
        self.assertEqual(classify('1、求卷积\n2、求频谱', source='cached_local_ocr')['status'], 'review')


class SignalCollectionTests(CircuitFixture):
    """Run the existing collection safety contract against the signal adapter."""
    def setUp(self):
        super().setUp()
        data = {'title': '信号严选', 'basis': 'Subjective priorities', 'inventory_count': 4,
                'questions': self.rows, 'buckets': [dict(key=k,title=k,rank=i,tier='core',focus='Practice')
                    for i,k in enumerate(['first_order','thevenin'],1)]}
        for target, value in [('drill.signal_selected.manifest', data),
                              ('drill.signal_selected_views.manifest', data),
                              ('drill.signal_selected_views.review_manifest', {'records': []})]:
            p = patch(target, return_value=value); p.start(); self.addCleanup(p.stop)

    def get(self, query='', *, view=SignalSelectedView, question=None, user=None, host='ei.test'):
        return super().get(query.replace('collection=circuit_selected', 'collection=signal_selected'),
                           view=view, question=question, user=user, host=host)

    def test_navigation_does_not_leak_between_virtual_collections(self):
        data = {'questions': [], 'buckets': []}
        with patch('drill.circuit_selected.manifest', return_value=data):
            response = self.get('collection=signal_selected&bucket=first_order',
                                view=DrillQuestionDetailView, question=self.q1)
            self.assertEqual(response.data['next_question_uuid'], str(self.q2.uuid))
