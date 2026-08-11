declare module 'cindyjs' {
  const CindyJS: unknown
  export default CindyJS
}

declare module 'cindyjs/build/js/CindyGL.js' {
  const plugin: unknown
  export default plugin
}

declare module 'fft.js' {
  export default class FFT {
    constructor(size: number)
    createComplexArray(): number[]
    realTransform(output: number[], input: number[]): void
    completeSpectrum(output: number[]): void
  }
}

// `three-modern` is an npm alias for the current Three.js package. Keep its
// type surface explicitly mapped while MathBox remains isolated on legacy
// `three` at runtime.
declare module 'three-modern' {
  export * from 'three'
}

declare module 'three-modern/addons/controls/OrbitControls.js' {
  export { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
}
