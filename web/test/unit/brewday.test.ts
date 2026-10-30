// Варочный день партии: шаг и фаза с сервиса, живой шаг пивоварни поверх, таймер, что приготовить на шаге.
import { describe, expect, it } from 'vitest'
import type { BrewDayStep, BrewEntry, Recipe } from '~/types'
import type { Phase } from '~/utils/brew'
import { phaseOf } from '~/utils/brew'
import { additionWhen, brewDay, breweryStep, lastMeasures, stepDetails, stepLine, stepRemaining } from '~/utils/brewday'
import { dots, snapshot } from './fixtures'

const STEPS: BrewDayStep[] = [
  { index: 0, key: 'prepare-0', kind: 'prepare', name: 'Подготовка', measures: [], additions: [], at: 1000 },
  { index: 1, key: 'heat-1', kind: 'heat', name: 'Нагрев', temp: 66, measures: [], additions: [] },
  { index: 2, key: 'mash_in-2', kind: 'mash_in', name: 'Засыпать солод', measures: ['ph', 'mash_temp'], additions: [] },
  { index: 3, key: 'rest-3', kind: 'rest', name: 'Осахаривание', temp: 66, minutes: 60, measures: [], additions: [] },
  { index: 4, key: 'rest-4', kind: 'rest', name: 'Мэш-аут', temp: 78, minutes: 10, measures: [], additions: [] },
  { index: 5, key: 'sparge-5', kind: 'sparge', name: 'Промывка', measures: ['first_wort'], additions: [] },
  { index: 6, key: 'boil-6', kind: 'boil', name: 'Кипячение', minutes: 60, measures: [], additions: [{ minutes: 60, label: 'Magnum 26 г' }, { minutes: 10, label: 'Centennial 15 г' }] },
  { index: 7, key: 'chill-7', kind: 'chill', name: 'Охлаждение', temp: 18, measures: ['og', 'fermenter_volume'], additions: [] },
  { index: 8, key: 'pitch-8', kind: 'pitch', name: 'Задать дрожжи', measures: [], additions: [] },
]
const at = (i: number, t: number) => STEPS.map(s => (s.index === i ? { ...s, at: t } : s))
const entry = (kind: BrewEntry['kind'], t: number, value: number | null = null): BrewEntry => ({ id: `${kind}-${t}`, at: t, kind, value, text: null })
const brew = (over: Partial<Parameters<typeof brewDay>[0]> = {}): Parameters<typeof brewDay>[0] => ({
  id: 'b1', brewDay: STEPS, currentStep: 0, phase: 'brewday', snapshot: null, ...over,
})
const idle: Phase = phaseOf(null)

describe('шаг с сервиса', () => {
  it('день идёт — текущий шаг и до него сделано', () => {
    const v = brewDay(brew({ currentStep: 3, brewDay: at(3, 1200) }), null, idle)
    expect(v.current).toBe(3)
    expect(v.active).toBe(true)
    expect(v.steps.map(s => s.state).slice(2, 5)).toEqual(['done', 'now', 'next'])
    expect(v.steps[3]!.ends).toBe(1200 + 60 * 60)
    expect(stepRemaining(v.steps[3]!, 1200 + 40 * 60)).toBe(20 * 60)
    expect(stepRemaining(v.steps[3]!, 1200 + 75 * 60)).toBe(-15 * 60)           // время вышло — шаг всё ещё текущий
    expect(stepRemaining(v.steps[0]!, 1500)).toBeNull()                           // без таймера
  })

  it('варочный день позади — все шаги сделаны, «Сейчас» не нужно', () => {
    for (const phase of ['fermenting', 'packaged'] as const) {
      const v = brewDay(brew({ phase, currentStep: 4 }), null, idle)
      expect(v.active).toBe(false)
      expect(v.steps.every(s => s.state === 'done')).toBe(true)
    }
  })
})

