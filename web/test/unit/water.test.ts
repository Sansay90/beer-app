import { describe, expect, it } from 'vitest'
import type { WaterAddition } from '~/types'
import { additionEffect, chlorideSulfate, WATER_AGENTS, waterAmount, waterProfiles, waterVolumes } from '~/utils/water'
import { malt } from './fixtures'

describe('ионы солей', () => {
  // атомные массы → мг иона на 1 г соли, независимо от таблицы WATER_AGENTS
  const A = { Ca: 40.078, Mg: 24.305, Na: 22.99, Cl: 35.453, S: 32.06, O: 15.999, H: 1.008, C: 12.011 }
  const H2O = 2 * A.H + A.O
  const SO4 = A.S + 4 * A.O
  const HCO3 = A.H + A.C + 3 * A.O
  const mgPerG = (ion: number, salt: number) => (ion / salt) * 1000

  it.each([
    ['cacl2', 'ca', mgPerG(A.Ca, A.Ca + 2 * A.Cl + 2 * H2O)],
    ['cacl2', 'cl', mgPerG(2 * A.Cl, A.Ca + 2 * A.Cl + 2 * H2O)],
    ['cacl2_anhydrous', 'ca', mgPerG(A.Ca, A.Ca + 2 * A.Cl)],
    ['gypsum', 'ca', mgPerG(A.Ca, A.Ca + SO4 + 2 * H2O)],
    ['gypsum', 'so4', mgPerG(SO4, A.Ca + SO4 + 2 * H2O)],
    ['nacl', 'na', mgPerG(A.Na, A.Na + A.Cl)],
    ['nahco3', 'hco3', mgPerG(HCO3, A.Na + HCO3)],
    ['caco3', 'hco3', mgPerG(2 * HCO3, A.Ca + A.C + 3 * A.O)],          // в заторе — 2 HCO₃⁻ на CaCO₃
    ['epsom', 'mg', mgPerG(A.Mg, A.Mg + SO4 + 7 * H2O)],
  ] as const)('%s → %s', (agent, ion, expected) => {
    expect(Math.abs(WATER_AGENTS[agent].ions[ion]! - expected)).toBeLessThan(0.5)
  })

  it('кислоты ионов не дают', () => {
    expect(WATER_AGENTS.lactic80.ions).toEqual({})
  })
})

describe('waterVolumes', () => {
  const recipe = (over: { ratio?: number | null; minutes?: number } = {}) => ({
    batch: { volume: 23 },
    boil: { minutes: over.minutes ?? 60 },
    fermentables: [malt(5, 5), malt(1, 0, { kind: 'sugar', use: 'boil' })],
    water: { ratio: over.ratio === undefined ? 3 : over.ratio },
  })

  it('заторная по гидромодулю, вся — после кипячения + испарение + дробина, промывочная — остальное', () => {
    // засыпь в затор 5 кг (сахар на кипячении не считается): затор 15 л, перед кипячением 23 + 3 = 26 л,
    // дробина удержит 5 × 0.8 = 4 л, всего 30 л, промывка 15 л
    expect(waterVolumes(recipe(), 3)).toEqual({ mash: 15, sparge: 15, preBoil: 26, absorbed: 4, total: 30, excess: false })
  })

  it('испарение — за время кипячения', () => {
    expect(waterVolumes(recipe({ minutes: 90 }), 3).preBoil).toBe(27.5)
  })

  it('испарение неизвестно — только заторная', () => {
    expect(waterVolumes(recipe(), null)).toMatchObject({ mash: 15, sparge: null, preBoil: null, total: null })
  })

  it('без гидромодуля заторной и промывочной нет', () => {
    expect(waterVolumes(recipe({ ratio: null }), 3)).toMatchObject({ mash: null, sparge: null, total: 30 })
  })

  it('заторной больше всей воды — промывки нет, флаг excess', () => {
    expect(waterVolumes(recipe({ ratio: 7 }), 3)).toMatchObject({ mash: 35, sparge: 0, excess: true })
  })

  it('объёмы округляются до 0.1 л', () => {
    expect(waterVolumes({ ...recipe(), fermentables: [malt(4.33, 5)] }, 3).mash).toBe(13)
  })
})

describe('профиль воды', () => {
  const additions: WaterAddition[] = [
    { agent: 'gypsum', name: '', amount: 5, target: 'mash' },
    { agent: 'cacl2', name: '', amount: 3, target: 'mash' },
    { agent: 'nacl', name: '', amount: 2, target: 'sparge' },
    { agent: 'lactic80', name: '', amount: 2.5, target: 'mash' },
  ]
  const volumes = { mash: 15, sparge: 15 }

  it('ионы заторной, промывочной и всей воды, мг/л', () => {
    const p = waterProfiles({ additions }, volumes)
    expect(p.mash!.ca).toBeCloseTo((5 * 232.8 + 3 * 272.6) / 15, 6)
    expect(p.mash!.so4).toBeCloseTo((5 * 557.9) / 15, 6)
    expect(p.mash!.na).toBe(0)
    expect(p.sparge!.na).toBeCloseTo((2 * 393.4) / 15, 6)
    expect(p.sparge!.ca).toBe(0)
    expect(p.total!.cl).toBeCloseTo((3 * 482.3 + 2 * 606.6) / 30, 6)
  })

  it('исходная вода прибавляется', () => {
    const p = waterProfiles({ additions, source: { ca: 10, hco3: 50 } }, volumes)
    expect(p.mash!.ca).toBeCloseTo(10 + (5 * 232.8 + 3 * 272.6) / 15, 6)
    expect(p.sparge!.hco3).toBe(50)
  })

  it('без объёма профиля нет', () => {
    expect(waterProfiles({ additions }, { mash: null, sparge: 15 })).toMatchObject({ mash: null, total: null })
  })

  it('что даёт добавка своей воде', () => {
    expect(additionEffect({ additions }, volumes, 0)).toBe('Ca +78 · SO₄ +186 мг/л')
    expect(additionEffect({ additions }, volumes, 2)).toBe('Na +52 · Cl +81 мг/л')
    expect(additionEffect({ additions }, volumes, 3)).toBeNull()                      // кислота
    expect(additionEffect({ additions }, { mash: null, sparge: 15 }, 0)).toBeNull()
    expect(additionEffect({ additions }, volumes, 9)).toBeNull()
  })

  it('хлорид к сульфату', () => {
    expect(chlorideSulfate({ ca: 0, mg: 0, na: 0, cl: 100, so4: 50, hco3: 0 })).toBe(2)
    expect(chlorideSulfate({ ca: 0, mg: 0, na: 0, cl: 100, so4: 0, hco3: 0 })).toBeNull()
    expect(chlorideSulfate(null)).toBeNull()
  })

  it('количество с единицей', () => {
    expect(waterAmount('gypsum', 5)).toBe('5 г')
    expect(waterAmount('lactic80', 2.5)).toBe('2,5 мл')
    expect(waterAmount('gypsum', null)).toBeNull()
  })
})
