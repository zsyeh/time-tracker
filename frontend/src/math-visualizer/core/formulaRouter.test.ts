import { describe, expect, it } from 'vitest'
import { matrixFromFormula, normalizeFormulaExpression, prepareSurfaceFormula, routeFormula } from './formulaRouter'

describe('Markdown formula routing', () => {
  it('classifies the supported mathematical systems', () => {
    expect(routeFormula('A(t)x, \\det(A), \\lambda v').module).toBe('linear')
    expect(routeFormula('w=f(z)=z^2+1/z').module).toBe('complex')
    expect(routeFormula('F(\\omega)=\\int f(t)e^{-i\\omega t}dt').module).toBe('fourier')
    expect(routeFormula('\\mathcal{L}f(s)=\\int_0^{\\infty}f(t)e^{-st}dt').module).toBe('laplace')
    expect(routeFormula('z=\\sin(x)\\cos(y)').module).toBe('surface')
    expect(routeFormula('y=a\\sin(kx+\\phi)').module).toBe('surface')
  })

  it('normalizes a simple TeX surface for math.js', () => {
    expect(normalizeFormulaExpression('z = \\sin(x) \\cos(y)')).toBe('sin(x) cos(y)')
  })

  it('normalizes nested TeX and assigns draggable surface parameters', () => {
    const prepared = prepareSurfaceFormula('z = \\alpha \\frac{\\sin(kx)}{1 + \\beta(x^2 + y^2)}')
    expect(prepared.expression).not.toContain('\\')
    expect(prepared.parameters.map((parameter) => parameter.symbol)).toEqual(['alpha', 'k', 'beta'])
    expect(prepared.parameters.every((parameter) => parameter.value === 1)).toBe(true)
  })

  it.each([
    ['y=A\\sin(\\omega x+\\phi)', ['A', 'omega', 'phi']],
    ['z=a e^{-\\alpha(x^2+y^2)}', ['a', 'alpha']],
    ['z=\\frac{\\sin(\\sqrt{x^2+y^2})}{1+\\beta(x^2+y^2)}', ['beta']],
    ['z=\\left|x\\right|+\\left|y\\right|', []],
  ])('prepares common parameterized surface notation: %s', (source, expectedParameters) => {
    const prepared = prepareSurfaceFormula(source)
    expect(prepared.unsupportedCommands).toEqual([])
    expect(prepared.parameters.map((parameter) => parameter.symbol)).toEqual(expectedParameters)
  })

  it('extracts a numeric 2×2 matrix', () => {
    expect(matrixFromFormula('A=\\begin{pmatrix}1 & 2 \\\\ -3 & 4\\end{pmatrix}')).toEqual([1, 2, -3, 4])
  })
})
