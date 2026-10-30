import { describe, expect, it } from 'vitest'
import { batchStatus, dryHopWhen, fermentAdvice, fermentCalm, stageCondition, brewFacts, entryInput, entryKindItems, entryValue, dryHopDays, fermentPlan, fromStored, gravityStable, toStored } from '../../app/utils/brewlog'

describe('журнал варки', () => {
  it('плотность вводится в °P, хранится в SG и обратно', () => {
    const sg = toStored('og', 12.8, 'plato')
    expect(sg).toBeCloseTo(1.0517, 3)
    expect(fromStored('og', sg, 'plato')).toBe(12.8)
    expect(toStored('og', 1.052, 'sg')).toBe(1.052)
    expect(toStored('ph', 5.32, 'plato')).toBe(5.32)              // не плотность — как есть
  })

  it('значение для показа — в единицах пивовара', () => {
    expect(entryValue('fg', 1.012, 'sg')).toBe('1,012')
    expect(entryValue('ph', 5.3, 'plato')).toBe('pH 5,3')
    expect(entryValue('fermenter_volume', 23.5, 'plato')).toBe('23,5 л')
    expect(entryValue('temp', 18, 'plato')).toBe('18 °C')
    expect(entryValue('note', null, 'plato')).toBe('')
  })

  it('поле ввода: единица и шаг; у вех и заметки поля нет', () => {
    expect(entryInput('gravity', 'plato')).toMatchObject({ suffix: '°P', step: 0.1 })
    expect(entryInput('temp', 'sg')).toMatchObject({ suffix: '°C', step: 0.5 })
    expect(entryInput('dry_hop', 'sg')).toBeNull()
  })

  it('итог варки одной строкой', () => {
    expect(brewFacts({ og: 1.052, fg: 1.012, abv: 5.25, volume: 23.5 }, 'sg')).toBe('1,052 → 1,012 · 5,3 % · 23,5 л')
    expect(brewFacts({ og: 1.052, fg: null, abv: null, volume: 23 }, 'sg')).toBe('OG 1,052 · 23 л')
    expect(brewFacts({ og: null, fg: null, abv: null, volume: null }, 'sg')).toBe('')
  })

  it('виды записей — по группам, в порядке варки', () => {
    const groups = entryKindItems()
    expect(groups.map(g => g[0]!.label)).toEqual(['Варочный день', 'Брожение и розлив', 'Заметка'])
    expect(groups[0]![1]).toMatchObject({ value: 'ph' })
  })
})

describe('брожение', () => {
  const DAY = 86400
  const plan = {
    fermentation: [{ name: 'Основное', temp: 18, days: 7 }, { name: null, temp: 20, days: 3 }],
    dryHops: [{ day: 4, items: ['Citra 100 г'] }, { day: null, items: ['Хмель'] }],
  }

  it('этапы — с датами от начала, текущий подсвечен', () => {
    const p = fermentPlan(plan, 0, 2 * DAY)
    expect(p.stages.map(s => [s.name, s.from / DAY, s.to / DAY, s.state])).toEqual([
      ['Основное', 0, 7, 'now'], ['Этап 2', 7, 10, 'next'],
    ])
    expect(p.days).toBe(10)
    expect(p.dryHops[0]).toMatchObject({ at: 3 * DAY, state: 'next' })    // 4-й день — через трое суток
    expect(p.dryHops[1]).toMatchObject({ at: null })
    expect(fermentPlan(plan, 0, 3.5 * DAY).dryHops[0]!.state).toBe('now')
  })

  it('разлито — всё позади', () => {
    const p = fermentPlan(plan, 0, 2 * DAY, DAY)
    expect(p.stages.every(s => s.state === 'done')).toBe(true)
  })

  it('статус партии', () => {
    expect(batchStatus({ phase: 'brewday', status: 'running', manual: false, fermentStart: null }, DAY)).toMatchObject({ label: 'варка идёт' })
    expect(batchStatus({ phase: 'brewday', status: 'stopped', manual: false, fermentStart: null }, DAY)).toMatchObject({ label: 'варочный день' })
    expect(batchStatus({ phase: 'brewday', status: 'running', manual: true, fermentStart: null }, DAY)).toMatchObject({ label: 'варочный день' })
    expect(batchStatus({ phase: 'fermenting', status: 'finished', manual: true, fermentStart: 0 }, 2.5 * DAY)).toMatchObject({ label: 'брожение · день 3' })
    expect(batchStatus({ phase: 'packaged', status: 'finished', manual: true, fermentStart: 0 }, 9 * DAY)).toMatchObject({ label: 'разлито' })
    expect(batchStatus({ phase: 'fermenting', status: 'finished', manual: true, fermentStart: 0 }, 90 * DAY)).toBeNull()
    expect(batchStatus({ phase: 'fermenting', status: 'finished', manual: true, fermentStart: null }, DAY)).toBeNull()
  })
})

