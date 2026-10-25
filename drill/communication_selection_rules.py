"""Communication study priorities over reliable existing question stems."""
import re

BUCKETS = [
    ('isi','无码间串扰／奈奎斯特／升余弦','core','滚降系数、带宽、最高码元速率与多电平信息速率。'),
    ('matched_filter','匹配滤波／抽样时刻／输出信噪比','core','h(t)=Ks*(T−t)、信号能量与最大输出信噪比；区别普通误码率代入题。'),
    ('pcm_capacity','PCM／信息量／香农容量','core','抽样、量化位数、PCM与时分复用速率、信息量和容量。'),
    ('analog_mod','AM／DSB／SSB 频谱与带宽','advanced','调制表达式、谱线位置、边带和传输带宽。'),
    ('binary_mod','2ASK／2FSK／2PSK 调制与带宽','advanced','典型表达式、相干解调框图、波形与第一零点带宽。'),
    ('baseband_basics','基带码型／频谱／眼图基础','foundation','AMI、HDB3、基本波形和频谱；不主攻复杂均衡设计。'),
    ('receiver_basics','接收性能／误码率基础（选练）','cross','基本判决与误码率公式应用，不冒充匹配滤波计算大题。'),
    ('angle_multilevel','FM／PM／多进制基础（选练）','cross','概念和简单带宽比较，不主攻复杂抗噪推导。'),
]
PATTERNS = {
    'isi':r'码间串扰|码间干扰|奈奎斯特|Nyquist|升余弦|滚降|无码间|最高.{0,5}(?:码元|传码)|二进制.{0,5}基带传输系统.{0,12}传输函数|数字基[带待].{0,45}传输特性',
    'matched_filter':r'匹配.{0,3}滤波|最大输出信噪比|最大信噪比',
    'pcm_capacity':r'PCM|脉冲编码|量化|抽样频率|抽样速率|信息量|平均信息|信源熵|香农|Shannon|信道容量|信息速率|传信率|码元速率和信息速率',
    'analog_mod':r'DSB|SSB|\bAM\b|单边带|双边带|振幅调制|调幅|线性调制',
    'binary_mod':r'2ASK|2FSK|2PSK|2DPSK|二进制.{0,8}(?:调制|幅移|频移|相移)|幅移键控|频移键控|相移键控',
    'baseband_basics':r'AMI|HDB3|PST|眼图|基带信号|基带传输|码型|双相码',
    'receiver_basics':r'误码率|错误概率|误符号率|最佳判决|最佳接收|抗噪声|包络检波|解调器.{0,12}信噪比',
    'angle_multilevel':r'\bFM\b|\bPM\b|调频|调相|频率调制|相位调制|角度调制|多进制|4DPSK|QAM|QPSK',
}
EXTRA=r'迫零|均衡器|均衡.{0,6}设计|部分响应|完整.{0,6}(?:傅里叶|积分|逆变换)|(?:证明|推导).{0,25}(?:单位冲激响应|升余弦|傅里叶逆)|推导.{0,12}(?:误码率|抗噪)|证明.{0,12}误码率|上题|前题|上一题|图缺失|缺图|题目不全'


def classify(stem,*,label='',topic='',scope='',source='structured_text'):
    text=re.sub(r'\s+','',stem)
    tags=[k for k,p in PATTERNS.items() if re.search(p,text,re.I)]
    row=dict(status='review',bucket=None,tags=tags,tier='foundation',kind='calculation',combined_priority=False,reason=[])
    if not text:
        row['reason']=['缺少可靠题干，不凭章节标题猜题型'];return row
    if scope=='out_of_scope' or re.search(EXTRA,text,re.I):
        row['reason']=['超纲标记、资料不全或复杂均衡/推导，非本轮主攻深度'];return row
    if not tags:
        row.update(status='excluded',reason=['未命中本轮通信训练范围']);return row
    # Mere mention of a matched receiver does not turn a BER substitution
    # exercise into h(t)/energy/max-SNR training.
    ber=bool(re.search(r'误码率|误符号率|错误概率',text))
    filter_target=bool(re.search(r'冲激响应|脉冲响应|最大.{0,4}信噪比|最佳抽样|信号能量',text))
    if ber and not filter_target:primary='receiver_basics'
    elif 'matched_filter' in tags:primary='matched_filter'
    elif 'isi' in tags:primary='isi'
    elif 'angle_multilevel' in tags:primary='angle_multilevel'
    elif 'binary_mod' in tags:primary='binary_mod'
    elif 'analog_mod' in tags:primary='analog_mod'
    elif 'pcm_capacity' in tags:primary='pcm_capacity'
    elif 'baseband_basics' in tags:primary='baseband_basics'
    else:primary='receiver_basics'
    if primary=='analog_mod' and re.search(r'信噪比|抗噪声|门限效应',text) and not re.search(r'频谱|带宽|表达式',text):
        primary='receiver_basics'
    # Eye diagrams are supporting basics even when the pulse is raised cosine.
    if '眼图' in text and not re.search(r'滚降系数|最高.{0,4}码元|无码间',text):primary='baseband_basics'
    concept=('选择' in label or '填空' in label or '判断' in label or '背诵' in topic
             or bool(re.search(r'SA-\d|简答',label))
             or (bool(re.search(r'什么|何谓|简述|试述|试叙述|试比较|一般写成什么|核心优势|基本概念|为什么',text))
                 and not re.search(r'计算|试求|求出|画出|写出',text)))
    kind='concept' if concept else 'analysis' if re.search(r'画出|方框图|框图|波形|频谱图',text) and not re.search(r'计算|试求|求出',text) else 'calculation'
    tier=next(b[2] for b in BUCKETS if b[0]==primary)
    if concept and primary!='matched_filter':tier='foundation'
    # Preserve visibility of the currently sparse matched-filter basics, but
    # retain the honest concept type; never count them as full calculation.
    if primary=='pcm_capacity' and re.search(r'A律|μ律|µ律|非均匀量化',text) and not concept:tier='cross'
    if primary=='angle_multilevel' and re.search(r'证明|推导',text):
        row['reason']=['多进制/角度调制专项证明不进入本轮主攻'];return row
    row.update(status='included',bucket=primary,tier=tier,kind=kind,
               combined_priority=primary in {'isi','matched_filter','pcm_capacity'} and tier=='core',
               reason=['题干明确匹配：'+'、'.join(tags)])
    return row
