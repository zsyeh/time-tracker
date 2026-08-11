# Codex Prompt — 在 `zsyeh/time-tracker` 中集成高性能数学可视化 Math Lab

## 0. 你的角色

你是一名高级全栈工程师、Web 图形工程师、科学计算工程师和数学可视化架构师。

你现在不是创建一个新项目，而是要在现有仓库中增量实现一个新的 **Math Lab / Interactive Mathematical Visualization Engine**：

- 仓库：`https://github.com/zsyeh/time-tracker.git`
- 现有产品：Personal Learning OS / time-tracker
- 必须与现有项目的技术栈、认证、部署、Docker、静态资源路径、UI 风格和数据隔离机制兼容
- 禁止为了实现数学可视化而重写现有项目
- 禁止另起 React/Next.js/独立 SPA
- 禁止破坏当前学习计时、历史记录、搜索、Passkey、邀请码、Launch Token、导出、Django Admin、Docker 部署等任何已有功能

目标是在现有 Learning OS 内增加一个独立、懒加载、可扩展的 **Math Lab** 页面，并建立后续可持续扩展的数学可视化内核。

---

# 1. 开工前必须先读取现有仓库

不要仅根据本提示词猜测项目结构。

首先检查当前工作树和仓库实际状态：

```bash
git status
git branch --show-current
git log -1 --oneline
```

然后至少阅读：

```text
README.md
docs/architecture.md
docs/deployment.md
frontend/package.json
frontend/package-lock.json
frontend/vite.config.ts
frontend/src/main.ts
frontend/src/App.vue
frontend/src/styles.css
frontend/src/lib/api.ts
Dockerfile
requirements.txt
```

并搜索与以下内容相关的现有实现：

```text
defineAsyncComponent
PageName
nav
theme
CSS variables
ECharts
KaTeX
ResizeObserver
mobile
static/app
frontend/dist
```

如果仓库在执行本任务时已经发生变化，以**当前仓库实际代码**为准，本提示词中的具体文件名或代码片段只是当前已知基线，不得覆盖更新后的架构。

如果工作树已有用户未提交修改：

- 不得 `git reset --hard`
- 不得覆盖无关文件
- 不得丢弃用户修改
- 不得使用强制 checkout 恢复整个文件
- 只做与本任务直接相关的最小增量变更

---

# 2. 当前项目基线：必须保持兼容

当前仓库是一个 monorepo / modular monolith：

```text
Browser
   ↓
Nginx / TLS
   ↓
Vue 3 static frontend + Django same-origin API
   ↓
relational database
```

当前主要前端技术：

```text
Vue 3
TypeScript
Vite
Element Plus
ECharts
KaTeX
markdown-it
highlight.js
```

当前后端：

```text
Django
Django REST Framework
django-allauth / Passkey / WebAuthn
SQLite / PostgreSQL
```

当前构建模式：

```text
frontend/
    npm build
        ↓
frontend/dist
        ↓
Django / Docker production image
```

Vite 当前静态资源 base：

```text
/static/app/
```

必须保留。

当前应用不是基于 Vue Router 的多路由 SPA，而是在 `App.vue` 内使用类似：

```ts
type PageName = 'today' | 'trends' | 'history' | 'issues' | 'settings'
const page = ref<PageName>('today')
```

并用：

```ts
defineAsyncComponent(...)
```

懒加载主要 View。

**第一阶段不要为了 Math Lab 引入 Vue Router。**

新 Math Lab 应按照现有导航模型集成：

```text
Today
Trends
Sessions
Issues
Math Lab
Settings
```

推荐增加：

```ts
const MathLabView = defineAsyncComponent(() => import('./views/MathLabView.vue'))
```

并扩展 `PageName`。

保持原有页面行为不变。

---

# 3. 关键工程目标

新增 Math Lab，但不能让它污染 Learning OS 核心。

整个系统应形成：

```text
Existing Learning OS
│
├── Today
├── Trends
├── Sessions
├── Issues
├── Math Lab  ← 新增
└── Settings

Math Lab
│
├── Vue UI shell
│
├── Math Visualization Core
│   ├── Math engine
│   ├── Scene model
│   ├── Animation timeline
│   ├── Performance manager
│   └── Renderer abstraction
│
├── Cindy adapter
├── MathBox adapter
├── Three.js renderer
├── Canvas compatibility renderer
│
└── Modules
    ├── Linear Algebra
    ├── Complex Analysis
    ├── Fourier
    ├── Laplace
    └── 3D Surfaces
```

Math Lab 第一阶段应尽量是**纯前端功能**。

除非确有必要：

- 不新增数据库表
- 不新增 Django migration
- 不新增后端 API
- 不修改认证模型
- 不修改 Session / Passkey 逻辑
- 不改变 CSRF / same-origin 机制

后续若需要“保存自定义数学场景”，再单独设计后端持久化；本次 MVP 不要因为保存功能扩大改动范围。

---

# 4. CindyJS 与 MathBox：必须各取所长，但必须隔离

核心原则：

> 不把 CindyJS、MathBox、Three.js 直接混成一个不可维护的渲染层。

必须建立 adapter。

## 4.1 CindyJS / CindyGL 的职责

优先用于：

- 复数函数
- 双复平面映射
- Domain Coloring
- 数学表达式驱动的几何关系
- GPU 上执行大量独立数学函数采样
- 复分析场景
- 高交互动态数学对象

典型场景：

```text
z-plane              w-plane
   z        f(z)         w
   ●   ───────────→      ●
```

用户拖动：

```text
point
curve
circle
grid
region
```

右侧实时显示：

```text
w = f(z)
```

支持示例：

```text
z
z^2
1/z
exp(z)
sin(z)
cos(z)
log(z)
```

Domain Coloring：

```text
Hue        ← arg(f(z))
Brightness ← |f(z)| 的平滑映射
```

CindyJS/CindyGL 必须通过：

```text
CindyAdapter
```

进入系统。

业务层不得散落：

```js
CindyJS(...)
```

调用。

---

# 5. MathBox 的职责

MathBox 的强项用于：

- 数学坐标系
- Axis
- Grid
- Vector
- Point
- Curve
- Surface
- Interval
- Area
- Transform
- Camera
- 数学动画 Scene Graph
- 参数随时间演化

