import { describe, expect, it } from 'vitest'
import type { AdditionSlot, DeviceStep, HistoryPoint, Snapshot } from '~/types'
import {
  additionViews, heatingEta, heatingRate, nextAction, phaseOf, programRemaining, programTotal, remainingSeconds, statusOf,
  stepProgress, stepViews,
} from '~/utils/brew'
import { dots, snapshot } from './fixtures'

// Программа в пивоварне: две паузы и кипячение 60 мин с закладками на 60, 30, 10 и 0 мин.
const STEPS: DeviceStep[] = [
  { name: 'Белковая', temp: 52, minutes: 15, watts: 2000, additions: [], boil: false },
  { name: null, temp: 66, minutes: 60, watts: 2000, additions: [], boil: false },
  { name: null, temp: 100, minutes: 60, watts: 2500, additions: [30, 10], boil: true },
]
const SLOTS: AdditionSlot[] = [
  { minutes: 60, items: [{ minutes: 60, kind: 'hop', name: 'Magnum', amount: 30, unit: 'g' }], label: 'Magnum 30 г' },
  { minutes: 30, items: [{ minutes: 30, kind: 'sugar', name: 'Декстроза', amount: 0.5, unit: 'kg' }], label: 'Декстроза 0.5 кг' },
  { minutes: 10, items: [], label: 'Закладка' },
  { minutes: 0, items: [{ minutes: 0, kind: 'hop', name: 'Saaz', amount: 40, unit: 'g' }], label: 'Saaz 40 г' },
]

/** Снимок с программой: step — номер шага с 1, remaining — секунд до конца шага. */
function brewing(over: Partial<Snapshot> & { remaining?: number | null; counting?: boolean } = {}): Snapshot {
  const { remaining = null, counting = false, ...rest } = over
  return snapshot({
    status: 'running',
    running: true,
    deviceRecipe: { name: 'Пилс', id: 'r1', steps: STEPS },
    additions: SLOTS,
    timer: { minutes: null, remaining, counting, at: 0 },
    ...rest,
  })
}

/** nextAction со всеми производными, как их собирает стор пивоварни. */
function next(s: Snapshot | null, { heatRate = null as number | null, endedAt = null as number | null, now = 0 } = {}) {
  const phase = phaseOf(s)
  const remaining = remainingSeconds(s, 0, 0)
  const steps = stepViews(s, phase)
  return nextAction({
    s, phase, remaining, eta: heatingEta(s, phase, heatRate), steps,
    additions: additionViews(s, phase, remaining), total: programTotal(s), endedAt, now,
  })
}

describe('фаза и статус', () => {
  it('кипячение идёт', () => {
    const s = brewing({ step: 3, counting: true, remaining: 1500 })
    const phase = phaseOf(s)
    expect(phase).toMatchObject({ running: true, counting: true, heating: false, boiling: true, inRecipe: true, step: 3 })
    expect(phase.current).toBe(STEPS[2])
    expect(statusOf(s, phase)).toMatchObject({ label: 'Кипячение', tone: 'error', live: true })
  })

  it('нагрев: программа идёт, таймер стоит, подсказки нет', () => {
    const s = brewing({ step: 2, temp: 50, stepTarget: 66 })
    expect(phaseOf(s).heating).toBe(true)
    expect(statusOf(s, phaseOf(s)).label).toBe('Нагрев')
    expect(phaseOf({ ...s, alert: 'malt' }).heating).toBe(false)
  })

  it.each([
    ['нет снимка', null, 'Нет данных'],
    ['не в сети', snapshot({ online: false }), 'Не в сети'],
    ['выключена', snapshot({ power: false }), 'Ожидание'],
    ['пауза', brewing({ status: 'paused', step: 2 }), 'Пауза'],
    ['ждёт подтверждения', brewing({ step: 1, alert: 'malt' }), 'Ждёт вас'],
    ['выдержка', brewing({ step: 2, counting: true, remaining: 600 }), 'Выдержка'],
    ['включена', snapshot(), 'Включена'],
  ] as const)('%s', (_, s, label) => {
    expect(statusOf(s, phaseOf(s)).label).toBe(label)
  })

  it('пустой снимок — ничего не идёт', () => {
    expect(phaseOf(null)).toEqual({
      running: false, paused: false, counting: false, heating: false, boiling: false, inRecipe: false, step: 0, current: null,
    })
  })
})

