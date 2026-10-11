"""Structured excerpts from the official UCAS 892 syllabus (2025-06-30).

This is presentation/reference metadata, not a second question taxonomy. Topic
matching always points back to the existing QuestionTopic records.
"""

EXAM_OVERVIEW = {
    'source': '中国科学院大学《电子信息专业综合》考试大纲',
    'compiled_at': '2025-06-30',
    'duration_minutes': 180,
    'total_score': 150,
    'course_weight': '五门课程各约 20%',
    'question_structure': [
        {'label': '选择题', 'score': 30}, {'label': '填空题', 'score': 30},
        {'label': '简答题', 'score': 30}, {'label': '计算及证明题', 'score': 60},
    ],
}


SYLLABUS = {
    'circuit': [
        ('电路模型和电路定律', [('master', '熟练掌握电荷、电阻、电流、电压、功率等基本物理量概念。'), ('understand', '理解关联参考方向。'), ('master', '熟练掌握基尔霍夫定律。'), ('understand', '理解模拟与数字信号的定义、特点。')]),
        ('电阻电路等效变换', [('master', '掌握包括 Y-Δ、平衡电桥、受控源电路在内的等效电路化简。'), ('master', '掌握两种电源之间的等效变换。')]),
        ('电阻电路一般分析方法与网络定理', [('master', '掌握节点电压法、网孔/回路电流法。'), ('master', '掌握叠加定理、戴维南定理和诺顿定理。')]),
        ('动态电路的时域分析', [('master', '掌握电容器、电感器及其电气特性、换路与初始值计算。'), ('master', '掌握一阶动态电路三要素法、零状态响应和零输入响应。'), ('master', '掌握二阶动态电路的时域分析。')]),
        ('正弦激励下动态电路的稳态分析', [('understand', '理解相量、阻抗、导纳、相量图。'), ('master', '掌握正弦稳态电路的相量分析法与共轭匹配。'), ('understand', '理解谐振、品质因数和理想变压器特性。')]),
    ],
    'analog': [
        ('半导体基础', [('master', '掌握半导体二极管原理、特性及电路模型。'), ('master', '掌握双极型晶体管的构成、工作原理、特性及小信号模型。'), ('master', '掌握 MOSFET、JFET 的构成、工作原理、特性及小信号模型。')]),
        ('基本放大电路', [('master', '掌握共射、共集、共基放大电路工作原理及分析方法。'), ('master', '掌握共源、共漏、共栅放大电路工作原理及分析方法。'), ('master', '掌握电流源、差分、功率及多级放大电路工作原理与分析方法。')]),
        ('放大电路的频率响应', [('understand', '理解电路的频率响应与波特图。'), ('master', '掌握基本放大电路的高频电路分析。')]),
        ('放大电路的反馈', [('understand', '理解反馈的概念与极性判断。'), ('master', '掌握深度负反馈电路的分析方法。'), ('know', '了解负反馈放大电路的稳定性分析。')]),
        ('集成运算放大器与应用', [('master', '掌握集成运算放大器组成、电压传输特性及模拟运算电路分析。'), ('understand', '理解电压比较器并掌握滞回比较器传输特性。'), ('understand', '理解利用运放产生矩形波、三角波、锯齿波的方法。')]),
    ],
    'digital': [
        ('数字电路的数学基础', [('master', '掌握不同数制转换、反码、补码及补码运算。'), ('understand', '理解逻辑函数及其描述方法。'), ('master', '掌握公式法、卡诺图法和含无关项的逻辑函数化简。')]),
        ('CMOS 门电路', [('master', '掌握 CMOS 反相器、与非门、或非门的结构、原理及静动态特性。'), ('master', '掌握漏极开路输出门和三态门的结构、原理及静态特性。')]),
        ('组合逻辑电路分析与设计', [('master', '掌握组合逻辑电路分析与基本设计方法。'), ('know', '了解编码器、译码器、数据选择器、加法器、比较器等模块。'), ('understand', '理解组合逻辑电路中的竞争-冒险。')]),
        ('半导体存储电路基础', [('understand', '理解半导体存储电路概念。'), ('master', '掌握触发器的组成、工作原理与分类。')]),
        ('时序逻辑电路分析与设计', [('master', '掌握同步时序逻辑电路分析方法。'), ('know', '了解移位寄存器、计数器、顺序脉冲及序列信号发生器。'), ('master', '掌握简单同步时序逻辑电路设计方法。')]),
    ],
    'signals': [
        ('信号与系统理论概述', [('know', '了解信号基本分类和典型信号表示。'), ('master', '掌握信号运算、奇异函数和信号分解方法。'), ('know', '了解系统分类，熟悉系统数学模型和基本特性。')]),
        ('连续时间系统和离散时间系统的时域分析', [('master', '掌握常系数微分/差分方程与系统框图建立。'), ('master', '掌握冲激响应、阶跃响应及系统特性判断。'), ('master', '掌握卷积的定义、性质和计算。')]),
        ('傅里叶变换及其应用', [('know', '了解周期信号傅里叶级数，熟悉典型周期信号频谱。'), ('master', '掌握非周期信号傅里叶变换及基本性质。'), ('master', '掌握抽样定理并理解连续时间信号恢复原理。'), ('master', '掌握利用 H(jω) 求响应、相关定理、维纳-欣钦定理及能量谱和功率谱分析。'), ('understand', '理解无失真传输的定义与特性。')]),
        ('拉氏变换和连续时间系统的 s 域分析', [('understand', '理解拉氏变换定义、应用范围、物理意义及收敛域。'), ('master', '掌握拉氏变换性质、常用变换及电路 s 域分析。'), ('master', '掌握系统函数、稳定性及利用零极点分析频率响应。')]),
        ('z 变换和离散时间系统的 z 域分析', [('understand', '理解 z 变换定义与收敛域。'), ('master', '掌握 z 变换性质、典型序列变换及差分方程求解。'), ('master', '掌握离散时间系统的系统函数和频率响应。')]),
    ],
    'communication': [
        ('通信系统基础', [('master', '掌握通信基本概念、系统模型、信息度量和主要性能指标。'), ('understand', '理解信道定义、分类及数学模型。'), ('master', '掌握信道容量、香农公式和脉冲编码调制。')]),
        ('模拟调制系统', [('understand', '理解调制目的、定义和分类。'), ('master', '掌握线性调制的一般模型。'), ('know', '了解线性调制抗噪声性能、角度调制及各种模拟调制系统性能比较。')]),
        ('数字基带传输系统', [('understand', '理解数字基带信号、频谱特性与常用码型。'), ('master', '掌握数字基带传输、码间串扰及无码间串扰传输特性。'), ('know', '了解抗噪声性能、眼图、部分响应系统和时域均衡。')]),
        ('数字带通传输系统', [('master', '掌握二进制数字调制原理。'), ('know', '了解二进制调制抗噪声性能及性能比较。'), ('know', '了解多进制数字调制原理及其抗噪声性能。')]),
        ('数字信号的最佳接收', [('understand', '理解数字信号最佳接收原理、准则及确知信号最佳接收机。'), ('master', '掌握数字信号的匹配滤波接收法。'), ('know', '了解最佳基带传输系统。')]),
    ],
}


