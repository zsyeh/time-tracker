import { describe, expect, it } from 'vitest'
import { matrixFromFormula, normalizeFormulaExpression, routeFormula } from './formulaRouter'

describe('Markdown formula routing', () => {
  it('classifies the supported mathematical systems', () => {
    expect(routeFormula('A(t)x, \\det(A), \\lambda v').module).toBe('linear')
    expect(routeFormula('w=f(z)=z^2+1/z').module).toBe('complex')
    expect(routeFormula('F(\\omega)=\\int f(t)e^{-i\\omega t}dt').module).toBe('fourier')
    expect(routeFormula('\\mathcal{L}f(s)=\\int_0^{\\infty}f(t)e^{-st}dt').module).toBe('laplace')
    expect(routeFormula('z=\\sin(x)\\cos(y)').module).toBe('surface')
  })

  it('normalizes a simple TeX surface for math.js', () => {
    expect(normalizeFormulaExpression('z = \\sin(x) \\cos(y)')).toBe('sin(x) cos(y)')
  })

  it('extracts a numeric 2×2 matrix', () => {
    expect(matrixFromFormula('A=\\begin{pmatrix}1 & 2 \\\\ -3 & 4\\end{pmatrix}')).toEqual([1, 2, -3, 4])
  })
})
