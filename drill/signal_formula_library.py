"""Fixed 892 Signals and Systems formula bank and four-day review plan."""

from __future__ import annotations


START_DATE = "2026-10-30"

CYCLE = (
    {
        "title": "傅里叶变换对、傅里叶变换性质",
        "sections": ("C",),
        "buckets": ("fourier",),
        "mistakes": (
            "单边指数必须带因果条件，且参数满足 a>0。",
            "频移后要替换整个频域表达式中的频率变量。",
            "尺度变换不能漏掉 1/|a|。",
        ),
    },
    {
        "title": "信号运算、卷积、LTI 系统时域分析",
        "sections": ("A",),
        "buckets": ("convolution", "system_function"),
        "mistakes": (
            "卷积积分必须先根据重叠区间确定上下限。",
            "零输入响应与零状态响应不能混淆。",
            "BIBO 稳定性判据要求冲激响应绝对可积或绝对可和。",
        ),
    },
    {
        "title": "拉普拉斯变换、Z 变换、系统函数、零极点",
        "sections": ("D", "E"),
        "buckets": ("laplace", "z_transform", "system_function"),
        "mistakes": (
            "单边变换的微分或移位公式必须带初始条件。",
            "同一个代数式可以对应不同序列，必须同时说明 ROC。",
            "因果稳定系统的连续极点在左半平面，离散极点在单位圆内。",
        ),
    },
    {
        "title": "傅里叶级数、能量与功率、相关函数、采样、无失真传输",
        "sections": ("B", "F"),
        "buckets": ("fourier_series", "spectrum", "correlation", "sampling"),
        "mistakes": (
            "能量信号与功率信号的相关函数及频谱定义不能混用。",
            "采样频谱复制包含 1/T_s 系数。",
            "无失真条件只需在输入信号占用频带内成立。",
        ),
    },
)


def _entry(key, section, title, formulas, condition, principle, pitfall, tags=()):
    return {
        "key": key,
        "section": section,
        "title": title,
        "formulas": tuple(formulas),
        "condition": condition,
        "principle": principle,
        "pitfall": pitfall,
        "tags": tuple(tags),
    }


