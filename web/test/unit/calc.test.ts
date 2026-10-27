import { describe, expect, it } from 'vitest'
import { platoFromSg } from '~/utils/beer'
import { adjustable, calcRecipe, extractForSg, fitBase, fitEbc, fitFg, fitIbu, fitOg, sgFromExtract, yieldOf } from '~/utils/calc'
import { newYeast } from '~/utils/recipe'
import { draft, hop, malt } from './fixtures'

// Опорный рецепт: 5 кг светлого солода 5 EBC, 23 л после кипячения, эффективность 75 %, 30 г хмеля 10 % на 60 мин.
// Ожидаемое посчитано отдельно по формулам из шапки calc.ts:
//   экстракт = 5 × 0.80 × 0.75 = 3.0 кг; °P = 100 × 3.0 / (23 × SG) → 12.41 °P, SG 1.0501
//   (проверка через PPG: 0.80 × 46.21 × 11.02 фунта × 0.75 / 6.076 галлона = 50.3 пункта);
//   IBU Тинсета = 1.65 × 0.000125^0.0501 × (1 − e^−2.4) / 4.15 × 0.10 × 30 000 / 23 = 1.0518 × 0.2191 × 130.43 = 30.05;
//   цвет Мори: °L = (5 / 1.97 + 0.76) / 1.3546 = 2.435, MCU = 11.023 × 2.435 / 6.076 = 4.417,
//   SRM = 1.4922 × 4.417^0.6859 = 4.134, EBC = 8.14.
const reference = () => draft({ fermentables: [malt(5, 5)], hops: [hop(30, 10, 60)] })

