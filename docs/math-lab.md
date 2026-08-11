# Math Lab

Math Lab 是 Learning OS 内的按需数学可视化工作区。它不是常驻监控面板：进入应用、查看热力图或打开 Markdown 时都不会初始化数学渲染器。用户从侧栏进入 `Math Lab`，或在沉浸式 Markdown 阅读器中点击 `OPEN MATH LAB` 后，才加载工作区外壳；具体模块和重型引擎在再次选择模块后加载。

## 架构

```text
App.vue
  └─ async MathLabView
       ├─ CapabilityDetector + quality policy
       ├─ async module component
       └─ pure MathScene
            ↓
          rendererFactory
            ├─ CanvasRenderer
            ├─ CindyAdapter → CindyJS/CindyGL
            ├─ MathBoxAdapter → isolated same-origin iframe
            └─ ThreeRenderer → modern Three.js
```

`MathLabView.vue` 只负责模块选择、性能档位和生命周期。数学计算放在 `core/`，模块控制器放在 `modules/`，渲染实现放在 `renderers/` 或 `adapters/`。`MathScene` 只包含数字、字符串、布尔值和数组，不持有 DOM、Vue Ref 或任一版本的 Three 对象。

MathBox 使用 Three 0.139.2，但被放进同源 iframe 渲染舱；主窗口里的现代 Three 0.185.1 与它不共享 singleton 或 GPU 对象。父页面只通过 `postMessage` 发送纯数据 SurfaceScene。退出模块时 renderer 会执行 `dispose()`；iframe、WebGL context、监听器、ResizeObserver 和 Timeline RAF 一并释放。

## 模块

- Linear Transform：2×2 矩阵、变换网格、单位正方形、基向量、任意向量、行列式、方向翻转和实特征方向。动画严格使用 `A(t)=(1-t)I+tA`。
- Complex Mapping：z/w 双平面、可拖动复点、预设函数、极点/分支保护和 domain coloring。Balanced/High 优先 CindyGL；Low/Compatibility 使用可缓存的 CPU Canvas 光栅。
- Fourier：时域、复平面绕行、数值 Fourier 积分、幅度/相位和 `fft.js` 离散频谱。
- Laplace：显示 `f(t)e^{-σt}e^{-iωt}` 的衰减、旋转、s 平面位置和数值积分结果。
- 3D Surface：预设曲面、轨道控制、缩放、网格/曲面切换和自动旋转。High 走现代 Three，Balanced 走隔离 MathBox，其他档位走 Canvas 投影。

三维模块还提供安全的自定义 `z=f(x,y)`。只有点击 `APPLY EXPRESSION` 时才加载 math.js。表达式先解析 AST，再检查节点、运算符、符号和函数白名单；赋值、函数定义、属性访问和任意对象遍历会被拒绝。通过验证后只把有限实数采样网格交给 renderer。表达式失败时保留上一帧有效曲面。

## 时间轴与交互

所有动画共用 `Timeline` 控制器，支持播放、暂停、重置、拖动、0.25–2 倍速度、反向和循环。页面隐藏时停止 RAF；恢复时重置时间基准，避免一次累计巨大的 `dt`。开启系统 `prefers-reduced-motion` 时不自动播放，仍可手动拖动时间轴。

Math Lab 可以从 Markdown 原生 `<dialog>` 顶层阅读环境进入。阅读正文的 `.reading-portal-scroll` 是唯一纵向滚动容器，背景在 modal 打开时处于 inert 状态；滚轮、指针和触摸事件还会在 portal 边界停止传播。退出键始终保留在固定头部。

每个 KaTeX 行内或块级公式都会获得一个轻量 `↗` 入口。`formulaRouter` 只使用字符串特征判断 Linear、Complex、Fourier、Laplace/Integral 或 Surface，不加载数学 vendor。路由面板显示自动判断和置信度，用户可以覆盖分类；确认后才创建 Math Lab 模块。数字矩阵、常见复函数、信号预设和三维公式会尽可能转换为模块初始状态，原公式始终显示在工作区导入栏中。

## 质量档位与回退

| 档位 | 目标 FPS | 最大 DPR | Surface | Complex | 典型路径 |
| --- | ---: | ---: | ---: | ---: | --- |
| Compatibility | 30 | 1 | 26 | 224 | Canvas only |
| Low | 40 | 1 | 48 | 384 | Canvas / reduced CPU work |
| Balanced | 60 | 1.5 | 88 | 672 | MathBox / CindyGL |
| High | 90 | 2 | 160 | 1024 | modern Three / CindyGL |

Auto 只做能力检测，不进行 UA 猜测。它检查 WebGPU、WebGL2/WebGL1、Canvas2D、逻辑核心数、可用设备内存、DPR 和 reduced-motion。持续慢帧 3 秒后降档；持续快帧 9 秒后才升档，避免频繁来回切换。任何 adapter 初始化失败都会显示英文错误并退回 Canvas，不能让用户只看到空白画布。

## 增加场景或 primitive

1. 在 `types.ts` 增加纯数据 scene，并并入 `MathScene` union。
2. 在 `modules/<domain>/` 创建独立 Vue 控制器，不要把算法塞入 `MathLabView.vue`。
3. 至少在 `CanvasRenderer` 增加兼容实现；若需要 GPU，再新增或扩展 adapter。
4. 在 `rendererFactory.ts` 基于 scene、quality 和 capability 选择路径。
5. 数值算法放在 `core/` 并补充 Vitest。不要把 renderer 对象写进 scene。
6. 实现 `resize`、`pause`、`resume`、`dispose`，并验证反复进入/退出不会增加 RAF、监听器或 WebGL context。

## 性能规则

- 工作区、模块、renderer 与 math.js 都使用异步边界；默认页面不请求任何数学 vendor 文件。
- Canvas domain coloring 以函数和分辨率为键缓存，不因拖动复点重复创建大 ImageData。
- Three 曲面只在表达式或分辨率改变时重建 geometry；相机交互只更新已有资源。
- FFT 只在 Fourier 模块载入后执行，并复用离散频谱，不在每个绘制帧执行 DFT。
- ResizeObserver、visibility pause 和 renderer generation token 防止竞态、后台耗电和过期初始化覆盖。
- 精度与显示密度分开；低档只降低采样/像素密度，不改变行列式、复数、积分等核心公式。

## 调试

工作区底部的 `RENDERER DIAGNOSTICS` 可查看 renderer、质量档位、FPS、frame time、DPR、viewport、surface 和 curve samples。排查时优先切换到 Compatibility，确认 Canvas 路径是否正常；再检查 WebGL capability、控制台 context-lost 信息和 `/static/app/vendor/math-lab/` 文件是否可访问。
