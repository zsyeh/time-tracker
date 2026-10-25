"""Deterministic study-priority rules, not an exam-probability estimator.

Only question-stem evidence selects a topic. Answers may identify an initial
condition technique but may not turn a neighbouring question into a match.
"""
import re

BUCKETS = [
    ('z_transform', 'Z 变换 · 差分方程与初始条件', 'core', '单边 Z 变换、Y(z)、部分分式、全响应；结合 H(z) 与稳定性。'),
    ('laplace', '拉氏变换 · H(s)、h(t) 与系统响应', 'core', '微分方程、冲激/阶跃响应、零输入与零状态；注意收敛域。'),
    ('fourier', '傅里叶变换 · 频谱与系统输出', 'core', '时移、频移、尺度、卷积定理；重点核对 2π 系数和频移符号。'),
    ('convolution', '卷积积分／卷积和', 'core', '重叠区间、积分上下限、分段波形；冲激参与卷积。'),
    ('system_function', '系统函数 · 零极点、稳定性与频响', 'core', 'H(s)/H(z)、收敛域、因果性、稳定性和频率响应。'),
    ('spectrum', '能量谱／功率谱 · 帕塞瓦尔', 'advanced', '基本谱计算与通过线性系统后的谱、功率和能量。'),
    ('sampling', '抽样频谱／抽样定理', 'advanced', '奈奎斯特条件、频谱复制和基本恢复，不主攻复杂重建推导。'),
    ('fourier_series', '傅里叶级数 · 基础巩固', 'foundation', '典型周期信号的系数与频谱，非首轮计算大题主攻。'),
    ('correlation', '相关函数／维纳–辛钦 · 基础巩固', 'foundation', '基本自相关、互相关与谱关系，不主攻繁琐分段积分。'),
]
PATTERNS = {
    'z_transform': r'[zZＺ]变换|差分方程|[zZ]域|[XYZHxyz]\(?[zZ]\)',
    'laplace': r'拉氏|拉普拉斯|[sS]域|[XYZH]\(?s\)|微分方程.{0,80}(?:响应|求解)|(?:冲激|阶跃|零状态|零输入|全)响应',
    'fourier': r'傅[里立]叶变换|傅氏变换|频谱|频移|时移.{0,30}变换|[HF]\(?j[ωw]\)|傅里叶反变换|[Ff]ourier',
    'convolution': r'卷积|卷和|褶积',
    'system_function': r'系统函数|零[、和与]?极点|零点|极点|稳定性|收敛域|频率响应|频响|无失真',
    'spectrum': r'能量谱|功率谱|帕[塞斯]瓦[尔耳]|Parseval|方均值',
    'sampling': r'(?:抽样|采样)(?:定理|频率|频谱|周期|间隔|信号|后|率)|(?:进行|理想|均匀|冲激)(?:抽样|采样)|奈奎斯特|Nyquist',
    'fourier_series': r'傅[里立]叶级数|傅氏级数|级数系数|傅里叶系数|基波|谱线间隔|谐波幅度',
    'correlation': r'自相关|互相关|相关函数|维纳.{0,5}[辛欣]钦|[辛欣]钦定理',
}
EXTRA = r'希尔伯特|Hilbert|佩利|维纳准则|同态滤波|状态空间|状态转移矩阵|最小相位|全通系统|全通网络|全通特性|椭圆滤波|多速率|快速傅里叶|\bFFT\b|\bDFT\b|圆周卷积|循环卷积|带通抽样|带通信号抽样'


def normalize(text):
    text = text.replace('\\omega', 'ω').replace('\\(', '(').replace('\\)', ')')
    text = re.sub(r'[\ue000-\uf8ff]', '(', text)
    return re.sub(r'\s+', '', text)


def classify(stem, *, label='', topic='', scope='', source='structured_text'):
    text = normalize(stem)
    tags = [key for key, pattern in PATTERNS.items() if re.search(pattern, text, re.I)]
    if source == 'structured_text' and '周期信号' in topic and 'fourier' in tags:
        tags.append('fourier_series')
    result = {'status': 'review', 'bucket': None, 'tags': tags, 'tier': 'foundation',
              'kind': 'calculation', 'combined_z_initial': False, 'reason': []}
    if not text:
        result['reason'] = ['缺少可靠题干文字，不仅凭章节号归类']
        return result
    if scope == 'out_of_scope' or re.search(EXTRA, text, re.I):
        result['reason'] = ['已标超纲或包含非本轮主攻深度的扩展内容，待复核']
        return result
    if source == 'cached_local_ocr' and len(re.findall(r'(?:^|\n)\s*\d{1,2}[、．.]', stem)) > 1:
        result['reason'] = ['OCR 区段包含多个主题号，归属待复核']
        return result
    if not tags:
        result['status'] = 'review' if source == 'cached_local_ocr' else 'excluded'
        result['reason'] = ['未明确命中指定计算题型；信号分类、单纯画序列或建模不混入主攻组']
        return result
    # Specific tasks beat generic words such as frequency spectrum. Transform
    # questions stay in their transform bucket even when ROC/poles are asked.
    order = ['sampling', 'correlation', 'spectrum', 'fourier_series',
             'z_transform', 'convolution', 'laplace', 'system_function', 'fourier']
    primary = next(key for key in order if key in tags)
    if 'fourier' in tags and primary == 'system_function' and re.search(r'j[ωw]|傅[里立]叶变换', text):
        primary = 'fourier'
    # A bare h(t) computation via convolution is a convolution exercise, not
    # an assumption that the question explicitly asks for a Laplace method.
    concept = ('填空' in label or '选择' in label or '判断' in label or '背诵' in topic
               or bool(re.search(r'SA-\d|简答', label))
               or bool(re.search(r'简述|简答|说明.{0,8}(?:条件|性质|区别)|什么是|何谓', text)))
    result.update(status='included', bucket=primary,
                  tier='foundation' if concept else next(b[2] for b in BUCKETS if b[0] == primary),
                  kind='concept' if concept else 'calculation',
                  combined_z_initial=primary == 'z_transform' and bool(re.search(r'初始|初值|起始状态|[yxv][(\[]?-?[012][)\](]*(?:=|为)', text, re.I)),
                  reason=['题干明确匹配：' + '、'.join(tags)])
    return result