describe('calcRecipe', () => {
  it('OG, FG, ABV, IBU и цвет опорного рецепта', () => {
    const c = calcRecipe(reference())
    expect(c.og).toBeCloseTo(1.05015, 4)
    expect(Math.abs(c.og! - 1.0503)).toBeLessThan(0.0005)         // PPG
    expect(c.fg).toBeCloseTo(1 + 0.05015 * 0.25, 4)               // 75 % по умолчанию
    expect(c.defaultAttenuation).toBe(true)
    expect(c.abv).toBeCloseTo(5.03, 1)
    expect(c.ibu).toBeCloseTo(30.05, 1)
    expect(c.ebc).toBeCloseTo(8.14, 1)
  })

  it('экстракт и плотность взаимно обратны (с точностью формул °P ↔ SG)', () => {
    expect(extractForSg(sgFromExtract(3, 23), 23)).toBeCloseTo(3, 2)
    expect(platoFromSg(sgFromExtract(3, 23))).toBeCloseTo(12.41, 1)
  })

  it('сбраживание — из дрожжей', () => {
    const c = calcRecipe(draft({ fermentables: [malt(5, 5)], yeasts: [{ ...newYeast(), name: 'US-05', attenuation: 80 }] }))
    expect(c.attenuation).toBe(80)
    expect(c.defaultAttenuation).toBe(false)
    expect(c.fg).toBeCloseTo(1 + (c.og! - 1) * 0.2, 6)
  })

  it('без объёма считать не из чего', () => {
    const c = calcRecipe(draft({ batch: { volume: null, efficiency: 75 }, fermentables: [malt(5, 5)], hops: [hop(30, 10, 60)] }))
    expect([c.og, c.fg, c.abv, c.ibu, c.ebc]).toEqual([null, null, null, null, null])
  })

  it('без хмеля IBU нет, без засыпи — OG и цвета нет', () => {
    expect(calcRecipe(draft({ fermentables: [malt(5, 5)] })).ibu).toBeNull()
    const c = calcRecipe(draft({ hops: [hop(30, 10, 60)] }))
    expect([c.og, c.ebc]).toEqual([null, null])
    expect(c.ibu).toBeGreaterThan(0)                                 // горечь считается по OG 1.050
  })

  it('выход экстракта по типу и цвету сырья', () => {
    expect(yieldOf(malt(1, 5))).toBe(80)
    expect(yieldOf(malt(1, 120))).toBe(75)
    expect(yieldOf(malt(1, 1000))).toBe(60)
    expect(yieldOf(malt(1, 0, { kind: 'adjunct' }))).toBe(75)
    expect(yieldOf(malt(1, 0, { kind: 'sugar' }))).toBe(100)
    expect(yieldOf(malt(1, 0, { kind: 'extract' }))).toBe(95)
  })

  it('сахар и экстракт растворяются целиком — эффективность на них не действует', () => {
    const sugar = (efficiency: number) => calcRecipe(draft({
      batch: { volume: 20, efficiency },
      fermentables: [malt(1, 0, { kind: 'sugar', use: 'boil', minutes: 10 })],
    })).og
    expect(sugar(50)).toBe(sugar(90))
    expect(extractForSg(sugar(50)!, 20)).toBeCloseTo(1, 2)
    const dme = calcRecipe(draft({ batch: { volume: 20, efficiency: 50 }, fermentables: [malt(1, 10, { kind: 'extract', use: 'boil' })] })).og
    expect(extractForSg(dme!, 20)).toBeCloseTo(0.95, 2)
  })

  it('сырьё на брожении в OG не входит, но цвет даёт', () => {
    const c = calcRecipe(draft({ fermentables: [malt(5, 5), malt(1, 100, { kind: 'sugar', use: 'fermentation' })] }))
    expect(c.og).toBeCloseTo(calcRecipe(reference()).og!, 10)
    expect(c.ebc).toBeGreaterThan(calcRecipe(reference()).ebc!)
  })

  it('сахар сбраживается целиком: на брожении — прибавляет крепость, в кипячении — ещё и снижает FG', () => {
    const base = calcRecipe(reference())
    // 0.5 кг сахара на 23 л — ~2.15 % экстракта, сбраживается без остатка: ~+1 % крепости
    const later = calcRecipe(draft({ fermentables: [malt(5, 5), malt(0.5, 0, { kind: 'sugar', use: 'fermentation' })] }))
    expect(later.og).toBeCloseTo(base.og!, 10)
    expect(later.fg).toBeCloseTo(base.fg!, 10)
    expect(later.abv! - base.abv!).toBeGreaterThan(0.9)
    expect(later.abv! - base.abv!).toBeLessThan(1.2)
    const boiled = calcRecipe(draft({ fermentables: [malt(5, 5), malt(0.5, 0, { kind: 'sugar', use: 'boil', minutes: 10 })] }))
    expect(boiled.og).toBeGreaterThan(base.og!)
    expect(boiled.fg).toBeCloseTo(base.fg!, 10)                  // остаток — только от солода
    expect(boiled.abv).toBeCloseTo(later.abv!, 1)
  })

  it('первое сусло — горечь на всё кипячение; вирпул и сухое охмеление горечи не дают', () => {
    const at60 = calcRecipe(reference()).ibu!
    const fwh = calcRecipe(draft({ fermentables: [malt(5, 5)], hops: [hop(30, 10, null, { use: 'first_wort' })] })).ibu
    expect(fwh).toBeCloseTo(at60, 6)
    const late = calcRecipe(draft({
      fermentables: [malt(5, 5)],
      hops: [hop(50, 10, 20, { use: 'whirlpool' }), hop(100, 10, null, { use: 'dry_hop', day: 3 })],
    }))
    expect(late.ibu).toBe(0)
  })

  it('чем короче кипячение, тем меньше горечи', () => {
    const ibu = (minutes: number) => calcRecipe(draft({ fermentables: [malt(5, 5)], hops: [hop(30, 10, minutes)] })).ibu!
    expect(ibu(10)).toBeLessThan(ibu(30))
    expect(ibu(30)).toBeLessThan(ibu(60))
  })
})