describe('брожение по факту', () => {
  const DAY = 86400
  const plan = { fermentation: [{ name: 'Основное', temp: 18, days: 7 }, { name: 'Дображивание', temp: 20, days: 3 }, { name: 'Холодное', temp: 4, days: 3 }] }
  const at = (d: number) => d * DAY

  it('переход к этапу сдвигает следующие', () => {
    const p = fermentPlan(plan, 0, at(6), null, [{ kind: 'stage', at: at(5), value: 1 }])
    expect(p.stages.map(s => [s.from / DAY, s.to / DAY, s.manual])).toEqual([[0, 5, false], [5, 8, true], [8, 11, false]])
    expect(p.current).toBe(1)
    expect(p.next).toBe(2)
    expect(p.days).toBe(11)
  })

  it('холодное осветление начинает холодный этап', () => {
    const p = fermentPlan(plan, 0, at(9.5), null, [{ kind: 'cold_crash', at: at(9), value: null }])
    expect(p.stages.map(s => s.from / DAY)).toEqual([0, 7, 9])
    expect(p.stages[1]!.to / DAY).toBe(9)                            // дображивание короче на день
  })

  it('разлито — следующего этапа нет', () => {
    expect(fermentPlan(plan, 0, at(3), at(2)).next).toBeNull()
  })

  it('стабильная плотность — двое суток в пределах 0,001', () => {
    const g = (d: number, value: number) => ({ kind: 'gravity' as const, at: at(d), value })
    expect(gravityStable([g(2, 1.030), g(4, 1.012), g(5, 1.012)])).toBeNull()
    expect(gravityStable([g(2, 1.030), g(4, 1.012), g(5, 1.012), g(6, 1.0115)])).toMatchObject({ value: 1.0115, since: at(4), days: 2 })
    expect(gravityStable([g(4, 1.012), g(6, 1.009)])).toBeNull()
  })
})

describe('сухое охмеление рецепта', () => {
  it('по дням, без дня — в конце', () => {
    expect(dryHopDays([
      { name: 'Citra', amount: 75, use: 'dry_hop', day: 3 },
      { name: 'Magnum', amount: 20, use: 'boil' },
      { name: 'Mosaic', amount: 75, use: 'dry_hop', day: 3 },
      { name: 'Simcoe', amount: 12.5, use: 'dry_hop' },
    ])).toEqual([{ day: 3, gravity: null, items: ['Citra 75 г', 'Mosaic 75 г'] }, { day: null, gravity: null, items: ['Simcoe 12,5 г'] }])
  })

  it('по плотности — раньше тех, что по дням; день при ней — примерный', () => {
    const groups = dryHopDays([
      { name: 'Citra', amount: 50, use: 'dry_hop', day: 5 },
      { name: 'Mosaic', amount: 50, use: 'dry_hop', day: 4, gravity: 1.018 },
      { name: 'Simcoe', amount: 50, use: 'dry_hop', day: 3, gravity: 1.024 },
    ])
    expect(groups.map(g => g.items[0])).toEqual(['Simcoe 50 г', 'Mosaic 50 г', 'Citra 50 г'])
    expect(dryHopWhen(groups[0]!, 'sg')).toBe('при 1,024 · ~3-й день')
    expect(dryHopWhen(groups[2]!, 'sg')).toBe('5-й день брожения')
  })
})

