# Math renderer compatibility

## Locked versions

验证环境：Node.js 18.20.4、npm 9.2.0、TypeScript 5.7、Vue 3.5、Vite 5.4.21。

| Component | Installed version | License | Integration |
| --- | --- | --- | --- |
| CindyJS + CindyGL | 0.0.5 npm package; bundled CindyGL | Apache-2.0 core, bundled subprojects noted upstream | self-hosted browser assets, loaded only for complex GPU mode |
| MathBox | 2.3.2-rc1 | MIT | isolated same-origin iframe |
| Three for MathBox | 0.139.2 | MIT | exists only inside the MathBox iframe |
| Modern Three | 0.185.1 (`three-modern` npm alias) | MIT | async `ThreeRenderer` chunk |
| math.js | 15.2.0 | Apache-2.0 | versioned self-hosted browser build, loaded only when applying a custom expression |
| fft.js | 4.0.4 | MIT | Fourier module chunk |
| Vitest | 3.2.6 | MIT | development/test only; supports Node 18 |

生产依赖执行 `npm audit --omit=dev` 的结果为 0 个已知漏洞。许可证文本随隔离 vendor 文件保存在 `frontend/public/vendor/math-lab/`；项目自身继续使用 GPL-3.0-or-later。

## MathBox / Three decision

MathBox 2.3.2-rc1 声明 `three >=0.118.0`，其开发/测试依赖落在 0.139 系列。项目因此保留精确的 Three 0.139.2 兼容运行时，同时用 npm alias 安装现代 Three 0.185.1。两套运行时不交换 `Vector3`、Mesh、Material 或 context。

为避免主应用出现全局 `window.THREE`，兼容 Three、OrbitControls 和 MathBox 的预构建浏览器文件只在 `mathbox-frame.html` 内加载。父窗口的 `MathBoxAdapter` 通过同源 `postMessage` 发送可结构化克隆的 SurfaceScene。关闭模块会删除 iframe，因此不会把旧版 Three singleton 留在 Learning OS 主窗口。

CindyJS/CindyGL 与 math.js 同样以版本化静态文件自托管，避免在 2 GB 构建环境中把大型预构建 runtime 的上千个内部模块重新拉进 Rollup graph。它们仍由各自异步控制器按需请求：Cindy 只用于 Complex Mapping 的 Balanced/High domain-coloring，math.js 只用于用户明确应用自定义曲面；加载或初始化失败会回退或保留上一帧有效场景。

## Renderer paths

| Scene / capability | High | Balanced | Low | Compatibility / no WebGL |
| --- | --- | --- | --- | --- |
| Linear | Canvas | Canvas | Canvas | Canvas |
| Complex domain coloring | CindyGL | CindyGL | cached Canvas CPU | cached Canvas CPU |
| Fourier / Laplace | Canvas + FFT/numerics | Canvas + FFT/numerics | Canvas | Canvas |
| 3D Surface | modern Three on WebGL2 | isolated MathBox on WebGL1+ | Canvas projection | Canvas projection |

WebGPU 只做 feature detection，为后续 renderer 保留能力位；当前 MVP 不要求 WebGPU，也不会提示用户打开实验 flag。WebGL context 丢失时 Three renderer 暂停并报告错误；adapter 初始化异常由 `VisualizationViewport` 捕获，然后创建 Canvas renderer。

## Browser coverage

能力/回退逻辑覆盖下列组合：

- Modern Chromium：WebGL2，通常 Auto → Balanced；可手动 High 使用现代 Three。
- Modern Firefox：WebGL2 可用时与 Chromium 同路径；WebGPU 缺失不影响功能。
- Modern Safari / iPadOS Safari：使用 WebGL capability detection；原生 dialog 顶层阅读器支持触摸滚动，Math Lab 可在全屏阅读状态进入。
- Mobile Safari / Chromium：响应式单列控制器、低 DPR 档位和 Canvas fallback。
- 禁用 WebGL、软件渲染被标为 major performance caveat，或 adapter 初始化失败：Compatibility Canvas。

当前执行环境没有可用的 Chromium/Firefox/Safari 二进制，因此本次自动验证覆盖 TypeScript、生产构建、Django 测试和数值单元测试，浏览器矩阵属于 capability/fallback 代码路径验证；发布后仍应在真实 iPhone/iPad 上做一次触摸回归。

## Known limitations

- 当前没有 WebGPU renderer；WebGPU 是未来优化路径。
- Canvas 3D 是精细线框投影，不提供完整的 GPU pan；GPU 路径提供 orbit/zoom。
- CindyGL、MathBox 和兼容 Three 是约 1.9 MB 的未压缩自托管文件，但默认完全不请求，并可由 Web 服务器长期缓存与压缩。
- math.js 首次冷加载明显大于普通控制器 chunk，因此只有明确点击 `APPLY EXPRESSION` 才请求；预设曲面不加载它。
- Vite 5 的开发服务器依赖链仍有 npm audit 的开发态 advisory；生产依赖审计为 0，且生产部署不暴露 Vite dev server。升级到下一代 Vite 需要单独验证 Node 与现有构建链，不在本次变更中强制升级。
