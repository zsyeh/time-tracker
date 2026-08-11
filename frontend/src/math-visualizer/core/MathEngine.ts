import type { MathNode } from 'mathjs'
import type { ComplexValue } from './numerics'
import { loadVendorScript } from './vendorAssets'

const allowedNodeTypes = new Set(['ConstantNode', 'SymbolNode', 'OperatorNode', 'ParenthesisNode', 'FunctionNode'])
const allowedFunctions = new Set(['sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'sinh', 'cosh', 'tanh', 'exp', 'log', 'sqrt', 'abs', 'arg', 're', 'im', 'conj'])
const allowedSymbols = new Set(['x', 'y', 'z', 't', 's', 'pi', 'e', 'i', ...allowedFunctions])
const allowedOperators = new Set(['add', 'subtract', 'multiply', 'divide', 'pow', 'unaryMinus', 'unaryPlus'])

export interface CompiledExpression {
  evaluate(scope: Record<string, unknown>): unknown
}

export interface SampledSurface {
  resolution: number
  range: number
  values: number[]
}

export class MathEngine {
  private math: typeof import('mathjs') | null = null

  constructor(runtime?: typeof import('mathjs')) {
    this.math = runtime || null
  }

  async load() {
    if (!this.math) {
      await loadVendorScript('mathjs-15.2.0.min.js')
      const runtime = (window as Window & { math?: typeof import('mathjs') }).math
      if (!runtime) throw new Error('math.js did not expose its browser runtime.')
      this.math = runtime
    }
    return this.math
  }

  async compile(source: string, extraSymbols: string[] = []): Promise<CompiledExpression> {
    if (!source.trim() || source.length > 180) throw new Error('Expression must contain 1–180 characters.')
    const math = await this.load()
    const node = math.parse(source)
    this.validateNode(node, new Set([...allowedSymbols, ...extraSymbols]))
    return node.compile()
  }

  async evaluateComplex(source: string, z: ComplexValue): Promise<ComplexValue> {
    const math = await this.load()
    const compiled = await this.compile(source, ['z'])
    const value = compiled.evaluate({ z: math.complex(z.re, z.im) })
    if (typeof value === 'number') return { re: value, im: 0 }
    if (math.isComplex(value)) return { re: value.re, im: value.im }
    throw new Error('Expression did not return a scalar complex value.')
  }

  async sampleSurface(source: string, resolution = 65, range = 5): Promise<SampledSurface> {
    const compiled = await this.compile(source, ['x', 'y'])
    const values: number[] = []
    for (let row = 0; row < resolution; row += 1) {
      const y = -range + row / (resolution - 1) * range * 2
      for (let column = 0; column < resolution; column += 1) {
        const x = -range + column / (resolution - 1) * range * 2
        const result = compiled.evaluate({ x, y })
        if (typeof result !== 'number' || !Number.isFinite(result)) throw new Error('Expression must remain finite and real across the visible domain.')
        values.push(Math.max(-100, Math.min(100, result)))
      }
    }
    return { resolution, range, values }
  }

  private validateNode(node: MathNode, symbols: Set<string>) {
    node.traverse((child) => {
      if (!allowedNodeTypes.has(child.type)) throw new Error(`${child.type} is not allowed.`)
      if (child.type === 'SymbolNode') {
        const symbol = child as MathNode & { name: string }
        if (!symbols.has(symbol.name)) throw new Error(`Symbol “${symbol.name}” is not allowed.`)
      }
      if (child.type === 'OperatorNode') {
        const operator = child as MathNode & { fn: string }
        if (!allowedOperators.has(operator.fn)) throw new Error(`Operator “${operator.fn}” is not allowed.`)
      }
      if (child.type === 'FunctionNode') {
        const fn = child as MathNode & { fn: { name?: string } }
        if (!fn.fn.name || !allowedFunctions.has(fn.fn.name)) throw new Error('Only approved scalar functions are allowed.')
      }
    })
  }
}
