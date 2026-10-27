import { describe, expect, it } from 'vitest'
import { abvOf, beerColor, ebcGradient, fmtGravity, gravityIn, platoFromSg, sgFromPlato } from '~/utils/beer'

describe('плотность', () => {
  it('°P и SG взаимно обратны', () => {
    for (const p of [0, 5, 12, 20, 30]) expect(platoFromSg(sgFromPlato(p))).toBeCloseTo(p, 1)
  })

  it('опорные точки: 12 °P ≈ 1.0484, 1.048 ≈ 11.9 °P', () => {
    expect(sgFromPlato(12)).toBeCloseTo(1.0484, 4)
    expect(platoFromSg(1.048)).toBeCloseTo(11.9, 1)
    expect(sgFromPlato(0)).toBe(1)
  })

  it('в единицах человека и с подписью', () => {
    expect(gravityIn(1.048, 'plato')).toBe(11.9)
    expect(gravityIn(1.0484, 'sg')).toBe(1.048)
    expect(fmtGravity(1.048, 'plato')).toBe('11,9 °P')
    expect(fmtGravity(1.05, 'sg')).toBe('1,050')
    expect(fmtGravity(null, 'plato')).toBe('—')
  })
})

describe('abvOf', () => {
  it('1.050 → 1.010: формула с поправкой на плотность даёт 5.34 %, упрощённая 131.25 × ΔSG — 5.25 %', () => {
    // 76.08 × 0.040 / (1.775 − 1.050) × 1.010 / 0.794 = 5.339
    expect(abvOf(1.05, 1.01)).toBeCloseTo(5.339, 2)
    expect(Math.abs(abvOf(1.05, 1.01)! - 0.04 * 131.25)).toBeLessThan(0.1)
  })

  it('без плотностей или без сбраживания — null', () => {
    expect(abvOf(null, 1.01)).toBeNull()
    expect(abvOf(1.05, undefined)).toBeNull()
    expect(abvOf(1.05, 1.05)).toBeNull()
    expect(abvOf(1.01, 1.05)).toBeNull()
  })
})

describe('beerColor', () => {
  const lower = (c: string | null) => c?.toLowerCase()

  it('на опорных точках — их цвет', () => {
    expect(lower(beerColor(2))).toBe('#f8eaa2')
    expect(lower(beerColor(4))).toBe('#f6e07a')
    expect(lower(beerColor(20))).toBe('#c77423')
    expect(lower(beerColor(80))).toBe('#0a0605')
  })

  it('между точками — линейно по каналам', () => {
    // 3 EBC — посередине между #F8EAA2 и #F6E07A
    expect(lower(beerColor(3))).toBe('#f7e58e')
  })

  it('за краями шкалы — крайние цвета', () => {
    expect(lower(beerColor(0))).toBe('#f8eaa2')
    expect(lower(beerColor(500))).toBe('#0a0605')
  })

  it('цвет не задан — null', () => {
    expect(beerColor(null)).toBeNull()
    expect(beerColor(undefined)).toBeNull()
  })

  it('градиент проходит через опорные точки внутри диапазона', () => {
    expect(ebcGradient(4, 12)).toBe('linear-gradient(to right, #f6e07a 0.0%, #f2d04e 25.0%, #edc03a 50.0%, #e2a42c 100.0%)')
    expect(ebcGradient(10, 10)).toBe(beerColor(10))
  })
})
