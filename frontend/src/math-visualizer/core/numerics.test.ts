import { describe, expect, it } from 'vitest'
import {
  approximately, determinant, eigenDirections, evaluateComplex, fourierCoefficient,
  numericalLaplace, surfaceValue, transform,
} from './numerics'

describe('linear algebra', () => {
  it('keeps the identity determinant and basis columns exact', () => {
    expect(determinant([1, 0, 0, 1])).toBe(1)
    expect(transform([2, 3, 5, 7], [1, 0])).toEqual([2, 5])
    expect(transform([2, 3, 5, 7], [0, 1])).toEqual([3, 7])
  })

  it('returns real eigendirections that satisfy Av = lambda v', () => {
    const matrix = [3, 1, 0, 2] as const
    for (const eigen of eigenDirections(matrix)) {
      const mapped = transform(matrix, eigen.vector)
      expect(approximately(mapped[0], eigen.value * eigen.vector[0])).toBe(true)
      expect(approximately(mapped[1], eigen.value * eigen.vector[1])).toBe(true)
    }
  })
})

describe('complex and transforms', () => {
  it('maps 1+i through z² to 2i', () => {
    const value = evaluateComplex('square', { re: 1, im: 1 })!
    expect(value.re).toBeCloseTo(0, 10)
    expect(value.im).toBeCloseTo(2, 10)
  })

  it('finds the sine frequency peak', () => {
    const atThree = fourierCoefficient('sine', 3)
    const atFive = fourierCoefficient('sine', 5)
    expect(Math.hypot(atThree.re, atThree.im)).toBeGreaterThan(.49)
    expect(Math.hypot(atFive.re, atFive.im)).toBeLessThan(.01)
  })

  it('approximates L{1}=1/s on the positive real axis', () => {
    const value = numericalLaplace('constant', 2, 0, 12, 12000)
    expect(value.re).toBeCloseTo(.5, 3)
    expect(value.im).toBeCloseTo(0, 5)
  })

  it('samples the selected 3D function', () => {
    expect(surfaceValue('saddle', 2, 1)).toBeCloseTo(.66)
  })
})
