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

export interface FormulaParameterDefinition {
  symbol: string
  value: number
  min: number
  max: number
  step: number
}

export interface PreparedSurfaceFormula {
  expression: string
  parameters: FormulaParameterDefinition[]
  unsupportedCommands: string[]
}

function compact(source: string) {
  return source.normalize('NFKC').toLowerCase().replace(/\\+/g, '\\').replace(/\s+/g, '')
}

const scalarFunctions = new Set([
  'abs', 'acos', 'asin', 'atan', 'ceil', 'cos', 'cosh', 'cot', 'csc', 'exp', 'floor',
  'log', 'max', 'min', 'sec', 'sign', 'sin', 'sinh', 'sqrt', 'tan', 'tanh',
])
const greekSymbols = [
  'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'varepsilon', 'zeta', 'eta', 'theta',
  'vartheta', 'iota', 'kappa', 'lambda', 'mu', 'nu', 'xi', 'rho', 'sigma', 'tau',
  'upsilon', 'phi', 'varphi', 'chi', 'psi', 'omega',
]

function replaceNestedTex(source: string): string {
  let value = source
  for (let pass = 0; pass < 16; pass += 1) {
    const next = value
      .replace(/\\+(?:d|t)?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, '(($1)/($2))')
      .replace(/\\+sqrt\s*\{([^{}]*)\}/g, 'sqrt($1)')
      .replace(/\^\s*\{([^{}]*)\}/g, '^($1)')
      .replace(/_\s*\{([^{}]*)\}/g, '_$1')
    if (next === value) break
    value = next
  }
  return value
}

export function normalizeFormulaExpression(source: string): string {
  let value = replaceNestedTex(source.trim())
    .replace(/^\$+|\$+$/g, '')
    .replace(/\\+(?:left|right)/g, '')
    .replace(/\\+(?:lvert|rvert|vert|lVert|rVert|Vert)/g, '|')
    .replace(/\\+(?:,|;|!|quad|qquad)/g, ' ')
    .replace(/\\+(?:operatorname|mathrm|text)\{([^{}]*)\}/g, '$1')
    .replace(/\\+ln\b/g, ' log')
    .replace(/\\+(sin|cos|tan|sec|csc|cot|asin|acos|atan|sinh|cosh|tanh|exp|log|sqrt)\s+([A-Za-z0-9_.]+)/g, ' $1($2)')
    .replace(/\\+(sin|cos|tan|sec|csc|cot|asin|acos|atan|sinh|cosh|tanh|exp|log|sqrt|min|max|floor|ceil|abs|sign)\b/g, ' $1')
    .replace(/\\+pi\b/g, ' pi')
    .replace(/\\+(?:cdot|times)/g, '*')
    .replace(/\\+pm/g, '+')
    .replace(/[−–]/g, '-')

  value = value.replace(/\\+([A-Za-z]+)\b/g, (command, symbol: string) => {
    const matched = greekSymbols.find((candidate) => candidate.toLowerCase() === symbol.toLowerCase())
    return matched ? ` ${matched.replace(/^var/, '')}` : command
  })
  value = replaceNestedTex(value)
    .replace(/\|([^|]+)\|/g, 'abs($1)')

  const equation = value.split('=')
  if (equation.length > 1 && /^(?:y|z|[A-Za-z_][A-Za-z0-9_]*\s*\(\s*x\s*(?:,\s*y\s*)?\))$/i.test(equation[0].trim())) value = equation.slice(1).join('=')
  return value.replace(/[{}]/g, (token) => token === '{' ? '(' : ')').replace(/\s+/g, ' ').trim()
}

function parameterDefaults(symbol: string): Omit<FormulaParameterDefinition, 'symbol'> {
  if (/^(?:phi|theta|phase)$/i.test(symbol)) return { value: 0, min: -3.15, max: 3.15, step: .05 }
  if (/^(?:k|m|n|omega|sigma|tau|frequency)$/i.test(symbol)) return { value: 1, min: .1, max: 8, step: .1 }
  return { value: 1, min: -5, max: 5, step: .1 }
}

export function prepareSurfaceFormula(source: string): PreparedSurfaceFormula {
  let expression = normalizeFormulaExpression(source)
    .replace(/\b([A-Za-z])([xy])\b/g, '$1 $2')
    .replace(/(\d)(xy)\b/g, '$1 x y')
  const unsupportedCommands = [...new Set([...expression.matchAll(/\\+([A-Za-z]+)/g)].map((match) => match[1]))]
  const reserved = new Set(['x', 'y', 'pi', 'e', 'infinity', ...scalarFunctions])
  const symbols = [...new Set(expression.match(/[A-Za-z_][A-Za-z0-9_]*/g) || [])]
    .filter((symbol) => !reserved.has(symbol.toLowerCase()))
    .filter((symbol) => !unsupportedCommands.includes(symbol))
    .slice(0, 10)
  const parameters = symbols.map((symbol) => ({ symbol, ...parameterDefaults(symbol) }))

  for (const parameter of parameters) {
    const escaped = parameter.symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    expression = expression.replace(new RegExp(`\\b${escaped}\\s*\\(`, 'g'), `${parameter.symbol} * (`)
  }
  expression = expression.replace(/\)\s*\(/g, ') * (')
  return { expression, parameters, unsupportedCommands }
}

export function routeFormula(source: string): FormulaRoute {
  const value = compact(source)
  const normalized = normalizeFormulaExpression(source)
  const surface = ((/f\(?x,y\)?|z=/.test(value) && value.includes('x') && value.includes('y')) || /\\partial.*x.*y|x\^?2[+\-]y\^?2/.test(value))
  if (surface) return { module: 'surface', confidence: 'high', normalized }
  if (/fourier|\\mathcal\{f\}|\\hat\{f\}|e\^?\{?-i.*(?:omega|\\omega)|(?:omega|\\omega).*f\(/.test(value)) return { module: 'fourier', confidence: 'high', normalized }
  if (/laplace|\\mathcal\{l\}|e\^?\{?-s?t|\\int_?0\^?\{?(?:\\infty|∞)/.test(value)) return { module: 'laplace', confidence: 'high', normalized }
  if (/\\begin\{[pbv]?matrix\}|\\det|det\(|eigen|\\lambda|\\vec|\\mathbf|a\(?t\)?x|av=/.test(value)) return { module: 'linear', confidence: 'high', normalized }
  if (/\\mathbb\{c\}|complex|arg\(?|\\operatorname\{(?:re|im)\}|(?:^|[^a-z])z(?:[^a-z]|$)|f\(z\)/.test(value)) return { module: 'complex', confidence: 'high', normalized }
  if (/\\int|∫/.test(value)) return { module: 'laplace', confidence: 'medium', normalized }
  if (value.includes('x') && value.includes('y')) return { module: 'surface', confidence: 'medium', normalized }
  if (/^(?:y|z|[a-z_][a-z0-9_]*\(x\))=/.test(value) || (value.includes('x') && /sin|cos|tan|sqrt|exp|log|\^/.test(value))) return { module: 'surface', confidence: 'medium', normalized }
  return { module: 'linear', confidence: 'low', normalized }
}

export function matrixFromFormula(source: string): readonly [number, number, number, number] | null {
  const body = source.match(/\\+begin\{[pbv]?matrix\}([\s\S]*?)\\+end\{[pbv]?matrix\}/i)?.[1]
  if (!body) return null
  const values = body.match(/[-+]?(?:\d+\.?\d*|\.\d+)/g)?.slice(0, 4).map(Number)
  return values?.length === 4 && values.every(Number.isFinite) ? values as [number, number, number, number] : null
}