特别适合：

```text
线性变换
参数曲线
3D 曲面
向量
坐标网格
连续数学动画
```

核心思想：

> 数学状态驱动几何，而不是预制视觉 morph。

例如线性变换：

```math
A(t) = (1-t)I + tA
```

所有点：

```math
x(t) = A(t)x
```

所以：

```text
grid
basis vectors
unit square
arbitrary vectors
```

都来自同一个数学状态。

---

# 6. MathBox / Three.js 兼容性：这是硬性要求

不要默认最新版 MathBox 可以安全地和最新版 Three.js 共用同一个运行时实例。

在安装任何依赖前：

```bash
npm view mathbox version
npm view mathbox dependencies
npm view mathbox peerDependencies
npm view three version
npm view cindyjs version
npm view mathjs version
```

并检查：

```bash
npm explain three
npm ls three
```

安装后再次检查依赖树。

必须输出：

```text
docs/math-renderer-compatibility.md
```

记录：

```text
CindyJS version
CindyGL availability
MathBox version
MathBox expected Three.js range
modern Three.js version
math.js version
FFT library version
Node compatibility
Vite compatibility
browser compatibility
license
fallback path
known limitations
```

## 6.1 禁止的做法

禁止：

- 为兼容 MathBox 把整个现有项目锁死到明显过时的 Three.js
- 把 MathBox 内部 Three 对象传给现代 Three renderer
- 依赖 `window.THREE`
- 在全局制造互相冲突的 THREE singleton
- 改 Vite 配置只是为了掩盖依赖冲突
- 把 `chunkSizeWarningLimit` 无限调大来隐藏 bundle 问题

## 6.2 推荐兼容策略

优先顺序：

### Strategy A

如果当前 MathBox 与选定 Three.js 能稳定共存：

```text
MathBoxAdapter
        ↓
MathBox
        ↓
compatible Three
```

正常使用。

### Strategy B

如果 npm 依赖树中存在不同 Three.js 版本，但包管理器能够隔离：

允许 MathBox 使用自己的 Three 实例。

但：

```text
MathBox objects
≠
Modern Three objects
```

两边只能交换纯数据：

```ts
type Vec3 = readonly [number, number, number]

interface SurfaceData {
  positions: Float32Array
  indices?: Uint32Array
}
```

不得交换：

```text
THREE.Vector3
THREE.Mesh
THREE.Material
```

### Strategy C

如果直接使用 MathBox 会产生严重兼容问题：

保留：

```text
MathBoxAdapter
```

但只让需要 MathBox 的场景走专用渲染路径。

必要时可将其隔离为独立 canvas / 独立 bundle。

只有在确实无法避免全局冲突时，才考虑 iframe 隔离。

### Strategy D

如果某一个 MathBox primitive 的直接使用成本明显高于重写成本：

允许在现代 Three.js 上重新实现该 primitive。

但必须：

- 保留统一 Scene API
- 在文档说明原因
- MathBox 仍应用于它真正擅长且兼容的场景
- 不允许因为一个兼容问题直接删除整个 MathBox adapter

---

# 7. 现代 Three.js 的定位

现代 Three.js 是高性能通用渲染主干，不取代 Cindy 或 MathBox 的专业能力。

主要用于：

- 高性能 3D
- 大型 surface
- GPU instancing
- shader
- WebGPU
- 高密度 vector field
- 大量 mesh / points
- 高频 buffer update

架构：

```text
Math Scene
   ↓
Renderer Adapter
   ├── Canvas2D
   ├── Cindy
   ├── MathBox
   ├── Three WebGL
   └── Three WebGPU
```

不要让业务组件直接：

```ts
import * as THREE from 'three'
```

然后到处操作 Scene。

Three.js 调用应集中在 renderer / primitive adapter 内。

---

# 8. 不允许引入另一个前端框架

本项目已经是 Vue 3。

严禁增加：

```text
React
React Three Fiber
Next.js
Nuxt
Svelte
Angular
```

数学可视化 UI 必须继续使用：

```text
Vue 3
<script setup lang="ts">
Composition API
Element Plus
```

现有 ECharts 和 KaTeX 应继续复用。

例如：

- 普通静态频谱 / 数据统计：可以继续用 ECharts
- 数学公式：继续用 KaTeX
- 参数输入：Element Plus
- 高性能实时数学图形：Cindy / MathBox / Three / Canvas

不要因为 Math Lab 重复安装第二套 UI framework 或第二套公式 renderer。

---

# 9. 新模块目录

尽量建立独立子系统，建议：

```text
frontend/src/
│
├── views/
│   └── MathLabView.vue
│
└── math-visualizer/
    │
    ├── index.ts
    │
    ├── types.ts
    │
    ├── core/
    │   ├── MathEngine.ts
    │   ├── Scene.ts
    │   ├── Timeline.ts
    │   ├── PerformanceManager.ts
    │   ├── CapabilityDetector.ts
    │   └── quality.ts
    │
    ├── renderers/
    │   ├── MathRenderer.ts
    │   ├── CanvasRenderer.ts
    │   ├── ThreeRenderer.ts
    │   └── rendererFactory.ts
    │
    ├── adapters/
    │   ├── CindyAdapter.ts
    │   └── MathBoxAdapter.ts
    │
    ├── primitives/
    │   ├── Axis.ts
    │   ├── Grid.ts
    │   ├── Point.ts
    │   ├── Vector.ts
    │   ├── Curve.ts
    │   ├── Surface.ts
    │   └── VectorField.ts
    │
    ├── modules/
    │   ├── linear-algebra/
    │   ├── complex-analysis/
    │   ├── fourier/
    │   ├── laplace/
    │   └── surfaces/
    │
    ├── components/
    │   ├── VisualizationViewport.vue
    │   ├── MathToolbar.vue
    │   ├── PerformanceSelector.vue
    │   ├── TimelineControls.vue
    │   └── RendererDebugPanel.vue
    │
    └── styles/
        └── math-lab.css
```

具体目录可根据现有代码风格调整，但核心隔离原则不能丢。

---

# 10. Lazy Load：不能拖慢 Learning OS 首页

这是硬性要求。

当前 Learning OS 首页和计时器是高频入口。

用户没有进入 Math Lab 时：

