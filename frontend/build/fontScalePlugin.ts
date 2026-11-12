import type { Plugin } from 'postcss'
// Apply the shared font token to legacy pixel typography at build time. Geometry,
// hit targets, image/canvas dimensions and em-based formula internals are unchanged.
export function fontScalePlugin(): Plugin {
  return {
    postcssPlugin: 'learning-ui-font-scale',
    Declaration(decl) {
      if (decl.value.includes('--ui-font-scale')) return
      if (decl.prop === 'font-size' || decl.prop.startsWith('--font-size-') || /^--el-font-size/.test(decl.prop)) {
        decl.value = decl.value.replace(/(?<![\w.-])(\d+(?:\.\d+)?)px\b/g, (_, n) => Number(n) === 0 ? '0px' : `calc(${n}px * var(--ui-font-scale, 1))`)
      } else if (decl.prop === 'font') {
        // The first px value in a shorthand is the size; subsequent line-height
        // and spacing values stay fixed, preserving the existing row geometry.
        decl.value = decl.value.replace(/\b(\d+(?:\.\d+)?)px\b/, (_, n) => `calc(${n}px * var(--ui-font-scale, 1))`)
      }
    },
  }
}