describe('время', () => {
  it('остаток шага — с поправкой на время после снимка', () => {
    const s = brewing({ remaining: 600, counting: true })
    expect(remainingSeconds(s, 1000, 1010)).toBe(590)
    expect(remainingSeconds(s, 1000, 2000)).toBe(0)
    expect(remainingSeconds(brewing({ remaining: 600 }), 1000, 1010)).toBe(600)       // таймер стоит
    expect(remainingSeconds(brewing(), 1000, 1010)).toBeNull()
    expect(remainingSeconds(null, 0, 0)).toBeNull()
  })

  it('скорость нагрева — по точкам не ближе полутора минут', () => {
    const history: HistoryPoint[] = [[0, 50, 66], [30, 50.5, 66], [60, 51, 66], [90, 51.5, 66], [120, 52, 66]]
    expect(heatingRate(history)).toBeCloseTo(1, 6)                  // 1.5 °C за 90 с
    expect(heatingRate(history.slice(0, 3))).toBeNull()
    expect(heatingRate([])).toBeNull()
  })

  it('прогноз нагрева', () => {
    const s = brewing({ step: 2, temp: 50, stepTarget: 66 })
    const phase = phaseOf(s)
    expect(heatingEta(s, phase, 1)).toBe(960)
    expect(heatingEta(s, phase, 0.01)).toBeNull()                    // слишком медленно — не гадаем
    expect(heatingEta({ ...s, temp: 67 }, phase, 1)).toBe(0)
    expect(heatingEta(s, phaseOf(brewing({ step: 2, counting: true })), 1)).toBeNull()
  })

  it('прогресс шага: выдержка — по таймеру, нагрев — по пути к цели', () => {
    const holding = brewing({ step: 2, counting: true, remaining: 1800 })
    expect(stepProgress(holding, phaseOf(holding), 1800, null)).toBe(0.5)
    const heating = brewing({ step: 2, temp: 50, stepTarget: 66 })
    expect(stepProgress(heating, phaseOf(heating), null, 40)).toBeCloseTo(10 / 26, 6)
    expect(stepProgress(heating, phaseOf(heating), null, null)).toBeNull()
    const manual = brewing({ mode: 'manual', step: 0, manualMinutes: 10, counting: true, remaining: 150 })
    expect(stepProgress(manual, phaseOf(manual), 150, null)).toBe(0.75)
    expect(stepProgress(snapshot(), phaseOf(snapshot()), 100, null)).toBeNull()
  })

  it('программа: всего и осталось', () => {
    expect(programTotal(brewing())).toBe((15 + 60 + 60) * 60)
    const s = brewing({ step: 2, counting: true, remaining: 1800 })
    expect(programRemaining(s, phaseOf(s), 1800)).toBe(3600 + 1800)
    expect(programRemaining(snapshot(), phaseOf(snapshot()), 1800)).toBeNull()
  })
})

describe('шаги и закладки', () => {
  it('шаги: пройденные, текущий, следующие; имя по умолчанию', () => {
    const s = brewing({ step: 2 })
    const views = stepViews(s, phaseOf(s))
    expect(views.map(v => [v.name, v.state])).toEqual([['Белковая', 'done'], ['Пауза 66 °C', 'current'], ['Кипячение', 'upcoming']])
    expect(stepViews(snapshot({ deviceRecipe: { steps: STEPS } }), phaseOf(null)).every(v => v.state === 'upcoming')).toBe(true)
  })

  it('на кипячении: прошедшие, следующая, остальные', () => {
    const s = brewing({ step: 3, counting: true, remaining: 1500 })
    const views = additionViews(s, phaseOf(s), 1500)
    expect(views.map(v => [v.minutes, v.phase, v.until])).toEqual([[60, 'done', -2100], [30, 'done', -300], [10, 'next', 900], [0, 'later', 1500]])
  })

  it('пивоварня ждёт «Заложил»', () => {
    const s = brewing({ step: 3, counting: true, remaining: 1790, additionsPending: [SLOTS[1]!] })
    expect(additionViews(s, phaseOf(s), 1790).map(v => v.phase)).toEqual(['done', 'due', 'next', 'later'])
  })

  it('до кипячения времени до закладок нет, следующая — первая', () => {
    const s = brewing({ step: 1, counting: true, remaining: 600 })
    expect(additionViews(s, phaseOf(s), 600).map(v => [v.phase, v.until])).toEqual([['next', null], ['later', null], ['later', null], ['later', null]])
    const idle = snapshot({ additions: SLOTS })
    expect(additionViews(idle, phaseOf(idle), null).every(v => v.phase === 'later')).toBe(true)
  })
})