```text
CindyJS
CindyGL
MathBox
Three.js
math.js heavy modules
FFT
```

不应该全部进入首屏 bundle。

至少做到：

```ts
const MathLabView = defineAsyncComponent(
  () => import('./views/MathLabView.vue')
)
```

在 Math Lab 内继续按需加载：

```text
Complex scene
    ↓ lazy import Cindy

3D scene
    ↓ lazy import Three / MathBox

Fourier scene
    ↓ lazy import FFT implementation
```

检查 Vite build 输出。

目标：

- Existing dashboard initial chunk 增幅尽量小
- 数学引擎拆分为异步 chunk
- 不通过修改 `chunkSizeWarningLimit` 掩盖问题

---

# 11. UI 集成方式

在现有 sidebar 中增加：

```text
Math Lab
```

不要重做整个 sidebar。

移动端已有 Menu，也必须自动出现 Math Lab。

Math Lab 页面内部建议：

```text
┌─────────────────────────────────────────────────────────────┐
│ Math Lab                            Mode: Auto / Balanced    │
├──────────────┬──────────────────────────────────────────────┤
│ Modules      │                                              │
│              │              Visualization                   │
│ Linear Alg.  │                                              │
│ Complex      │                                              │
│ Fourier      │                                              │
│ Laplace      │                                              │
│ 3D Surface   │                                              │
│              │                                              │
├──────────────┴──────────────────────────────────────────────┤
│ Expression / Parameters / Timeline                          │
└─────────────────────────────────────────────────────────────┘
```

在窄屏：

```text
module selector
controls
viewport
timeline
```

纵向排列。

必须支持：

```text
desktop
iPad
mobile
```

不要要求固定 viewport width。

使用：

```text
ResizeObserver
```

驱动 renderer resize。

不要只监听 `window.resize`。

---

# 12. UI 风格必须继承现有项目

先阅读：

```text
frontend/src/styles.css
```

并复用已有：

```text
CSS variables
panel style
spacing
border
background
theme colors
dark/light logic
```

Math Lab 不要突然变成完全不同的 Material / gaming dashboard。

要求：

```text
Learning OS 原有视觉语言
+
scientific visualization workspace
```

不要大量使用：

```text
gradient
glow
neon
glassmorphism
```

数学对象可以有高对比颜色，但 UI 本身保持克制。

---

# 13. 五种模式

必须支持：

```text
Auto
Compatibility
Low
Balanced
High
```

其中 Auto 是默认。

UI 必须允许用户手动覆盖。

用户手动选择后，本次页面会话内保持，不需要第一阶段写入服务器。

可使用简单的 Vue state；如确实需要持久化，可使用现有设置体系之前先评估，不要未经设计扩展后端。

---

# 14. CapabilityDetector

创建：

```ts
interface RuntimeCapabilities {
  webgpu: boolean
  webgl2: boolean
  webgl1: boolean
  canvas2d: boolean
  reducedMotion: boolean
  devicePixelRatio: number
  hardwareConcurrency?: number
  deviceMemoryGb?: number
}
```

检测：

```text
navigator.gpu
WebGL2 context
WebGL context
Canvas2D
devicePixelRatio
navigator.hardwareConcurrency
navigator.deviceMemory（存在时）
prefers-reduced-motion
```

不要用 UA 字符串决定 GPU 模式。

不要假设：

```text
iPhone = low
Mac = high
Chrome = WebGPU
```

一律 capability detection。

---

# 15. PerformanceManager

创建统一性能管理器。

建议：

```ts
type QualityTier =
  | 'compatibility'
  | 'low'
  | 'balanced'
  | 'high'

interface QualityProfile {
  tier: QualityTier
  targetFps: number
  maxDpr: number
  curveSamples: number
  surfaceResolution: number
  vectorFieldDensity: number
  complexResolution: number
  enableGpuEvaluation: boolean
  enableAntialias: boolean
}
```

不要把每个场景自己的 magic number 散落在组件里。

---

# 16. Auto 模式

Auto 不能只靠硬件名称。

初始策略：

```text
capability detection
        ↓
initial tier
        ↓
lightweight runtime benchmark
        ↓
runtime frame-time feedback
```

启动 benchmark 必须：

- 足够轻
- 不明显阻塞页面
- 不长期占用 GPU
- 不在 Learning OS 首页执行
- 只有进入 Math Lab 后才运行

测量：

```text
frame time
simple geometry throughput
basic shader throughput
```

不要为了 benchmark 制造高温/高负载。

---

# 17. Compatibility 模式

目标：

> 即使 GPU 能力弱，也能理解数学，而不是简单显示“设备不支持”。

优先：

```text
Canvas2D / SVG / existing ECharts
```

若 WebGL 可用且稳定，可使用非常低质量 GPU 路径。

建议默认：

```text
DPR <= 1
target FPS ≈ 30
curveSamples ≈ 200–400
surfaceResolution ≈ 24–32
vectorFieldDensity ≈ 10–15
complexResolution ≈ 192–256
```

关闭：

```text
high-density surface
expensive shader
large render targets
high DPR
post processing
dynamic shadow
visual-only effects
```

3D 如果无法稳定创建 WebGL：

允许降级为：

```text
CPU projection
wireframe
reduced interaction
```

但必须明确显示：

```text
Compatibility renderer
```

不要直接白屏。

---

# 18. Low 模式

目标设备：

```text
普通手机
低功耗笔记本
老核显
低性能 WebView
```

优先：

```text
WebGL2
```

否则降级。

建议：

```text
DPR <= 1
target FPS = 30–45
curveSamples = 400–700
surfaceResolution = 40–56
vectorFieldDensity = 16–22
complexResolution = 320–448
```

关闭纯视觉特效。

---

# 19. Balanced 模式

默认体验目标：

```text
现代核显
Apple Silicon
主流桌面
现代手机 / iPad
```

优先：

```text
WebGPU（只有实现成熟且稳定时）
        ↓
WebGL2
```

MathBox / CindyGL 可在适合它们的场景中工作。

建议：

```text
DPR <= 1.5
target FPS = 60
curveSamples = 800–1500
surfaceResolution = 80–112
vectorFieldDensity = 26–36
complexResolution = 640–800
```

---

# 20. High 模式

目标：