describe('шаг по программе пивоварни', () => {
  const steps = [{ temp: 66, minutes: 60, watts: 2500, additions: [], boil: false }, { temp: 78, minutes: 10, watts: 2500, additions: [], boil: false }, { temp: 100, minutes: 60, watts: 2500, additions: [60], boil: true }]
  const snap = (over: Parameters<typeof snapshot>[0] = {}) => snapshot({ brewId: 'b1', deviceRecipe: { steps }, ...over })
  const run = (over: Partial<Phase>): Phase => ({ ...idle, running: true, inRecipe: true, ...over })

  it('нагрев до первой паузы — «Нагрев», пауза с отсчётом — пауза, кипячение — кипячение', () => {
    expect(breweryStep(STEPS, snap(), run({ step: 1, heating: true }))).toBe(1)
    expect(breweryStep(STEPS, snap(), run({ step: 1, counting: true, current: steps[0]! }))).toBe(3)
    expect(breweryStep(STEPS, snap(), run({ step: 2, counting: true }))).toBe(4)
    expect(breweryStep(STEPS, snap(), run({ step: 3, counting: true, current: steps[2]! }))).toBe(6)
  })

  it('подсказки пивоварни — засыпь и промывка', () => {
    expect(breweryStep(STEPS, snap({ alert: 'malt' }), run({ step: 1 }))).toBe(2)
    expect(breweryStep(STEPS, snap({ alert: 'mashEnd' }), run({ step: 2 }))).toBe(5)
  })

  it('пивоварня варит эту партию — её живой шаг поверх шага с сервиса', () => {
    const v = brewDay(brew({ currentStep: 3 }), snap(), run({ step: 2, counting: true }))
    expect(v.byBrewery).toBe(true)
    expect(v.current).toBe(4)
  })

  it('чужая варка пивоварни или программа не идёт — шаг с сервиса', () => {
    expect(brewDay(brew({ currentStep: 2 }), snap({ brewId: 'other' }), run({ step: 2, counting: true })).current).toBe(2)
    const stopped = brewDay(brew({ currentStep: 7 }), snap(), idle)
    expect(stopped.current).toBe(7)
  })
})

describe('что приготовить', () => {
  const recipe = {
    name: 'Тест', batch: { volume: 20, efficiency: 75, evaporation: 3 }, boil: { minutes: 60, watts: 2500 },
    fermentables: [{ name: 'Pilsner', amount: 4, use: 'mash' }, { name: 'Сахар', amount: 0.5, use: 'boil' }],
    water: { ratio: 3, additions: [{ agent: 'cacl2', amount: 2.4 }, { agent: 'lactic80', amount: 1.5, target: 'sparge' }] },
    yeasts: [{ name: 'US-05', amount: 2, unit: 'pkg' }],
  } as unknown as Recipe

  it('подготовка — вода с солями по воде, засыпь только затираемая, дрожжи', () => {
    expect(stepDetails(STEPS[0]!, recipe)).toEqual([
      'Затор: 12 л — хлорид кальция 2,4 г',
      'Промывка: 14,2 л — молочная кислота 80 % 1,5 мл',
      'Засыпь 4 кг: Pilsner 4 кг',
      'Дрожжи: US-05 2 пак.',
    ])
  })

  it('в затор — с солями и хмель, и прочее «в затор»; хмель на первое сусло — на промывке', () => {
    const r = { ...recipe,
      hops: [{ name: 'Hallertau', amount: 20, use: 'first_wort' }, { name: 'Magnum', amount: 10, use: 'mash' }, { name: 'Citra', amount: 30, use: 'boil' }],
      miscs: [{ kind: 'fining', name: 'Brewtan B', amount: 0.5, unit: 'g', use: 'mash' }, { kind: 'fining', name: 'Мох', amount: 5, unit: 'g', use: 'boil' }],
    } as unknown as Recipe
    expect(stepDetails(STEPS[0]!, r)[0]).toBe('Затор: 12 л — хлорид кальция 2,4 г, Magnum 10 г, Brewtan B 0,5 г')
    expect(stepDetails(STEPS[5]!, r)).toEqual(['промывочная вода 14,2 л', 'до кипячения 23 л', 'на первое сусло: Hallertau 20 г'])
  })

  it('промывка — объёмы по испарению оборудования из рецепта партии; на прочих шагах — ничего', () => {
    expect(stepDetails(STEPS[5]!, recipe)).toEqual(['промывочная вода 14,2 л', 'до кипячения 23 л'])
    expect(stepDetails(STEPS[3]!, recipe)).toEqual([])
    expect(stepDetails(STEPS[0]!, null)).toEqual([])
  })
})

describe('подписи шагов', () => {
  it('температура и время шага, закладки по минутам кипячения', () => {
    expect(stepLine(STEPS[3]!)).toBe(dots('66,0 °C · 1 ч'))
    expect(stepLine(STEPS[5]!)).toBe('')
    expect([60, 10, 0].map(m => additionWhen(m, 60))).toEqual(['старт', 'за 10 мин', 'конец'])
  })
})

describe('последние замеры', () => {
  it('по каждому виду — самый поздний', () => {
    const m = lastMeasures([entry('ph', 100, 5.3), entry('ph', 200, 5.4), entry('og', 300, 1.06), entry('note', 400)])
    expect(m.get('ph')?.value).toBe(5.4)
    expect(m.get('og')?.value).toBe(1.06)
    expect(m.has('note')).toBe(false)
  })
})
