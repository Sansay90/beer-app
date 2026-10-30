// Общие примеры сервиса и интерфейса (shared/): расчёт показателей и программа пивоварни дают то же, что
// у сервиса (service/tests/test_shared.py проверяет себя по тем же файлам).
import { describe, expect, it } from 'vitest'
import calcCases from '../../../shared/calc-cases.json'
import programCases from '../../../shared/program-cases.json'
import scaleCases from '../../../shared/scale-cases.json'
import fermentCases from '../../../shared/ferment-cases.json'
import type { Recipe } from '~/types'
import { fermentAdvice, fermentCalm, fermentPlan } from '~/utils/brewlog'
import { calcRecipe } from '~/utils/calc'
import { boilGroups, deviceTimers, programOf } from '~/utils/recipe'
import { scaleRecipe } from '~/utils/scale'

interface Case<E> { name: string; recipe: unknown; expected: E }

const cases = <E>(data: unknown) => (data as Case<E>[]).map(c => [c.name, c] as const)

describe('показатели — как у сервиса (shared/calc-cases.json)', () => {
  it.each(cases<Record<string, number | boolean | null>>(calcCases))('%s', (_, c) => {
    const got = calcRecipe(c.recipe as Recipe) as unknown as Record<string, number | boolean | null>
    expect(Object.keys(got).sort()).toEqual(Object.keys(c.expected).sort())
    for (const [key, value] of Object.entries(c.expected)) {
      if (typeof value === 'number') expect(got[key], key).toBeCloseTo(value, 9)
      else expect(got[key], key).toBe(value)
    }
  })
})

interface ProgramExpected {
  steps: { temp: number; minutes: number; watts: number; boil: boolean }[]
  timers: number[]
  slots: { minutes: number; items: unknown[] }[]
}

describe('программа пивоварни — как у сервиса (shared/program-cases.json)', () => {
  it.each(cases<ProgramExpected>(programCases))('%s', (_, c) => {
    const r = c.recipe as Recipe
    // температура кипячения на экране — метка пивоварни, у сервиса — 100 °C: сравниваются паузы
    expect(programOf(r).map(s => ({ minutes: s.minutes, watts: s.watts, boil: s.boil, ...(s.boil ? {} : { temp: s.temp }) })))
      .toEqual(c.expected.steps.map(s => ({ minutes: s.minutes, watts: s.watts, boil: s.boil, ...(s.boil ? {} : { temp: s.temp }) })))
    expect(deviceTimers(r)).toEqual(c.expected.timers)
    // в JSON у сервиса нет undefined: отсутствующее количество (у оборудования) приходит как null
    const groups = boilGroups(r).map(g => ({ ...g, items: g.items.map(i => ({ ...i, amount: i.amount ?? null })) }))
    expect(groups).toEqual(c.expected.slots)
  })
})

/** Глубокое сравнение: числа — приблизительно, остальное — точно; у сервиса в JSON нет undefined — его нет и здесь. */
function same(got: unknown, expected: unknown, path = '') {
  if (Array.isArray(expected)) {
    expect(Array.isArray(got), path).toBe(true)
    expect((got as unknown[]).length, path).toBe(expected.length)
    expected.forEach((v, i) => same((got as unknown[])[i], v, `${path}[${i}]`))
  } else if (expected && typeof expected === 'object') {
    const g = got as Record<string, unknown>
    expect(Object.keys(g).sort(), path).toEqual(Object.keys(expected).sort())
    for (const [k, v] of Object.entries(expected)) same(g[k], v, `${path}.${k}`)
  } else if (typeof expected === 'number' && !Number.isInteger(expected)) {
    expect(got, path).toBeCloseTo(expected, 9)
  } else {
    expect(got, path).toBe(expected)
  }
}

describe('пересчёт под оборудование — как у сервиса (shared/scale-cases.json)', () => {
  it.each(cases<Recipe>(scaleCases))('%s', (_, c) => {
    const to = (c as unknown as { to: { volume: number | null; efficiency: number | null } }).to
    same(scaleRecipe(c.recipe as Recipe, to), c.expected)
  })
})

interface FermentCase {
  name: string
  plan: Parameters<typeof fermentPlan>[0]
  start: number
  now: number
  entries: { kind: 'stage' | 'og' | 'gravity'; at: number; value: number | null }[]
  expected: unknown
}

describe('расписание брожения — как у сервиса (shared/ferment-cases.json)', () => {
  it.each((fermentCases as unknown as FermentCase[]).map(c => [c.name, c] as const))('%s', (_, c) => {
    const p = fermentPlan(c.plan, c.start, c.now, null, c.entries)
    const advice = fermentAdvice(p, c.plan, c.entries)
    const calm = fermentCalm(p, c.plan, c.entries)
    same({
      current: p.current,
      stages: p.stages.map(s => ({ from: s.from, to: s.to, target: s.target })),
      advice: advice && { stage: advice.stage, why: advice.why, value: advice.value, at: advice.at },
      calm: calm && { value: calm.value, at: calm.at, stuck: calm.stuck },
    }, c.expected)
  })
})