```text
高性能桌面 GPU
现代独显
高性能 Apple Silicon
高刷新率设备
```

优先使用现代 Three.js WebGPU 路径处理重型 3D。

建议：

```text
DPR <= min(devicePixelRatio, 2)
target FPS = 60 / 90 / 120 adaptive
curveSamples = 1500–4000
surfaceResolution = 144–224
vectorFieldDensity = 40–64
complexResolution = 1024+
```

但：

> High 不等于堆没有数学价值的画质效果。

不要为了“高性能模式”加入：

```text
bloom
SSAO
cinematic shadows
lens flare
```

除非它们真正帮助理解数学。

---

# 21. 动态自动降级

持续测量最近约：

```text
60–120 frames
```

使用：

```text
EMA / moving average
```

而不是单帧波动。

例如：

```text
平均 frame time > 22 ms 持续 3 秒
```

逐级减少：

```text
render resolution
surface density
curve sampling
vector density
```

如果：

```text
平均 frame time < 10–12 ms 持续 8–12 秒
```

再逐步提高。

必须有 hysteresis。

禁止：

```text
High → Balanced → High → Balanced
```

每秒抖动。

---

# 22. prefers-reduced-motion

如果：

```css
prefers-reduced-motion: reduce
```

则：

- 不自动播放长动画
- 默认降低运动速度
- 保留数学状态拖动和手动 timeline
- 不删除功能

Accessibility 与性能模式是两个维度，不要混为一谈。

---

# 23. Renderer abstraction

定义尽量小而稳定的接口：

```ts
export interface MathRenderer {
  readonly id: string

  init(container: HTMLElement): Promise<void>

  resize(width: number, height: number, dpr: number): void

  setQuality(profile: QualityProfile): void

  render(scene: MathScene, time: number): void

  pause(): void

  resume(): void

  dispose(): void
}
```

允许按 renderer 能力增加 capability 描述：

```ts
interface RendererCapabilities {
  supports3D: boolean
  supportsComplexGpu: boolean
  supportsInstancing: boolean
  supportsWebGPU: boolean
}
```

不要制造 100 个所有 renderer 都无法实现的方法。

---

# 24. Math Scene：使用纯数据模型

核心 scene 不应该持有：

```text
THREE.Mesh
Cindy object
MathBox primitive
DOM element
Vue Ref
```

Scene 应尽量是纯数学数据：

```ts
interface VectorPrimitive {
  kind: 'vector'
  from: readonly [number, number, number]
  to: readonly [number, number, number]
}

interface GridPrimitive {
  kind: 'grid'
  dimensions: 2 | 3
  range: readonly [number, number]
}
```

renderer 把 Scene 转换成实际 GPU/Canvas 对象。

---

# 25. MathEngine

引入或封装 `math.js`，但必须 lazy load 到 Math Lab chunk。

创建：

```text
MathEngine
```

负责：

```text
complex arithmetic
matrix
determinant
eigenvalues / eigenvectors
expression parsing
function sampling
numerical integration
basic linear algebra
```

FFT 可以使用独立、轻量、许可兼容的库。

依赖加入前检查 license。

现有项目是 GPL-3.0-or-later，因此禁止加入许可证冲突的依赖。

---

# 26. 用户表达式安全

用户可以输入：

```text
sin(x)
exp(-x^2)
z^2 + 1/z
```

严禁：

```js
eval(...)
new Function(...)
```

即使 math.js 本身提供 expression parser，也必须构建限制层。

建议：

```text
parse expression
        ↓
inspect AST
        ↓
whitelist node types
        ↓
whitelist symbols/functions
        ↓
compile
```

允许的典型函数：

```text
sin
cos
tan
asin
acos
atan
sinh
cosh
tanh
exp
log
sqrt
abs
arg
re
im
conj
```

拒绝：

```text
assignment
function assignment
property access
arbitrary object traversal
import
createUnit
evaluate nested source strings
```

错误表达式：

- UI 显示错误
- renderer 保持上一帧有效场景
- 不导致整个 Math Lab 崩溃

---

# 27. Timeline

不要让每个数学模块自己写 RAF。

创建：

```text
Timeline
AnimationController
```

统一：

```text
play
pause
reset
scrub
speed
reverse
loop
```

内部：

```text
t ∈ [0, 1]
```

模块使用：

```ts
getState(t)
```

计算数学状态。

Vue 不应该在 60/120 FPS 下更新全部响应式组件。

高频 frame state：

```text
renderer / animation controller
```

低频 UI state：

```text
Vue
```

---

# 28. RAF 生命周期

Math Lab 不可见时：

```text
pause RAF
```

浏览器 tab hidden：

```text
document.visibilityState
```

自动 pause。

恢复时：

- 继续渲染
- 不瞬间累计巨大 dt
- 不创建第二个 RAF loop

每个 renderer / scene 最多一个明确拥有者的 animation loop。

---

# 29. WebGL context 管理

监听：

```text
webglcontextlost
webglcontextrestored
```

context lost：

- prevent default where appropriate
- pause renderer
- 显示可理解提示
- 保留数学 scene state

context restored：

- 重建 GPU resources
- 恢复 scene
- 不要求用户刷新整个 Learning OS

如果恢复失败：

```text
WebGPU / WebGL2
    ↓
lower renderer
    ↓
Canvas compatibility
```

---

# 30. GPU 资源释放

所有 renderer/adapters 必须：

```ts
dispose()
```

需要释放：

```text
geometry
buffer
material
texture
render target
event listener
ResizeObserver
RAF
Cindy instance
MathBox instance
Three renderer
```

用户从 Math Lab 切回 Today 后：

- 重型动画停止
- 不继续占用 GPU
- 可以选择保留少量 JS module cache
- GPU context/资源应按实际生命周期释放或休眠

重点测试：

```text
Today → Math Lab → Today → Math Lab
```

反复切换不得持续增长：

```text
RAF count
WebGL context
event listeners
GPU resources
```

---

# 31. Debug panel

开发环境支持一个可折叠 Debug panel：

```text
Renderer
Quality tier
FPS
frame time
DPR
viewport resolution
surface resolution
curve samples
draw calls（能获得时）
triangle count（能获得时）
WebGPU/WebGL backend
```

默认不占据普通用户主要 UI。

生产模式可以隐藏高级指标或只保留 renderer/tier。