describe('брожение по плотности', () => {
  const DAY = 86400
  const plan = {
    og: 1.050,
    fermentation: [
      { name: 'Основное', temp: 12, days: 5, until: 'gravity' as const, gravity: 1.024 },
      { name: 'Подъём', temp: 14, days: 3, until: 'gravity' as const, gravity: 1.018 },
      { name: 'Пауза', temp: 16.5, days: 4, until: 'fg' as const },
      { name: 'Холод', temp: 4, days: 2, until: 'days' as const },
    ],
    dryHops: [{ day: 4, gravity: 1.020, items: ['Citra 50 г'] }],
  }
  const g = (d: number, value: number, kind: 'gravity' | 'og' = 'gravity') => ({ kind, at: d * DAY, value })
  type F = Parameters<typeof fermentPlan>[4]
  const advise = (now: number, entries: F) => fermentAdvice(fermentPlan(plan, 0, now, null, entries), plan, entries)
  const calm = (now: number, entries: F) => fermentCalm(fermentPlan(plan, 0, now, null, entries), plan, entries)

  it('дни — прикидка: этап по плотности не кончается, пока цель не наступила, следующие сдвигаются', () => {
    const p = fermentPlan(plan, 0, 7 * DAY)
    expect(p.current).toBe(0)
    expect(p.stages[0]).toMatchObject({ state: 'now', to: 7 * DAY, target: 1.024 })
    expect(p.stages.map(s => s.from / DAY)).toEqual([0, 7, 10, 14])
    expect(p.estimated).toBe(true)
    expect(stageCondition(plan.fermentation[0]!, 'sg')).toBe('до 1,024 · ~5 дн.')
    expect(stageCondition(plan.fermentation[2]!, 'sg')).toBe('до FG · ~4 дн.')
    expect(stageCondition(plan.fermentation[3]!, 'sg')).toBe('2 дн.')
  })

  it('цель — от фактической OG; дошли — пора', () => {
    const entries = [g(0, 1.054, 'og'), g(3, 1.0255)]
    const p = fermentPlan(plan, 0, 3.5 * DAY, null, entries)
    expect(p.stages[0]!.target).toBeCloseTo(1 + 0.024 * 54 / 50, 6)          // 1,0259: та же доля сбраживания
    expect(advise(3.5 * DAY, entries)).toMatchObject({ stage: 0, why: 'target', value: 1.0255 })
    expect(p.dryHops[0]!.state).toBe('next')                                  // своя цель сухого — ниже
    expect(advise(3.5 * DAY, [g(3, 1.0255)])).toBeNull() // без OG — цель рецепта 1,024
  })

  it('цель не наступает, а брожение встало — пора всё равно; «до FG» — плотность стоит двое суток', () => {
    expect(advise(7 * DAY, [g(5, 1.030), g(6, 1.0292)])).toMatchObject({ why: 'slow', value: 1.0292 })
    expect(advise(7 * DAY, [g(1, 1.045), g(2, 1.044)])).toBeNull()   // до половины пути — не считается
    const fg = [{ kind: 'stage' as const, at: 6 * DAY, value: 2 }, g(7, 1.012), g(8, 1.012), g(9, 1.0115)]
    expect(advise(9.5 * DAY, fg)).toMatchObject({ stage: 2, why: 'stable' })
    expect(gravityStable([g(1, 1.049), g(3, 1.049)], 1.050)).toBeNull()      // лаг-фаза — ещё не «стоит»
  })

  it('второй этап: половина пути — от плотности на его начало, а не от OG', () => {
    const e = [g(4, 1.0235), { kind: 'stage' as const, at: 4.1 * DAY, value: 1 }, g(5.2, 1.022)]
    expect(advise(5.5 * DAY, e)).toBeNull()                                   // −0,0015 за сутки, до 1,018 далеко
  })

  it('после «до FG» на выдержке — «похоже, закончилось» только по замерам с её начала', () => {
    const fg = [{ kind: 'stage' as const, at: DAY, value: 1 }, { kind: 'stage' as const, at: 2 * DAY, value: 2 },
      g(3, 1.012), g(4, 1.012), g(5, 1.0115), { kind: 'stage' as const, at: 5.1 * DAY, value: 3 }]
    expect(calm(5.2 * DAY, fg)).toBeNull()
    expect(calm(8 * DAY, [...fg, g(6, 1.0115), g(8, 1.0113)])).toMatchObject({ value: 1.0113 })
  })

  it('план пройден, только когда последний этап позади; сухое по плотности — не точкой в прикидочный день', () => {
    const one = { og: 1.050, fermentation: [{ name: 'Основное', temp: 18, days: 7, until: 'fg' as const }], dryHops: [{ day: 3, gravity: 1.020, items: ['Citra'] }] }
    const p = fermentPlan(one, 0, 9 * DAY, null, [g(4, 1.030)])
    expect(p.finished).toBe(false)                                            // прикидка прошла, конечной нет
    expect(p.dryHops[0]).toMatchObject({ at: 2 * DAY, estimated: true, state: 'next' })
    const reached = fermentPlan(one, 0, 9 * DAY, null, [g(4, 1.030), g(6, 1.019)]).dryHops[0]!
    expect(reached).toMatchObject({ at: 6 * DAY, estimated: false, state: 'now' })
  })
})
