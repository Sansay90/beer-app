import { describe, expect, it } from 'vitest'
import type { Recipe } from '~/types'
import { calcRecipe, DEFAULT_EFFICIENCY } from '~/utils/calc'
import {
  blankRecipe, boilGroups, boilItems, deviceTimers, fermentationStep, mashStep, newMisc, options, programMinutes, programOf, programSummary,
  share, toDraft, toRecipe, totalKg, validateRecipe, wattOptions, whenInBoil, whenLabel, HOP_USES,
} from '~/utils/recipe'
import { draft, hop, LIMITS, malt } from './fixtures'

describe('новый рецепт', () => {
  it('объём и эффективность — из основного оборудования, мощность — потолок модели', () => {
    const d = blankRecipe(LIMITS, { volume: 23, efficiency: 82 })
    expect(d.batch).toEqual({ volume: 23, efficiency: 82 })
    expect(d.mash.map(s => [s.temp, s.minutes, s.watts])).toEqual([[66, 60, 2500], [78, 10, 2500]])
    expect(d.boil).toEqual({ minutes: 60, watts: 2500 })
    expect(validateRecipe(d, LIMITS)).toEqual([])
  })

  it('без профиля — эффективность по умолчанию', () => {
    expect(blankRecipe(LIMITS, null).batch.efficiency).toBe(DEFAULT_EFFICIENCY)
  })

  it('добавки — когда их обычно кладут', () => {
    expect(newMisc('spice')).toMatchObject({ use: 'boil', minutes: 5 })
    expect(newMisc('fining')).toMatchObject({ use: 'boil', minutes: 15 })
    expect(newMisc('adjunct')).toMatchObject({ use: 'boil', minutes: 10 })
  })

  it('варианты мощности — от потолка вниз с шагом', () => {
    expect(wattOptions({ ...LIMITS, minWatts: 2000 }).map(o => o.value)).toEqual([2500, 2400, 2300, 2200, 2100, 2000])
    expect(wattOptions(null)[0]).toEqual({ label: '2500 W', value: 2500 })
    expect(wattOptions(null).at(-1)!.value).toBe(100)
  })
})