---

# 32. MVP 1：Linear Transformation

这是第一优先级。

创建场景：

```text
2×2 matrix
coordinate grid
unit square
basis e1 / e2
arbitrary vector
transformed vector
determinant
eigen-directions
```

矩阵 UI：

```text
[a b]
[c d]
```

动画：

```math
A(t) = (1-t)I + tA
```

每个 grid point：

```math
x(t) = A(t)x
```

显示：

```text
e1 → Ae1
e2 → Ae2
```

单位正方形面积：

```text
1 → |det(A)|
```

如果：

```math
det(A) < 0
```

明确表示 orientation flip。

---

# 33. Eigenvector 可视化

如果存在实特征方向：

显示：

```math
Av = \lambda v
```

用不同视觉编码区分：

```text
普通向量
特征向量
```

动画必须让用户看到：

普通向量通常改变方向。

特征向量：

```text
方向保持在同一直线上
只缩放或反向
```

如果矩阵没有实特征方向：

不要伪造 eigenvector。

明确显示：

```text
No real eigendirections
```

---

# 34. SVD：第二阶段线代功能

接口要提前支持，但 MVP 可在 Linear Transform 完成后实现。

动画：

```math
A = U\Sigma V^T
```

按顺序：

```text
V^T
 ↓
Σ
 ↓
U
```

用户可以：

```text
play all
step Vᵀ
step Σ
step U
```

优先数学正确，不追求花哨 transition。

---

# 35. MVP 2：Complex Mapping

核心布局：

```text
┌──────────────────┐  ┌──────────────────┐
│     z-plane      │  │     w-plane      │
│                  │  │                  │
│ z                │  │      w=f(z)      │
└──────────────────┘  └──────────────────┘
```

使用 CindyJS/CindyGL 的专业能力。

支持：

```text
point
line
circle
grid
simple parametric curve
```

用户拖动左侧对象：

右侧同步映射。

显示当前：

```text
z
f(z)
Re
Im
|z|
arg(z)
|f(z)|
arg(f(z))
```

必须正确处理：

```text
pole
branch issue
NaN
Infinity
overflow
```

---

# 36. Domain Coloring

这是 CindyGL 的重点场景。

High/Balanced：

优先 GPU per-pixel。

Low：

降低 render target resolution。

Compatibility：

CPU sampling + Canvas rasterization 或更低分辨率 fallback。

避免每帧创建新的大 ImageData / texture。

支持：

```text
pan
zoom
function parameters
```

不要因为单个 singularity 把整个 shader 输出污染为 NaN。

---

# 37. MVP 3：Fourier

不要只做一张频谱图。

同时展示：

```text
Time domain
    ↓
Complex wrapping
    ↓
Fourier coefficient
    ↓
Frequency domain
```

核心数学：

```math
f(t)e^{-i\omega t}
```

用户拖动：

```text
ω
```

实时看到：

```text
complex plane winding
centroid / integral
magnitude
phase
frequency response
```

支持预设：

```text
single sine
two-tone signal
square wave
triangle wave
```

离散数据：

```text
FFT
```

教学模式：

```text
numerical Fourier integral
```

普通频谱曲线如果 ECharts 足够，可以复用现有 ECharts。

Complex wrapping 等高交互部分不要强塞给 ECharts。

---

# 38. Fourier Series

在 Fourier MVP 稳定后增加。

支持：

```text
Square
Sawtooth
Triangle
Custom
```

显示：

```text
partial sum
harmonics
phasors
epicycles
spectrum
```

控制：

```text
N = 1 ... n
```

用户改变 N 时，不要重建整个页面。

---

# 39. MVP 4：3D Surface

支持：

```math
z = f(x,y)
```

预设：

```text
sin(x²+y²)
x²-y²
exp(-(x²+y²))
sin(x)cos(y)
```

功能：

```text
orbit
pan
zoom
surface
wireframe
axes
grid
parameter animation
```

Balanced：

可以优先使用 MathBox 适合的数学坐标/曲面场景。

High：

如果现代 Three.js/WebGPU 的吞吐和兼容更好，可走 Three renderer。

Compatibility：

降低为低密度 wireframe；无 WebGL 时允许 Canvas CPU 投影 fallback。

---

# 40. Laplace 模块

在 MVP 四个场景稳定后实现。

核心：

```math
F(s)=\int_0^\infty f(t)e^{-st}\,dt
```

其中：

```math
s=\sigma+i\omega
```

拆开：

```math
e^{-\sigma t}e^{-i\omega t}
```

界面：

```text
             Im(s)=ω
                ↑
                │
────────────────┼────────────→ Re(s)=σ
                │
```

拖动 `s` 点：

同步展示：

```text
original signal
e^{-σt} weighted signal
complex rotation e^{-iωt}
integral / transform value
```

后续预留：

```text
poles
zeros
ROC
```

---

# 41. Primitive API

不要一开始设计超级复杂 DSL。

第一阶段最小 Primitive：

```text
Axis
Grid
Point
Vector
Curve
Surface
VectorField
TextLabel
```

后续：

```text
ComplexPlane
DomainColoring
Signal
Spectrum
Phasor
Region
Pole
Zero
```

示意：

```ts
const scene = new MathScene()

scene.add({
  kind: 'vector',
  from: [0, 0, 0],
  to: [2, 1, 0],
})
```

重点：

- 简洁
- 强类型
- renderer-neutral

---

# 42. TypeScript

保持现有 TypeScript 体系。

要求：

```text
strict-friendly
```

避免无边界 `any`。

如果 CindyJS / MathBox 类型定义不完整：

建立非常窄的：

```text
vendor type declarations
adapter-local interfaces
```

例如：

```ts
declare module 'some-library' {
  // only the API actually used
}
```

不要为了消除 TS 错误：

```ts
const x: any = ...
```

一路传进整个系统。

第三方动态对象可以在 adapter 边界使用：

```text
unknown
type guard
narrow interface
```

---

# 43. Vue 性能规则

禁止每帧：

```ts
someVueRef.value = ...
```

导致大规模 Vue patch。

60/120 FPS 数据：

```text
renderer state
typed arrays
uniforms
buffers
```

Vue 只接收低频摘要：

```text
FPS 每 500ms
current ω
current matrix
current mode
selected function
```

