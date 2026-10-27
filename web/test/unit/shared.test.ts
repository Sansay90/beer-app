// Общие примеры сервиса и интерфейса (shared/): расчёт показателей и программа пивоварни дают то же, что
// у сервиса (service/tests/test_shared.py проверяет себя по тем же файлам).
import { describe, expect, it } from 'vitest'
import calcCases from '../../../shared/calc-cases.json'
import programCases from '../../../shared/program-cases.json'
import type { Recipe } from '~/types'
import { calcRecipe } from '~/utils/calc'
import { boilGroups, deviceTimers, programOf } from '~/utils/recipe'

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