describe('форма ↔ API', () => {
  const full = () => draft({
    name: '  Пилс  ',
    fermentables: [malt(5, 3.5, { name: ' Pilsner ' }), malt(null as unknown as number, null as unknown as number, { name: '' }),
      malt(0.5, 0, { kind: 'sugar', use: 'boil', minutes: 15 }), malt(0.3, 0, { kind: 'sugar', use: 'mash', minutes: 20 })],
    hops: [hop(30, 4, 60, { name: 'Saaz' }), hop(50, 4, 7, { name: 'Saaz', use: 'dry_hop', day: 5 }),
      hop(20, 4, 20, { name: 'Saaz', use: 'whirlpool', day: 2 })],
    miscs: [{ ...newMisc('fining'), name: 'Ирландский мох', amount: 5 }, { ...newMisc('equipment'), amount: 1 }, newMisc('spice')],
    yeasts: [{ name: ' W-34/70 ', form: 'dry', amount: 2, unit: 'pkg', attenuation: 80 }, { name: '', form: 'dry', amount: 1, unit: 'pkg', attenuation: null }],
    water: {
      ratio: 3,
      source: { ca: 0, mg: 0, na: 0, cl: 0, so4: 0, hco3: 0 },
      additions: [
        { agent: 'cacl2', name: 'лишнее', amount: 3, target: 'mash' },
        { agent: 'gypsum', name: '', amount: null, target: 'mash' },
        { agent: 'other', name: ' Фосфорная ', amount: null, target: 'mash' },
      ],
    },
    mash: [mashStep(2000, 52, 10, ' '), mashStep(2000, 64, 45, 'Осахаривание')],
    notes: '  Светлый лагер.  ',
  })

  it('пустые строки отбрасываются, названия обрезаются', () => {
    const r = toRecipe(full())
    expect(r.name).toBe('Пилс')
    expect(r.notes).toBe('Светлый лагер.')
    expect(r.fermentables.map(f => f.name)).toEqual(['Pilsner', 'Солод', 'Солод'])
    expect(r.yeasts).toEqual([{ name: 'W-34/70', form: 'dry', amount: 2, unit: 'pkg', attenuation: 80 }])
    expect(r.mash.map(s => s.name)).toEqual([null, 'Осахаривание'])
  })

  it('время — только там, где оно имеет смысл', () => {
    const r = toRecipe(full())
    expect(r.fermentables.map(f => f.minutes)).toEqual([null, 15, null])
    expect(r.hops.map(h => [h.minutes, h.day])).toEqual([[60, null], [null, 5], [20, null]])
  })

  it('оборудование — без количества и даже без названия', () => {
    const r = toRecipe(full())
    expect(r.miscs.map(m => [m.kind, m.amount])).toEqual([['fining', 5], ['equipment', null]])
  })

  it('соли без количества отбрасываются, название — только у «Другого»', () => {
    expect(toRecipe(full()).water!.additions).toEqual([
      { agent: 'cacl2', name: '', amount: 3, target: 'mash' },
      { agent: 'other', name: 'Фосфорная', amount: null, target: 'mash' },
    ])
  })

  it('показатели — посчитанные по ингредиентам', () => {
    const d = full()
    const c = calcRecipe(d)
    expect(toRecipe(d).targets).toEqual({ og: c.og, fg: c.fg, ibu: c.ibu, ebc: c.ebc, abv: c.abv })
  })

  it('API → форма → API без потерь', () => {
    const r = toRecipe(full())
    expect(toRecipe(toDraft(r))).toEqual(r)
  })

  it('пустые поля ответа сервиса — значения формы по умолчанию', () => {
    const d = toDraft({
      name: 'Минимум', fermentables: [{ name: 'Pale', kind: 'grain', use: 'mash' }], hops: [], miscs: [], yeasts: [],
      mash: [{ temp: 66, minutes: 60, watts: 2000 }], fermentation: [], notes: '',
    } as Recipe)
    expect(d.batch).toEqual({ volume: null, efficiency: null })
    expect(d.fermentables[0]).toEqual({ name: 'Pale', kind: 'grain', amount: null, ebc: null, use: 'mash', minutes: null })
    expect(d.water).toEqual({ ratio: null, source: { ca: 0, mg: 0, na: 0, cl: 0, so4: 0, hco3: 0 }, additions: [] })
    expect(d.mash[0]!.name).toBe('')
    expect(d.boil).toBeNull()
    expect(d.style).toBeNull()
  })
})