---

# 44. 高频 Geometry 更新

禁止：

```js
requestAnimationFrame(() => {
  disposeOldGeometry()
  createNewGeometry()
})
```

优先：

```text
persistent geometry
buffer update
uniform update
matrix update
instancing
```

大量箭头：

```text
InstancedMesh
```

大量点：

```text
Points / GPU buffer
```

Surface：

优先固定 topology，仅更新 vertex positions 或 shader parameter。

---

# 45. Worker 原则

不要为了架构炫技直接把所有计算扔 Worker。

先 profiling。

适合 Worker 的潜在任务：

```text
large FFT
large surface CPU sampling
expensive numerical integration
large vector field sampling
```

如果主线程已经可以稳定：

```text
60 FPS
```

则保持简单。

需要 Worker 时：

- 使用 transferable buffer
- 不频繁复制大数组
- Worker 与 renderer 生命周期同步
- dispose 时 terminate

---

# 46. Existing API / auth 不得破坏

当前前端 API 使用 same-origin：

```text
credentials: same-origin
CSRF cookie
X-CSRFToken
401/403 redirect login
```

Math Lab 第一阶段不需要 API。

如果确实新增 API：

必须复用：

```text
frontend/src/lib/api.ts
```

不要创建第二套 fetch/auth client。

禁止：

```text
CORS
JWT
local auth token
new login system
```

---

# 47. Docker 兼容

现有 Docker frontend build 使用 Node 18。

新增依赖必须确认：

```text
Node 18 可安装
npm ci 可安装
Vite 5 可构建
```

不要只在本机最新 Node 版本验证。

必须最终验证：

```bash
cd frontend
npm ci
npm run typecheck
npm run build
```

如果环境允许，再验证：

```bash
docker build .
```

不要修改 Docker 架构，除非数学依赖确实要求且有充分理由。

不要加入 CDN runtime dependency 作为核心方案。

生产环境应该由 Vite bundle 正常提供 JS。

---

# 48. Vite 兼容

必须保留：

```ts
base: '/static/app/'
```

不要改成：

```text
/
```

否则会破坏 Django 静态资源部署。

数学模块必须正常被 Vite code splitting。

如果需要 `manualChunks`：

只在 bundle 分析证明有意义时加入。

例如可能：

```text
math-cindy
math-mathbox
math-three
math-core
```

不要过度拆 chunk 导致几十个碎片请求。

---

# 49. Existing ECharts

项目已经存在 ECharts。

对于：

```text
frequency spectrum
simple sampled signal
non-realtime trend
```

如果 ECharts 足够：

优先复用。

不要再安装：

```text
Plotly
Chart.js
D3 entire stack
```

除非有明确无法替代的需求。

---

# 50. Existing KaTeX

公式显示继续复用项目现有 KaTeX。

Math Lab UI 需要显示：

```math
A(t)=(1-t)I+tA
```

```math
Av=\lambda v
```

```math
F(\omega)=\int f(t)e^{-i\omega t}dt
```

等公式。

建立一个轻量：

```text
MathFormula.vue
```

或复用当前已有 Markdown/KaTeX rendering helper。

不要重复引入 MathJax。

---

# 51. CSS 与 canvas

Canvas/WebGL viewport：

- 必须有稳定 aspect ratio
- 容器 resize 后正确更新 backing store
- DPR 与 CSS pixels 分离
- 不产生横向页面溢出
- iPad split view 下正常 resize
- 手机旋转正常

使用：

```text
ResizeObserver
```

避免：

```text
canvas.width = window.innerWidth
```

这种全局假设。

---

# 52. Touch interaction

Math Lab 必须考虑 iPad/手机。

需要：

```text
single finger drag
two finger pinch
wheel zoom desktop
pointer events
```

优先：

```text
Pointer Events
```

不要同时维护三套：

```text
mousedown
touchstart
pointerdown
```

造成重复触发。

对 viewport：

```css
touch-action
```

按实际交互精确设置，不要导致整个页面无法滚动。

---

# 53. 数学正确性优先于视觉

必须实现可验证测试。

Linear Algebra：

```text
det(I)=1
A*e1 与矩阵第一列一致
A*e2 与矩阵第二列一致
```

Eigen：

```text
Av ≈ λv
```

Complex：

```text
f(z)=z²
f(1+i)=2i
```

Fourier：

对单一正弦：

```text
频谱主峰出现在正确频率
```

Laplace：

```text
L{1}=1/s
L{e^{at}}=1/(s-a)
```

3D：

采样点必须满足：

```text
z = f(x,y)
```

允许数值误差，但必须设置合理 tolerance。

---

# 54. 测试工具

先检查项目是否已经有前端测试框架。

如果没有：

可以考虑加入轻量：

```text
Vitest
```

仅用于：

```text
MathEngine
quality selection
matrix transform
complex arithmetic
FFT helper
expression validator
```

不要第一阶段为了 Math Lab 引入大型 E2E 栈。

如果加入 Vitest：

同步更新：

```text
package.json
package-lock.json
```

并确保：

```bash
npm run typecheck
npm run build
npm test
```

可执行。

---

# 55. Baseline before modification

修改之前先运行现有检查。

至少：

```bash
python manage.py check
python manage.py test

cd frontend
npm ci
npm run typecheck
npm run build
```

如果 baseline 已有失败：

记录失败。

不要把原有失败误认为本次引入。

修改完成后运行同一组。

---

# 56. Bundle 检查

完成后查看 Vite build 输出。

重点：

```text
initial app chunk
MathLab chunk
Cindy chunk
MathBox chunk
Three chunk
```

目标：

> 用户日常打开 Today 页面时，不应该为一个未打开的 Math Lab 支付全部 GPU/数学库下载和解析成本。

如果 Math Lab bundle 很大是可以接受的，但必须 lazy load。

---

# 57. Error isolation

Math Lab 是附加功能。

如果：

```text
Cindy initialization fails
MathBox initialization fails
WebGPU fails
shader compile fails
```

不能让：

```text
Today
Sessions
Settings
Active Session
```

一起崩溃。

MathLabView 内部建立 error boundary 等价机制：

- 捕获 renderer init error
- 展示错误
- 自动 fallback
- 提供 Retry
- 提供切换 Compatibility Mode