def _tokens(value):
    value = value.lower().replace(' ', '')
    return {value[index:index + 2] for index in range(max(0, len(value) - 1))}


def match_official_requirement(course_code, chapter_title, topic_title):
    chapters = SYLLABUS.get(course_code, ())
    chapter = max(chapters, key=lambda item: len(_tokens(item[0]) & _tokens(chapter_title)), default=None)
    if not chapter:
        return 'unspecified', ''
    topic_tokens = _tokens(topic_title)
    ranked = sorted(
        ((len(topic_tokens & _tokens(text)), level, text) for level, text in chapter[1]),
        reverse=True,
    )
    score, level, text = ranked[0]
    if not score:
        explicit = {
            ('analog', '幅频特性与相频特性'): ('understand', '理解电路的频率响应与波特图。'),
            ('digital', '状态方程、状态表与状态图'): ('master', '掌握同步时序逻辑电路分析方法。'),
            ('communication', '调频 FM 与调相 PM 基本概念'): ('know', '了解调频、调相的基本概念及角度调制的抗噪声性能。'),
        }
        if (course_code, topic_title) in explicit:
            return explicit[(course_code, topic_title)]
    return (level, text) if score else ('unspecified', '')


def course_syllabus_payload(course_code):
    return [
        {'chapter': chapter, 'requirements': [{'level': level, 'text': text} for level, text in requirements]}
        for chapter, requirements in SYLLABUS.get(course_code, ())
    ]