describe('программа пивоварни и закладки', () => {
  const recipe = () => draft({
    mash: [mashStep(2000, 52, 15), mashStep(2000, 66, 60, 'Осахаривание')],
    boil: { minutes: 60, watts: 2500 },
    hops: [hop(30, 10, 60, { name: 'Magnum' }), hop(20, 5, 10, { name: 'Saaz' }), hop(40, 5, 15, { name: 'Saaz', use: 'whirlpool' }),
      hop(50, 5, null, { name: 'Citra', use: 'dry_hop', day: 3 }), hop(10, 5, 75, { name: 'Лишний' })],
    miscs: [{ ...newMisc('fining'), name: 'Мох', amount: 5, minutes: 10 }, { ...newMisc('spice'), name: 'Кориандр', amount: 15, use: 'fermentation' }],
    fermentables: [malt(5, 5), malt(0.5, 0, { name: 'Декстроза', kind: 'sugar', use: 'boil', minutes: 30 })],
  })

  it('шаги: паузы затирания, затем кипячение', () => {
    expect(programOf(recipe())).toEqual([
      { name: 'Пауза 1', temp: 52, minutes: 15, watts: 2000, boil: false },
      { name: 'Осахаривание', temp: 66, minutes: 60, watts: 2000, boil: false },
      { name: 'Кипячение', temp: 100.1, minutes: 60, watts: 2500, boil: true },
    ])
    expect(programOf(recipe(), 99.5).at(-1)!.temp).toBe(99.5)
    expect(programMinutes(recipe())).toBe(135)
    expect(programOf({ ...recipe(), boil: null })).toHaveLength(2)
  })

  it('закладки: от ранних к поздним, вирпул — в конце, сухое охмеление и вне кипячения — нет', () => {
    expect(boilItems(recipe()).map(i => [i.minutes, i.kind, i.name, i.amount, i.unit])).toEqual([
      [60, 'hop', 'Magnum', 30, 'g'],
      [30, 'sugar', 'Декстроза', 0.5, 'kg'],
      [10, 'hop', 'Saaz', 20, 'g'],
      [10, 'fining', 'Мох', 5, 'g'],
      [0, 'hop', 'Saaz', 40, 'g'],
    ])
    expect(boilItems({ ...recipe(), boil: null })).toEqual([])
  })

  it('напоминания — по одному на минуту', () => {
    expect(boilGroups(recipe()).map(g => [g.minutes, g.items.length])).toEqual([[60, 1], [30, 1], [10, 2], [0, 1]])
  })

  it('таймеры пивоварни — строго внутри кипячения, без повторов', () => {
    expect(deviceTimers(recipe())).toEqual([30, 10])
  })

  it('подписи времени', () => {
    expect(whenInBoil(0, 60)).toBe('в конце кипячения')
    expect(whenInBoil(60, 60)).toBe('в начале кипячения')
    expect(whenInBoil(15, 60)).toBe('за 15 мин до конца')
    expect(whenLabel(HOP_USES, 'boil', 60)).toBe('Кипячение · 60 мин')
    expect(whenLabel(HOP_USES, 'whirlpool', 20)).toBe('Вирпул · 20 мин')
    expect(whenLabel(HOP_USES, 'dry_hop', null, 3)).toBe('Сухое охмеление · 3-й день')
    expect(whenLabel(HOP_USES, 'mash')).toBe('Затор')
    expect(whenLabel(HOP_USES, 'unknown')).toBe('unknown')
  })

  it('сводка программы', () => {
    expect(programSummary(recipe())).toBe('3 шага · 2 ч 15 мин')
    expect(programSummary({ ...recipe(), mash: [], boil: { minutes: 60, watts: 2000 } })).toBe('1 шаг · 1 ч')
    expect(programSummary({ ...recipe(), mash: [], boil: null })).toBe('без программы')
  })
})