Vue 顶层 App 不应因此白屏。

---

# 58. Renderer fallback

目标链：

```text
WebGPU
 ↓
WebGL2
 ↓
WebGL1 / compatible MathBox/Cindy path
 ↓
Canvas2D
```

但不是所有场景必须完全使用同一个 renderer。

允许：

```text
Complex Analysis → CindyGL
3D Heavy Surface → Three WebGPU
Math coordinate scene → MathBox
Compatibility → Canvas
```

系统的统一性来自：

```text
Math Scene + adapter
```

而不是所有东西硬塞进一个引擎。

---

# 59. 场景能力匹配

创建类似：

```ts
function selectRenderer(
  scene: SceneDescriptor,
  profile: QualityProfile,
  capabilities: RuntimeCapabilities,
): RendererChoice
```

例如：

```text
complex-domain-coloring
→ CindyGL preferred

mathbox-coordinate-scene
→ MathBox preferred

high-density-3d
→ Three WebGPU preferred

compatibility-linear-transform
→ Canvas preferred
```

不要机械规定：

```text
High = WebGPU everything
Low = Canvas everything
```

应该由：

```text
scene requirements
+
device capability
+
quality tier
```

共同决定。

---

# 60. 模式切换

用户运行中：

```text
Balanced → Compatibility
```

必须：

- 保存当前数学 scene state
- dispose 原 renderer
- 初始化 fallback renderer
- 恢复 scene
- 不重置所有参数

这要求 Scene state 与 Renderer state 解耦。

---

# 61. Math Lab 首页

进入 Math Lab 后，不要马上启动所有重型 renderer。

首先显示模块选择：

```text
Linear Transform
Complex Mapping
Fourier
3D Surface
Laplace
```

默认可以打开：

```text
Linear Transform
```

只初始化当前场景所需引擎。

切换到 Complex 后才 lazy-load Cindy。

切换到 3D 后才 lazy-load MathBox/Three。

---

# 62. 推荐的第一版界面控制

## Linear

```text
a b c d
Play
Reset
Show grid
Show unit square
Show eigenvectors
Mode
```

## Complex

```text
f(z)
Preset
Show grid
Show domain coloring
Reset view
Mode
```

## Fourier

```text
Signal preset
Frequency ω
Play
Show wrapping
Show spectrum
Mode
```

## Surface

```text
f(x,y)
Preset
Surface / Wireframe
Resolution
Auto rotate OFF by default
Mode
```

不要一次做几十个控制项。

---

# 63. 3D camera

默认：

```text
OrbitControls-like interaction
```

但确认 Three.js addon 与当前版本打包方式兼容。

不得从未固定版本 CDN import。

所有 production dependency 从 npm bundle。

camera state：

```text
position
target
zoom
```

应该在 renderer recreate 后尽量恢复。

---

# 64. 复数 branch 与 singularity

对于：

```text
log(z)
sqrt(z)
1/z
```

必须考虑：

```text
branch cut
pole
undefined point
```

第一阶段不需要实现整套 Riemann surface。

但必须：

- 不画错误值
- 不让 shader 出现全屏 NaN
- UI 可以提示 principal branch
- singularity 附近 clamp / discard 时明确是渲染策略

---

# 65. Performance defaults 不是数学精度

区分：

```text
display sampling precision
```

与：

```text
math engine result correctness
```

例如：

Low 模式可以只画：

```text
48×48 surface
```

但：

```text
det(A)
eigenvalue
selected point f(z)
```

仍应按照正常数值精度计算。

不要因为 Low 模式把所有数学运算都改为粗糙近似。

---

# 66. 文档

新增：

```text
docs/math-lab.md
docs/math-renderer-compatibility.md
```

`docs/math-lab.md` 包括：

```text
architecture
modules
quality modes
renderer fallback
how to add a new scene
how to add a new primitive
performance rules
debugging
```

`docs/math-renderer-compatibility.md` 包括：

```text
actual installed versions
tested browsers
renderer paths
MathBox/Three compatibility decision
Cindy integration
known issues
licenses
```

README 只增加简短 Math Lab 能力说明和文档链接。

不要让 README 变成巨大实现文档。

---

# 67. Browser 测试矩阵

至少逻辑上覆盖：

```text
Chrome / Chromium modern
Safari modern
Firefox modern
iPad Safari
mobile Safari / Chromium
```

重点不是追求完全一致，而是：

```text
functional fallback
```

Firefox/Safari 无 WebGPU 或 WebGPU 能力不同：

必须回退。

不要显示 blank canvas。

---

# 68. WebGPU 规则

WebGPU 是优化路径，不是最低依赖。

禁止让整个 Math Lab：

```text
requires WebGPU
```

使用前：

```text
feature detection
adapter request
device request
error handling
```

初始化失败立即 fallback。

不要依赖浏览器实验 flag。

---

# 69. 代码风格

跟随仓库现有风格。

如果现有 Vue 文件：

```text
<script setup lang="ts">
```

继续使用。

不要突然引入：

```text
class-based Vue
Options API 大规模重写
```

核心数学/renderer TypeScript 可以使用 class，但不要滥用继承。

优先：

```text
composition
small interfaces
plain data
```

---

# 70. 禁止 God Component

`MathLabView.vue` 负责：

```text
layout
selected module
quality mode
high-level lifecycle
```

不要让它包含：

```text
matrix algorithms
FFT
WebGL shader source
Cindy setup
MathBox setup
Three scene construction
all controls
all rendering
```

每个子模块独立。

---

# 71. 不要过度抽象

同时避免另一个极端。

不要在 MVP 前先写：

```text
4000 行抽象层
50 个 interface
plugin marketplace
distributed event bus
```

抽象必须由当前 4 个 MVP 场景验证。

原则：

> 至少有两个使用者时再抽象通用层，renderer boundary 除外。

---

# 72. 开发顺序

严格按以下顺序推进。

## Phase 0 — Baseline

```text
inspect repo
run tests/build
record current state
```

## Phase 1 — Compatibility investigation

检查：

```text
CindyJS
CindyGL
MathBox
Three.js
math.js
FFT library
Node 18
Vite 5
licenses
```

生成：

```text
docs/math-renderer-compatibility.md
```

## Phase 2 — Shell integration

完成：