FORMULA_LIBRARY = (
    _entry("A1_even_odd", "A", "奇偶分解", (
        r"f_e(t)=\frac{f(t)+f(-t)}{2}",
        r"f_o(t)=\frac{f(t)-f(-t)}{2}",
        r"f(t)=f_e(t)+f_o(t)",
    ), "适用于可进行时间反转与线性组合的信号。", "把信号与其时间反转相加或相减。", "奇分量的减法次序不能写反。", ("signal",)),
    _entry("A2_step_impulse", "A", "阶跃函数与冲激函数", (
        r"\frac{d\varepsilon(t)}{dt}=\delta(t)",
        r"\int_{-\infty}^{t}\delta(\tau)d\tau=\varepsilon(t)",
        r"f(t)\delta(t-t_0)=f(t_0)\delta(t-t_0)",
        r"\int_{-\infty}^{+\infty}f(t)\delta(t-t_0)dt=f(t_0)",
        r"\delta(at)=\frac{1}{|a|}\delta(t)",
    ), "抽样性质要求 f(t) 在 t_0 附近具有可定义的取值。", "冲激只保留抽样点的函数值。", "冲激尺度变换必须使用绝对值。", ("signal", "impulse")),
    _entry("A3_convolution", "A", "连续与离散卷积", (
        r"y(t)=x(t)*h(t)",
        r"y(t)=\int_{-\infty}^{+\infty}x(\tau)h(t-\tau)d\tau",
        r"y[n]=\sum_{k=-\infty}^{+\infty}x[k]h[n-k]",
        r"f(t)*\delta(t)=f(t)",
        r"f(t)*\delta(t-t_0)=f(t-t_0)",
        r"f(t)*g(t)=g(t)*f(t)",
    ), "积分或求和必须收敛；LTI 零状态响应使用该关系。", "翻转、平移、相乘并在重叠区间积分或求和。", "分段卷积最常错在重叠区间和积分上下限。", ("convolution", "lti")),
    _entry("A4_responses", "A", "冲激响应、阶跃响应与全响应", (
        r"g(t)=\int_{-\infty}^{t}h(\tau)d\tau",
        r"h(t)=\frac{dg(t)}{dt}",
        r"y_{zs}(t)=x(t)*h(t)",
        r"y(t)=y_{zi}(t)+y_{zs}(t)",
    ), "系统为 LTI；阶跃响应关系按零状态响应理解。", "阶跃是冲激的积分，线性系统输出相应保持微积分关系。", "不能把零输入响应并入卷积项。", ("lti", "response")),
    _entry("A5_causality", "A", "LTI 系统因果性", (
        r"h(t)=0,\quad t<0",
        r"h[n]=0,\quad n<0",
    ), "常规连续或离散 LTI 系统。", "因果系统不能在输入发生前产生响应。", "该判据针对冲激响应，不是任意输出。", ("lti", "causality")),
    _entry("A5_stability", "A", "LTI 系统 BIBO 稳定性", (
        r"\int_{-\infty}^{+\infty}|h(t)|dt<\infty",
        r"\sum_{n=-\infty}^{+\infty}|h[n]|<\infty",
    ), "常规 LTI 系统的冲激响应判据。", "绝对可积或绝对可和保证有界输入产生有界输出。", "只看 h(t) 是否趋零并不足以判断稳定。", ("lti", "stability")),

    _entry("B1_fundamental_frequency", "B", "基波角频率", (
        r"\omega_0=\frac{2\pi}{T_0}",
    ), "连续时间周期信号的基波周期为 T_0。", "每个周期相位增加 2\pi。", "不要把角频率与普通频率混用。", ("fourier_series",)),
    _entry("B2_exponential_fs", "B", "指数形式傅里叶级数", (
        r"f(t)=\sum_{k=-\infty}^{+\infty}F_ke^{jk\omega_0t}",
        r"F_k=\frac{1}{T_0}\int_{t_0}^{t_0+T_0}f(t)e^{-jk\omega_0t}dt",
    ), "f(t) 为满足傅里叶级数收敛条件的 T_0 周期信号。", "复指数在一个周期上正交。", "系数积分前是 1/T_0，不是 2/T_0。", ("fourier_series",)),
    _entry("B3_trigonometric_fs", "B", "三角形式傅里叶级数", (
        r"f(t)=\frac{a_0}{2}+\sum_{n=1}^{\infty}[a_n\cos(n\omega_0t)+b_n\sin(n\omega_0t)]",
        r"a_n=\frac{2}{T_0}\int_{t_0}^{t_0+T_0}f(t)\cos(n\omega_0t)dt",
        r"b_n=\frac{2}{T_0}\int_{t_0}^{t_0+T_0}f(t)\sin(n\omega_0t)dt",
    ), "实周期信号并满足傅里叶级数收敛条件。", "正弦与余弦在一个周期内正交。", "直流项写成 a_0/2。", ("fourier_series",)),
    _entry("B4_real_coefficients", "B", "实信号傅里叶级数系数性质", (
        r"F_{-k}=F_k^*",
        r"F_{-k}=F_k",
        r"F_{-k}=-F_k",
        r"F_n=\frac{a_n-jb_n}{2}",
        r"F_{-n}=\frac{a_n+jb_n}{2}",
    ), "第一式适用于实信号；第二式对应实偶信号，第三式对应实奇信号。", "实信号的正负频率系数共轭对称。", "实奇信号的系数通常为纯虚数，不能误判成实数。", ("fourier_series", "symmetry")),
    _entry("B5_periodic_ft", "B", "周期信号的傅里叶变换", (
        r"F(j\omega)=2\pi\sum_{k=-\infty}^{+\infty}F_k\delta(\omega-k\omega_0)",
    ), "按广义傅里叶变换理解。", "周期信号频谱是位于谐波频率处的冲激谱。", "不能漏掉 2\pi。", ("fourier_series", "fourier")),
    _entry("B6_discrete_period", "B", "离散正弦信号周期判断", (
        r"\omega_0N=2\pi m",
    ), "N 为正整数，m 为整数。", "离散正弦只有归一化角频率与 2\pi 比值为有理数时才周期。", "连续正弦总是周期，离散正弦不一定。", ("fourier_series", "discrete")),

    _entry("C1_ft_definition", "C", "傅里叶正变换与反变换", (
        r"F(j\omega)=\int_{-\infty}^{+\infty}f(t)e^{-j\omega t}dt",
        r"f(t)=\frac{1}{2\pi}\int_{-\infty}^{+\infty}F(j\omega)e^{j\omega t}d\omega",
    ), "经典意义下要求相应积分存在；广义信号按分布理解。", "正变换分析频率分量，反变换叠加重构信号。", "本约定的 1/(2\pi) 位于反变换。", ("fourier", "definition")),
    _entry("C2_impulse_constant", "C", "冲激与常数的傅里叶变换对", (
        r"\delta(t)\leftrightarrow1",
        r"1\leftrightarrow2\pi\delta(\omega)",
    ), "常数信号按广义傅里叶变换理解。", "两者互为对偶。", "常数信号的变换不能写成普通函数。", ("fourier", "pair", "priority")),
    _entry("C2_right_exponential", "C", "单边指数傅里叶变换对", (
        r"e^{-at}\varepsilon(t)\leftrightarrow\frac{1}{a+j\omega}",
    ), "a>0。", "直接在 [0,+\infty) 上积分指数函数。", "必须同时写出因果阶跃与 a>0。", ("fourier", "pair", "priority")),
    _entry("C2_right_exponential_powers", "C", "单边指数乘幂傅里叶变换对", (
        r"te^{-at}\varepsilon(t)\leftrightarrow\frac{1}{(a+j\omega)^2}",
        r"t^2e^{-at}\varepsilon(t)\leftrightarrow\frac{2}{(a+j\omega)^3}",
        r"t^ne^{-at}\varepsilon(t)\leftrightarrow\frac{n!}{(a+j\omega)^{n+1}}",
    ), "a>0，n 为非负整数。", "可由时域乘 t 的微分性质递推。", "分子是 n!，分母次数为 n+1。", ("fourier", "pair", "priority")),
    _entry("C2_two_sided_exponential", "C", "双边指数傅里叶变换对", (
        r"e^{-a|t|}\leftrightarrow\frac{2a}{a^2+\omega^2}",
    ), "a>0。", "把偶信号拆成正负半轴积分。", "不要与单边指数的复数分母混淆。", ("fourier", "pair", "priority")),
    _entry("C2_complex_exponential", "C", "复指数傅里叶变换对", (
        r"e^{j\omega_0t}\leftrightarrow2\pi\delta(\omega-\omega_0)",
    ), "按广义傅里叶变换理解。", "单一复指数对应单根谱线。", "谱线位于 +\omega_0，且系数为 2\pi。", ("fourier", "pair", "priority")),
    _entry("C2_sinusoid", "C", "余弦与正弦傅里叶变换对", (
        r"\cos(\omega_0t)\leftrightarrow\pi[\delta(\omega-\omega_0)+\delta(\omega+\omega_0)]",
        r"\sin(\omega_0t)\leftrightarrow\frac{\pi}{j}[\delta(\omega-\omega_0)-\delta(\omega+\omega_0)]",
    ), "按广义傅里叶变换理解。", "用欧拉公式把正弦与余弦写成两个复指数。", "正弦的两根谱线符号相反，并带 \pi/j。", ("fourier", "pair", "priority")),
    _entry("C2_rect", "C", "Sa 函数与矩形脉冲傅里叶变换对", (
        r"Sa(x)=\frac{\sin x}{x}",
        r"rect(\frac{t}{T})\leftrightarrow TSa(\frac{\omega T}{2})",
    ), "rect(t/T) 在 |t|<T/2 时为 1，在 |t|>T/2 时为 0。", "有限时间积分产生 sinc 形频谱。", "矩形脉冲宽度为 T，Sa 的自变量是 \omega T/2。", ("fourier", "pair", "priority")),
    _entry("C3_transform_premise", "C", "傅里叶变换性质的统一前提", (
        r"f(t)\leftrightarrow F(j\omega)",
    ), "以下性质均在相应变换存在的条件下使用。", "先确定一组已知变换对，再施加时移、频移、尺度或微积分运算。", "使用性质前不能忽略变换存在条件。", ("fourier",)),
    _entry("C3_time_shift", "C", "傅里叶变换时移性质", (
        r"f(t-t_0)\leftrightarrow e^{-j\omega t_0}F(j\omega)",
    ), "已知 f(t)\leftrightarrow F(j\omega)，且相应变换存在。", "变量代换后产生线性相位因子。", "时移不改变幅度谱，但指数符号容易写反。", ("fourier", "property", "priority")),
    _entry("C3_frequency_shift", "C", "傅里叶变换频移性质", (
        r"f(t)e^{j\omega_0t}\leftrightarrow F(j(\omega-\omega_0))",
        r"f(t)e^{-j\omega_0t}\leftrightarrow F(j(\omega+\omega_0))",
    ), "已知 f(t)\leftrightarrow F(j\omega)，且相应变换存在。", "时域调制使频谱整体平移。", "必须替换整个频域表达式中的 \omega。", ("fourier", "property", "priority")),
    _entry("C3_scaling_reversal", "C", "傅里叶变换尺度与时间反转", (
        r"f(at)\leftrightarrow\frac{1}{|a|}F(j\frac{\omega}{a})",
        r"f(-t)\leftrightarrow F(-j\omega)",
    ), "a\ne0，且相应变换存在。", "时间压缩对应频域扩展，积分变量代换产生尺度因子。", "尺度因子必须是 1/|a|。", ("fourier", "property", "priority")),
    _entry("C3_time_derivative", "C", "傅里叶变换时域微分", (
        r"\frac{df(t)}{dt}\leftrightarrow j\omega F(j\omega)",
        r"\frac{d^nf(t)}{dt^n}\leftrightarrow(j\omega)^nF(j\omega)",
    ), "边界项满足相应消失条件，或按广义变换理解。", "分部积分把微分转化为频域乘法。", "n 阶微分的因子是 (j\omega)^n。", ("fourier", "property")),
    _entry("C3_time_multiplication", "C", "傅里叶变换时域乘 t", (
        r"tf(t)\leftrightarrow j\frac{dF(j\omega)}{d\omega}",
        r"t^nf(t)\leftrightarrow j^n\frac{d^nF(j\omega)}{d\omega^n}",
    ), "频谱具有所需阶数的可微性。", "对频域核函数关于 \omega 求导。", "不要把 j^n 误写成 (-j)^n。", ("fourier", "property")),
    _entry("C3_duality", "C", "傅里叶变换对偶性质", (
        r"F(jt)\leftrightarrow2\pi f(-\omega)",
    ), "已知 f(t)\leftrightarrow F(j\omega)，并在本变换约定下使用。", "交换时域与频域后由反变换得到。", "F(jt) 表示把频谱表达式的自变量换成 t，并出现时间反转与 2\pi。", ("fourier", "property")),
    _entry("C3_convolution_multiplication", "C", "傅里叶变换卷积与相乘性质", (
        r"f(t)*g(t)\leftrightarrow F(j\omega)G(j\omega)",
        r"f(t)g(t)\leftrightarrow\frac{1}{2\pi}[F(j\omega)*G(j\omega)]",
    ), "相应卷积、乘积与变换存在。", "时域卷积对应频域相乘，时域相乘对应频域卷积。", "第二式不能漏掉 1/(2\pi)。", ("fourier", "property", "convolution")),
    _entry("C3_conjugate", "C", "傅里叶变换共轭性质", (
        r"f^*(t)\leftrightarrow F^*(-j\omega)",
        r"F(-j\omega)=F^*(j\omega)",
    ), "第二式要求 f(t) 为实信号。", "对变换积分取共轭会使指数核符号反转。", "实信号是频谱共轭对称，不一定是偶对称。", ("fourier", "property", "symmetry")),
    _entry("C4_frequency_response", "C", "系统频率响应", (
        r"H(j\omega)=\frac{Y(j\omega)}{X(j\omega)}",
        r"Y(j\omega)=H(j\omega)X(j\omega)",
        r"h(t)\leftrightarrow H(j\omega)",
    ), "LTI 系统零状态响应，且相关变换存在；比值式要求 X(j\omega)\ne0。", "卷积定理把时域系统运算变成频域乘法。", "有初始状态时不能把全响应直接写成 H(j\omega)X(j\omega)。", ("fourier", "system_function")),
    _entry("C5_affine_transform", "C", "尺度、时移与频移组合变换", (
        r"f(at-b)\leftrightarrow\frac{1}{|a|}e^{-j\omega b/a}F(j\frac{\omega}{a})",
        r"f(at-b)e^{j\omega_0t}\leftrightarrow\frac{1}{|a|}e^{-j(\omega-\omega_0)b/a}F(j\frac{\omega-\omega_0}{a})",
    ), "a\ne0，且相应变换存在。", "先把 f(at-b) 写成 f(a(t-b/a))，再依次使用尺度、时移和频移。", "频移后指数因子和 F 的自变量都要替换 \omega。", ("fourier", "property", "priority")),

    _entry("D1_lt_definition", "D", "单边拉普拉斯变换定义", (
        r"F(s)=\int_{0^-}^{+\infty}f(t)e^{-st}dt",
        r"s=\sigma+j\omega",
    ), "积分在某个收敛域内存在。", "指数核同时描述衰减与振荡。", "下限 0^- 用于保留原点冲激与初始条件。", ("laplace", "definition")),
    _entry("D2_basic_pairs", "D", "拉普拉斯基本变换对", (
        r"\varepsilon(t)\leftrightarrow\frac{1}{s}",
        r"e^{-at}\varepsilon(t)\leftrightarrow\frac{1}{s+a}",
        r"te^{-at}\varepsilon(t)\leftrightarrow\frac{1}{(s+a)^2}",
        r"t^ne^{-at}\varepsilon(t)\leftrightarrow\frac{n!}{(s+a)^{n+1}}",
        r"\cos(\omega_0t)\varepsilon(t)\leftrightarrow\frac{s}{s^2+\omega_0^2}",
        r"\sin(\omega_0t)\varepsilon(t)\leftrightarrow\frac{\omega_0}{s^2+\omega_0^2}",
        r"\operatorname{Re}(s)>-a",
    ), "因果信号使用单边变换；最后一式是右边指数信号的双边拉普拉斯 ROC。", "由指数积分及频移关系得到。", "变换式与 ROC 必须配套，余弦分子是 s，正弦分子是 \omega_0。", ("laplace", "pair")),
    _entry("D3_time_shift", "D", "拉普拉斯时移性质", (
        r"f(t-t_0)\varepsilon(t-t_0)\leftrightarrow e^{-st_0}F(s)",
    ), "t_0>0，采用对应的因果信号定义。", "积分变量平移产生 e^{-st_0}。", "不能漏掉延迟后的阶跃函数。", ("laplace", "property")),
    _entry("D3_derivatives", "D", "单边拉普拉斯时域微分", (
        r"f'(t)\leftrightarrow sF(s)-f(0^-)",
        r"f''(t)\leftrightarrow s^2F(s)-sf(0^-)-f'(0^-)",
    ), "单边拉普拉斯变换，初始值取 0^-。", "分部积分后边界项成为初始条件。", "二阶公式中两个初始项都不能漏。", ("laplace", "property", "initial_condition")),
    _entry("D3_integral_multiplication", "D", "拉普拉斯积分、乘 t 与卷积", (
        r"\int_0^t f(\tau)d\tau\leftrightarrow\frac{F(s)}{s}",
        r"tf(t)\leftrightarrow-\frac{dF(s)}{ds}",
        r"f(t)*g(t)\leftrightarrow F(s)G(s)",
    ), "第一式要求零初始积分状态；卷积式用于单边因果信号。", "积分对应除以 s，乘 t 对应对 s 求负导数。", "拉普拉斯乘 t 的导数前有负号。", ("laplace", "property", "convolution")),
    _entry("D4_initial_final_value", "D", "拉普拉斯初值与终值定理", (
        r"f(0^+)=\lim_{s\to\infty}sF(s)",
        r"f(\infty)=\lim_{s\to0}sF(s)",
    ), "必须检查定理适用条件；终值定理要求相应极点条件成立。", "极限从变换域提取时间端点行为。", "终值定理不能用于发散或持续振荡响应。", ("laplace", "property", "stability")),
    _entry("D5_ct_system_function", "D", "连续时间系统函数", (
        r"H(s)=\frac{Y(s)}{X(s)}",
        r"a_2y''+a_1y'+a_0y=b_1x'+b_0x",
        r"H(s)=\frac{b_1s+b_0}{a_2s^2+a_1s+a_0}",
        r"\operatorname{Re}(p_i)<0",
        r"H(j\omega)=H(s)",
    ), "比值和微分方程推导采用零初始条件；因果有理系统稳定时极点严格位于左半平面；双边 ROC 包含虚轴时可代入 s=j\omega。", "微分方程经拉普拉斯变换成为代数方程。", "不能在 ROC 不含虚轴时直接声称频率响应存在。", ("laplace", "system_function", "stability")),

    _entry("E1_z_definition", "E", "双边 Z 变换定义", (
        r"X(z)=\sum_{n=-\infty}^{+\infty}x[n]z^{-n}",
    ), "级数在相应收敛域内收敛。", "Z 变换是序列按 z^{-n} 加权的双边级数。", "只给代数式而不说明 ROC 通常不完整。", ("z_transform", "definition")),
    _entry("E2_z_pairs", "E", "Z 变换基本对与 ROC", (
        r"\delta[n]\leftrightarrow1",
        r"\varepsilon[n]\leftrightarrow\frac{z}{z-1}",
        r"a^n\varepsilon[n]\leftrightarrow\frac{z}{z-a}",
        r"na^n\varepsilon[n]\leftrightarrow\frac{az}{(z-a)^2}",
        r"|z|>|a|",
        r"|z|>1",
    ), "右边指数序列 ROC 为 |z|>|a|；单位阶跃序列 ROC 为 |z|>1。", "对几何级数求和，并可用乘 n 性质得到第四式。", "必须区分右边、左边和双边序列的 ROC。", ("z_transform", "pair", "roc")),
    _entry("E3_z_properties", "E", "双边 Z 变换性质", (
        r"x[n-n_0]\leftrightarrow z^{-n_0}X(z)",
        r"a^nx[n]\leftrightarrow X(\frac{z}{a})",
        r"nx[n]\leftrightarrow-z\frac{dX(z)}{dz}",
        r"x[n]*h[n]\leftrightarrow X(z)H(z)",
    ), "相应级数与 ROC 存在，且运算后的 ROC 需另行判断。", "由定义换元、求导和交换求和次序得到。", "乘 n 性质前有负号，移位还会影响 ROC。", ("z_transform", "property")),
    _entry("E4_unilateral_z", "E", "单边 Z 变换与移位", (
        r"X(z)=\sum_{n=0}^{+\infty}x[n]z^{-n}",
        r"Z\{x[n+1]\}=zX(z)-zx[0]",
        r"Z\{x[n-1]\}=z^{-1}X(z)+x[-1]",
    ), "采用单边 Z 变换定义，初始条件按给定索引解释。", "改变求和起点会产生边界初始项。", "单边与双边移位公式不同，不能漏掉初始条件。", ("z_transform", "property", "initial_condition")),
    _entry("E5_dt_system_function", "E", "离散时间系统函数与稳定性", (
        r"y[n]+a_1y[n-1]+a_2y[n-2]=b_0x[n]+b_1x[n-1]",
        r"H(z)=\frac{b_0+b_1z^{-1}}{1+a_1z^{-1}+a_2z^{-2}}",
        r"H(e^{j\omega})=H(z)",
        r"|p_i|<1",
    ), "系统函数采用零初始条件；频率响应要求单位圆包含于 ROC；因果有理系统 BIBO 稳定时所有极点位于单位圆内。", "差分方程经 Z 变换成为代数方程。", "仅看极点模长而不结合因果性与 ROC 可能误判。", ("z_transform", "system_function", "stability")),

    _entry("F1_energy_power", "F", "信号能量与周期信号平均功率", (
        r"E=\int_{-\infty}^{+\infty}|x(t)|^2dt",
        r"E=\sum_{n=-\infty}^{+\infty}|x[n]|^2",
        r"P=\frac{1}{T}\int_0^T|x(t)|^2dt",
    ), "前两式用于连续和离散能量信号；第三式用于周期功率信号。", "平方模积分或求和衡量总能量，周期平均得到功率。", "周期信号通常能量无穷，但平均功率有限。", ("energy", "power")),
    _entry("F2_parseval", "F", "帕塞瓦尔定理", (
        r"E=\frac{1}{2\pi}\int_{-\infty}^{+\infty}|X(j\omega)|^2d\omega",
        r"P=\sum_{k=-\infty}^{+\infty}|F_k|^2",
    ), "第一式用于非周期能量信号，第二式用于周期信号。", "正交变换保持能量或平均功率。", "连续傅里叶变换约定下不能漏掉 1/(2\pi)。", ("spectrum", "energy", "power")),
    _entry("F3_correlation", "F", "能量信号自相关与互相关", (
        r"R_{xx}(\tau)=\int_{-\infty}^{+\infty}x(t+\tau)x^*(t)dt",
        r"R_{xy}(\tau)=\int_{-\infty}^{+\infty}x(t+\tau)y^*(t)dt",
        r"R_{xx}(\tau)\leftrightarrow|X(j\omega)|^2",
        r"R_{xy}(\tau)\leftrightarrow X(j\omega)Y^*(j\omega)",
    ), "采用能量信号相关定义；功率信号应使用时间平均相关函数与功率谱密度。", "相关可视为信号与共轭时间反转信号的卷积。", "互相关的共轭对象与变量次序会决定频域乘积顺序。", ("correlation", "spectrum")),
    _entry("F4_sampling", "F", "采样定理与理想冲激采样", (
        r"f_s=\frac{1}{T_s}",
        r"f_s>2f_m",
        r"\omega_s>2\omega_m",
        r"x_s(t)=\sum_{n=-\infty}^{+\infty}x(nT_s)\delta(t-nT_s)",
        r"X_s(j\omega)=\frac{1}{T_s}\sum_{k=-\infty}^{+\infty}X(j(\omega-k\omega_s))",
    ), "输入严格带限，理想无混叠采样使用严格大于两倍最高频率的条件。", "时域与冲激列相乘，对应频域周期复制。", "角频率与普通频率不能混用，频谱复制系数是 1/T_s。", ("sampling", "fourier")),
    _entry("F5_distortionless", "F", "无失真传输", (
        r"H(j\omega)=Ke^{-j\omega t_0}",
        r"y(t)=Kx(t-t_0)",
    ), "关系只需在输入信号占用的频带内成立。", "恒定幅度增益与线性相位只改变尺度和延迟。", "不要错误地要求系统在所有频率上都满足该形式。", ("system_function", "fourier")),
)

FORMULA_BY_KEY = {entry["key"]: entry for entry in FORMULA_LIBRARY}
FOURIER_DAILY_KEYS = tuple(
    entry["key"]
    for entry in FORMULA_LIBRARY
    if entry["section"] == "C" and ("pair" in entry["tags"] or "property" in entry["tags"])
)