describe('validateRecipe', () => {
  const ok = () => draft({
    mash: [mashStep(2000, 66, 60)],
    hops: [hop(30, 10, 60)],
    fermentables: [malt(5, 5)],
  })

  it('годный рецепт — без ошибок', () => {
    expect(validateRecipe(ok(), LIMITS)).toEqual([])
  })

  it('название, температура, длительность и мощность пауз', () => {
    const d = ok()
    d.name = ' '
    d.mash = [mashStep(2000, 10, 60), mashStep(2000, 66, 0.5), mashStep(2550, 66, 60), mashStep(3000, 66, 60)]
    expect(validateRecipe(d, LIMITS)).toEqual([
      'Нужно название рецепта',
      'Пауза 1: температура 20…100 °C',
      'Пауза 2: длительность — целые минуты от 1',
      'Пауза 3: мощность 100…2500 W',
      'Пауза 4: мощность 100…2500 W',
    ])
  })

  it('потолок мощности неизвестен — любая кратная шагу', () => {
    const d = ok()
    d.mash = [mashStep(5000, 66, 60), mashStep(1050, 66, 60), mashStep(1025, 66, 60)]
    expect(validateRecipe(d, { ...LIMITS, maxWatts: null, wattsStep: 50 })).toEqual(['Пауза 3: мощность от 100 W, кратно 50'])
    expect(validateRecipe(d, { ...LIMITS, maxWatts: null })).toEqual([
      'Пауза 2: мощность от 100 W, кратно 100',
      'Пауза 3: мощность от 100 W, кратно 100',
    ])
  })

  it('шагов больше, чем помнит пивоварня', () => {
    const d = ok()
    d.mash = Array.from({ length: 9 }, () => mashStep(2000, 66, 10))
    expect(validateRecipe(d, LIMITS)).toEqual(['Программа: не больше 9 шагов вместе с кипячением'])
  })

  it('закладки на кипячении: без времени, за пределами кипячения, без кипячения', () => {
    const d = ok()
    d.hops = [hop(30, 10, null, { name: 'Magnum' }), hop(10, 5, 90, { name: 'Saaz' })]
    d.miscs = [{ ...newMisc('fining'), minutes: 70 }]
    expect(validateRecipe(d, LIMITS)).toEqual([
      '«Magnum»: укажите, за сколько минут до конца кипячения',
      '«Saaz» за 90 мин — кипячение длится 60 мин',
      '«осветлитель» за 70 мин — кипячение длится 60 мин',
    ])
    d.boil = null
    expect(validateRecipe(d, LIMITS)).toContain('«Magnum» — на кипячении, а кипячения в программе нет')
  })

  it('разных минут закладок больше, чем таймеров у пивоварни', () => {
    const d = ok()
    d.hops = [50, 40, 30].map(m => hop(10, 5, m))
    expect(validateRecipe(d, { ...LIMITS, maxAdditions: 2 })).toEqual(['Закладки на кипячении — не больше чем на 2 разных минут'])
  })

  it('строка с количеством, но без названия', () => {
    const d = ok()
    d.fermentables.push(malt(1, 5, { name: '' }))
    d.hops.push(hop(10, 5, 10, { name: '' }))
    expect(validateRecipe(d, LIMITS)).toEqual(['Засыпь: у строки нет названия', 'Хмель: у строки нет названия'])
  })
})

describe('сводка', () => {
  it('масса засыпи и доля', () => {
    expect(totalKg([{ amount: 4.5 }, { amount: null }, { amount: 0.5 }])).toBe(5)
    expect(share(0.5, 5)).toBe(10)
    expect(share(null, 5)).toBeNull()
    expect(share(1, 0)).toBeNull()
  })

  it('варианты для выпадающего списка', () => {
    expect(options({ a: 'А', b: 'Б' })).toEqual([{ value: 'a', label: 'А' }, { value: 'b', label: 'Б' }])
  })
})

describe('брожение в форме', () => {
  const stage = (over: Partial<ReturnType<typeof fermentationStep>> = {}) => ({ ...fermentationStep(12, 5, 'Основное', 'gravity'), ...over })

  it('«до плотности» — с плотностью, выдержка — с днями; у «до плотности» дни необязательны', () => {
    expect(validateRecipe(draft({ fermentation: [stage()] }), LIMITS)).toEqual(['Брожение: у этапа «Основное» — до какой плотности'])
    expect(validateRecipe(draft({ fermentation: [stage({ until: 'days', days: 0 })] }), LIMITS)).toEqual(['Брожение: у выдержки «Основное» — сколько дней'])
    expect(validateRecipe(draft({ fermentation: [stage({ gravity: 1.024, days: 0 })] }), LIMITS)).toEqual([])
  })

  it('в API: плотность — только у «до плотности» и у сухого охмеления; стёртые дни — 0', () => {
    const r = toRecipe(draft({
      fermentation: [stage({ until: 'fg', gravity: 1.024 }), stage({ gravity: 1.018, days: undefined as unknown as number })],
      hops: [hop(30, 4, 60, { gravity: 1.020 }), hop(50, 4, 7, { use: 'dry_hop', day: 4, gravity: 1.020 })],
    }))
    expect(r.fermentation!.map(s => [s.until, s.gravity, s.days])).toEqual([['fg', null, 5], ['gravity', 1.018, 0]])
    expect(r.hops!.map(h => h.gravity)).toEqual([null, 1.02])
  })
})