```text
Math Lab sidebar entry
MathLabView async loading
responsive shell
quality selector
```

确认所有旧页面仍正常。

## Phase 3 — Core

实现：

```text
CapabilityDetector
PerformanceManager
Timeline
MathScene
MathRenderer
renderer factory
MathEngine
```

## Phase 4 — Linear Transform MVP

先做最简单 renderer，可用 Canvas2D。

验证 Scene/Renderer abstraction。

再增加 MathBox/Three 路径。

## Phase 5 — Complex MVP

集成 CindyJS/CindyGL。

验证 adapter 隔离。

## Phase 6 — Fourier MVP

实现：

```text
signal
complex wrapping
spectrum
```

## Phase 7 — 3D Surface MVP

实现 MathBox/Three 场景和 fallback。

## Phase 8 — Adaptive quality

实际 profiling 后完善 Auto。

## Phase 9 — Tests/docs/build

完成全部验证。

不要在 Phase 1 写完架构文档后停止。

继续实际实现。

---

# 73. 完成标准

任务只有满足以下标准才算完成：

### Existing project

- [ ] Today 页面工作
- [ ] Active Session 工作
- [ ] Trends 工作
- [ ] Sessions 工作
- [ ] Issues 工作
- [ ] Settings 工作
- [ ] 登录/登出逻辑未破坏
- [ ] Vite base 仍为 `/static/app/`
- [ ] Docker 构建路径未破坏

### Math Lab

- [ ] Sidebar / mobile menu 可以进入 Math Lab
- [ ] MathLabView 是 async loaded
- [ ] Auto 模式存在
- [ ] Compatibility 模式存在
- [ ] Low 模式存在
- [ ] Balanced 模式存在
- [ ] High 模式存在
- [ ] Linear Transformation 可用
- [ ] Complex Mapping 可用
- [ ] Fourier MVP 可用
- [ ] 3D Surface MVP 可用
- [ ] renderer failure 有 fallback
- [ ] Math Lab 离开后 animation 停止

### Engineering

- [ ] TypeScript typecheck 通过
- [ ] Vite build 通过
- [ ] Backend check 通过
- [ ] Existing backend tests 不因本次改动新增失败
- [ ] package-lock 正确更新
- [ ] 没有使用 `eval` / `new Function`
- [ ] 没有新增 React
- [ ] 没有新增 Vue Router
- [ ] 没有破坏 same-origin architecture
- [ ] 没有把全部数学库塞进 initial bundle
- [ ] 没有为了 MathBox 降级整个项目技术栈
- [ ] 没有明显 GPU/context/event listener 泄漏

---

# 74. 最终验证命令

至少执行：

```bash
python manage.py check
python manage.py test
```

然后：

```bash
cd frontend
npm ci
npm run typecheck
npm run build
```

如果加入前端测试：

```bash
npm test
```

如果当前环境支持：

```bash
cd ..
docker build .
```

不要声称“完成”但没有实际运行 build/typecheck。

---

# 75. 最终向我汇报的格式

完成后不要只说“实现好了”。

给我：

## 1. Architecture

说明：

```text
CindyJS 用在哪里
MathBox 用在哪里
Three.js 用在哪里
Canvas fallback 用在哪里
```

## 2. Compatibility Decision

明确说明：

```text
MathBox 与 Three 的实际版本关系
是否存在双 Three 实例
如何隔离
WebGPU fallback
CindyGL fallback
```

## 3. Files Changed

逐个列出关键文件和用途。

## 4. Performance Modes

说明：

```text
Auto
Compatibility
Low
Balanced
High
```

实际参数和 renderer 选择。

## 5. Bundle

给出 build 后主要 chunk 大小。

重点说明：

```text
原 Today 首屏是否被显著增重
```

## 6. Verification

贴出：

```text
typecheck
build
tests
Django check
```

最终结果。

## 7. Known Limitations

不要隐藏：

```text
browser incompatibility
MathBox limitation
WebGPU limitation
Cindy limitation
mobile limitation
```

---

# 76. 最核心的设计原则

这个功能不是“在学习记录网站里塞几个函数图”。

目标是逐渐形成：

```text
Interactive Mathematical Visualization Engine
```

但它必须作为：

```text
Personal Learning OS
```

的一个模块存在。

必须满足：

```text
Existing Learning OS
      │
      ├── stable
      ├── lightweight
      ├── same-origin
      └── backward compatible

Math Lab
      │
      ├── lazy loaded
      ├── renderer isolated
      ├── adaptive performance
      ├── mathematically correct
      └── independently extensible
```

数学动画的本质必须是：

```text
Mathematical State
        ↓
Scene Description
        ↓
Sampling / Geometry / Shader
        ↓
Renderer
        ↓
Frame
```

而不是：

```text
pre-rendered animation
fake morph
visual effect
```

例如线性变换必须来自：

```math
x(t)=A(t)x
```

复变映射必须来自：

```math
w=f(z)
```

Fourier 必须来自：

```math
f(t)e^{-i\omega t}
```

Laplace 必须来自：

```math
f(t)e^{-\sigma t}e^{-i\omega t}
```

---

# 77. 现在直接开始执行

现在开始处理当前仓库，不要再向我重复需求。

执行：

1. 检查 git 工作树。
2. 阅读现有架构和前端入口。
3. 运行 baseline check/build/test。
4. 调研并验证 CindyJS / CindyGL / MathBox / Three.js / math.js / FFT 的当前可安装版本和许可。
5. 生成兼容性文档。
6. 用现有 Vue 3 + TypeScript + Vite 架构新增懒加载 Math Lab。
7. 实现 renderer abstraction 和五档性能策略。
8. 先完成 Linear Transformation。
9. 再完成 CindyJS/CindyGL Complex Mapping。
10. 再完成 Fourier。
11. 再完成 MathBox/Three 3D Surface。
12. 加入 fallback、dispose、resize、visibility pause。
13. 完成测试和文档。
14. 实际运行 typecheck/build/tests。
15. 修复本次引入的所有阻塞性问题。
16. 最后按照“最终向我汇报的格式”汇报。

不要停留在方案讨论。

直接修改现有 `zsyeh/time-tracker` 项目，完成一个实际可运行、与现有 Learning OS 兼容的 Math Lab MVP。