describe('подгонка под цель', () => {
  const recipe = () => draft({
    fermentables: [malt(4, 5), malt(0.5, 120), malt(0.3, 0, { kind: 'sugar', use: 'fermentation' })],
    hops: [hop(20, 12, 60), hop(30, 5, 10), hop(50, 8, 15, { use: 'whirlpool' })],
    yeasts: [newYeast()],
  })

  it('что можно подгонять', () => {
    expect(adjustable(recipe())).toEqual({ og: true, fg: true, ibu: true, ebc: true })
    expect(adjustable(draft())).toEqual({ og: false, fg: false, ibu: false, ebc: false })
    expect(adjustable(draft({ batch: { volume: null, efficiency: 75 }, fermentables: [malt(5, 5)] })).og).toBe(false)
  })

  it('OG: вся засыпь в сусле пропорционально, сырьё на брожении не трогаем', () => {
    const d = recipe()
    fitOg(d, fitBase(d), 1.06)
    expect(Math.abs(calcRecipe(d).og! - 1.06)).toBeLessThan(0.0005)
    expect(d.fermentables[0]!.amount! / d.fermentables[1]!.amount!).toBeCloseTo(8, 1)
    expect(d.fermentables[2]!.amount).toBe(0.3)
  })

  it('OG: подгонка от снимка — повторное перетаскивание не копит округление', () => {
    const d = recipe()
    const base = fitBase(d)
    fitOg(d, base, 1.07)
    fitOg(d, base, 1.05)
    const fresh = recipe()
    fitOg(fresh, fitBase(fresh), 1.05)
    expect(d.fermentables.map(f => f.amount)).toEqual(fresh.fermentables.map(f => f.amount))
  })

  it('IBU: меняется только горькая закладка', () => {
    const d = recipe()
    fitIbu(d, fitBase(d), 40)
    expect(Math.abs(calcRecipe(d).ibu! - 40)).toBeLessThan(0.1)
    expect(d.hops.slice(1).map(h => h.amount)).toEqual([30, 50])
  })

  it('IBU: горьких закладок на одной минуте несколько — меняются все', () => {
    const d = recipe()
    d.hops.push(hop(10, 12, 60))
    fitIbu(d, fitBase(d), 50)
    expect(Math.abs(calcRecipe(d).ibu! - 50)).toBeLessThan(0.2)            // две закладки — два округления до 0.1 г
    expect(d.hops[0]!.amount! / d.hops[3]!.amount!).toBeCloseTo(2, 1)
  })

  it('IBU: цель ниже горечи поздних закладок — горькая закладка в ноль', () => {
    const d = recipe()
    fitIbu(d, fitBase(d), 1)
    expect(d.hops[0]!.amount).toBe(0)
  })

  it('FG: сбраживание дрожжей', () => {
    const d = recipe()
    fitFg(d, 1.012)
    const c = calcRecipe(d)
    expect(Number.isInteger(d.yeasts[0]!.attenuation)).toBe(true)
    expect(Math.abs(c.fg! - 1.012)).toBeLessThan(0.0005)
  })

  it('FG: с сахаром в кипячении цель тоже достигается', () => {
    const d = draft({ fermentables: [malt(5, 5), malt(1, 0, { kind: 'sugar', use: 'boil', minutes: 10 })], yeasts: [newYeast()] })
    fitFg(d, 1.010)
    expect(Math.abs(calcRecipe(d).fg! - 1.010)).toBeLessThan(0.0005)
  })

  it('цвет: масса самого тёмного солода', () => {
    const d = recipe()
    fitEbc(d, fitBase(d), 30)
    expect(Math.abs(calcRecipe(d).ebc! - 30)).toBeLessThan(0.1)
    expect(d.fermentables[0]!.amount).toBe(4)
  })

  it('цвет: светлее остальной засыпи не сделать — тёмного солода ноль', () => {
    const d = recipe()
    fitEbc(d, fitBase(d), 1)
    expect(d.fermentables[1]!.amount).toBe(0)
  })
})