describe('nextAction', () => {
  it('нет снимка и нет связи', () => {
    expect(next(null).kind).toBe('wait')
    expect(next(snapshot({ online: false }))).toMatchObject({ kind: 'offline', tone: 'error', actions: [] })
  })

  it('подсказка пивоварни', () => {
    expect(next(brewing({ step: 1, alert: 'malt' }))).toMatchObject({
      kind: 'alert', title: 'Засыпьте солод', attention: true, actions: ['confirmAlert', 'pause'],
    })
    expect(next(brewing({ step: 2, alert: 'mashEnd' })).title).toBe('Затирание закончено')
    expect(next(brewing({ step: 2, alert: 'other' })).title).toBe('Пивоварня ждёт подтверждения')
  })

  it('пауза', () => {
    expect(next(brewing({ status: 'paused', step: 2 }))).toMatchObject({ kind: 'paused', actions: ['resume'] })
  })

  it('пора закладывать — даже после конца программы', () => {
    const due = { additionsPending: [SLOTS[1]!] }
    expect(next(brewing({ step: 3, counting: true, remaining: 1790, ...due }))).toMatchObject({
      kind: 'additionNow', title: 'Заложите: Декстроза 0.5 кг', icon: 'i-lucide-candy', attention: true, actions: ['ackAddition'], addition: 30,
    })
    expect(next(snapshot({ ...due, deviceRecipe: { steps: STEPS } })).kind).toBe('additionNow')
    expect(next(snapshot({ additionsPending: [SLOTS[2]!] })).title).toBe('Время закладки')
  })

  it('кипячение: обратный отсчёт до следующей закладки', () => {
    expect(next(brewing({ step: 3, counting: true, remaining: 1500 }))).toMatchObject({
      kind: 'addition', title: 'Закладка за 10 мин', icon: 'i-lucide-list-plus', countdown: 900, actions: ['pause'],
    })
    expect(next(brewing({ step: 3, counting: true, remaining: 3000 }))).toMatchObject({ title: 'Декстроза 0.5 кг', countdown: 1200 })
  })

  it('нагрев: с прогнозом и без', () => {
    const s = brewing({ step: 2, temp: 50, stepTarget: 66 })
    expect(next(s, { heatRate: 1 })).toMatchObject({ kind: 'heating', title: 'Нагрев до 66,0 °C', description: 'Осталось примерно 16 мин' })
    expect(next(s).description).toBe('Прогноз появится через пару минут нагрева')
    expect(next(brewing({ step: 3, temp: 90, stepTarget: 100, additions: [] })).title).toBe('Нагрев до кипения')
  })

  it('выдержка: что дальше', () => {
    expect(next(brewing({ step: 1, counting: true, remaining: 300, additions: [] }))).toMatchObject({
      kind: 'nextStep', title: 'Дальше: Пауза 66 °C', description: 'Нагрев до 66,0 °C', countdown: 300,
    })
    expect(next(brewing({ step: 2, counting: true, remaining: 300, additions: [] })).description).toBe('Нагрев до кипения')
  })

  it('последний шаг, конец и ручной режим', () => {
    expect(next(brewing({ step: 3, counting: true, remaining: 0, additions: [] })).kind).toBe('finishing')
    expect(next(brewing({ step: 3, counting: true, remaining: 60, additions: [] }))).toMatchObject({ kind: 'finish', title: 'Последний шаг' })
    expect(next(brewing({ mode: 'manual', step: 0, counting: true, remaining: 60, deviceRecipe: null, additions: [] })))
      .toMatchObject({ kind: 'finish', title: 'Ручной режим', countdown: 60 })
  })

  it('после программы: завершена, затем — готова к новому запуску', () => {
    const idle = snapshot({ deviceRecipe: { name: 'Пилс', steps: STEPS } })
    expect(next(idle, { endedAt: 1000, now: 1000 + 60 })).toMatchObject({ kind: 'ended', title: 'Программа завершена' })
    expect(next(idle, { endedAt: 1000, now: 1000 + 31 * 60 })).toMatchObject({
      kind: 'ready', title: '«Пилс»', description: dots('3 шага · 2 ч 15 мин без учёта нагрева'), actions: ['startRecipe'],
    })
  })

  it('рецепта в пивоварне нет или он не из приложения', () => {
    expect(next(snapshot())).toMatchObject({ kind: 'noRecipe', actions: ['chooseRecipe'] })
    expect(next(snapshot({ deviceRecipe: { steps: STEPS.slice(0, 1) } }))).toMatchObject({
      title: 'Рецепт из Smart Life', description: dots('1 шаг · 15 мин без учёта нагрева'),
    })
  })
})
