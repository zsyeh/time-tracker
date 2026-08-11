import type { MathModuleId } from '../types'

export interface FormulaRoute {
  module: MathModuleId
  confidence: 'high' | 'medium' | 'low'
  normalized: string
}

export interface FormulaLaunchRequest extends FormulaRoute {
  expression: string
  id: number
  automatic: boolean
}

export const formulaModuleOptions: Array<{ id: MathModuleId; label: string }> = [
  { id: 'linear', label: 'Linear transformation' },
  { id: 'complex', label: 'Complex mapping' },
  { id: 'fourier', label: 'Fourier / frequency' },
  { id: 'laplace', label: 'Laplace / integral' },
  { id: 'surface', label: '3D surface' },
]

function compact(source: string) {
  return source.normalize('NFKC').toLowerCase().replace(/\s+/g, '')
}

export function normalizeFormulaExpression(source: string): string {
  let value = source.trim()
    .replace(/^\$+|\$+$/g, '')
    .replace(/\\left|\\right/g, '')
    .replace(/\\(?:,|;|!|quad|qquad)/g, ' ')
    .replace(/\\(?:operatorname|mathrm|text)\{([^{}]*)\}/g, '$1')
    .replace(/\\(sin|cos|tan|exp|log|sqrt)\b/g, '$1')
    .replace(/\\pi\b/g, 'pi')
    .replace(/\\cdot|\\times/g, '*')
    .replace(/−/g, '-')

  for (let pass = 0; pass < 4; pass += 1) {
    const next = value
      .replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, '(($1)/($2))')
      .replace(/\\sqrt\{([^{}]*)\}/g, 'sqrt($1)')
      .replace(/\^\{([^{}]*)\}/g, '^($1)')
    if (next === value) break
    value = next
  }

  const equation = value.split('=')
  if (equation.length > 1 && /(?:^|\\)(?:z|f\s*\(\s*x\s*,\s*y\s*\))/.test(equation[0].trim())) value = equation.slice(1).join('=')
  return value.replace(/[{}]/g, (token) => token === '{' ? '(' : ')').replace(/\s+/g, ' ').trim()
}

export function routeFormula(source: string): FormulaRoute {
  const value = compact(source)
  const normalized = normalizeFormulaExpression(source)
  const surface = (/f\(?x,y\)?|z=/.test(value) && value.includes('x') && value.includes('y')) || /\\partial.*x.*y|x\^?2[+\-]y\^?2/.test(value)
  if (surface) return { module: 'surface', confidence: 'high', normalized }
  if (/fourier|\\mathcal\{f\}|\\hat\{f\}|e\^?\{?-i.*(?:omega|\\omega)|(?:omega|\\omega).*f\(/.test(value)) return { module: 'fourier', confidence: 'high', normalized }
  if (/laplace|\\mathcal\{l\}|e\^?\{?-s?t|\\int_?0\^?\{?(?:\\infty|∞)/.test(value)) return { module: 'laplace', confidence: 'high', normalized }
  if (/\\begin\{[pbv]?matrix\}|\\det|det\(|eigen|\\lambda|\\vec|\\mathbf|a\(?t\)?x|av=/.test(value)) return { module: 'linear', confidence: 'high', normalized }
  if (/\\mathbb\{c\}|complex|arg\(?|\\operatorname\{(?:re|im)\}|(?:^|[^a-z])z(?:[^a-z]|$)|f\(z\)/.test(value)) return { module: 'complex', confidence: 'high', normalized }
  if (/\\int|∫/.test(value)) return { module: 'laplace', confidence: 'medium', normalized }
  if (value.includes('x') && value.includes('y')) return { module: 'surface', confidence: 'medium', normalized }
  return { module: 'linear', confidence: 'low', normalized }
}

export function matrixFromFormula(source: string): readonly [number, number, number, number] | null {
  const body = source.match(/\\begin\{[pbv]?matrix\}([\s\S]*?)\\end\{[pbv]?matrix\}/i)?.[1]
  if (!body) return null
  const values = body.match(/[-+]?(?:\d+\.?\d*|\.\d+)/g)?.slice(0, 4).map(Number)
  return values?.length === 4 && values.every(Number.isFinite) ? values as [number, number, number, number] : null
}
