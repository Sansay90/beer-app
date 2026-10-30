// Заготовки для тестов: форма рецепта, ограничения пивоварни и снимок сервиса с разумными значениями.
import type { Limits, Snapshot } from '~/types'
import type { FermentableRow, HopRow, RecipeDraft } from '~/types/recipe'
import { SEP } from '~/utils/format'
import { blankWater, newFermentable, newHop } from '~/utils/recipe'

/** Ограничения по умолчанию, как у сервиса без пивоварни, но с известным потолком мощности. */
export const LIMITS: Limits = {
  maxSteps: 9, maxAdditions: 9, minTemp: 20, maxTemp: 100, boilTemp: 100.1, minWatts: 100, maxWatts: 2500, wattsStep: 100,
}

export function draft(over: Partial<RecipeDraft> = {}): RecipeDraft {
  return {
    name: 'Тест',
    style: null,
    batch: { volume: 23, efficiency: 75 },
    fermentables: [],
    hops: [],
    miscs: [],
    yeasts: [],
    water: blankWater(),
    mash: [],
    boil: { minutes: 60, watts: 2000 },
    fermentation: [],
    notes: '',
    ...over,
  }
}

export const malt = (amount: number, ebc: number, over: Partial<FermentableRow> = {}): FermentableRow =>
  ({ ...newFermentable(), name: 'Солод', amount, ebc, ...over })

export const hop = (amount: number, alpha: number, minutes: number | null, over: Partial<HopRow> = {}): HopRow =>
  ({ ...newHop(minutes), name: 'Хмель', amount, alpha, ...over })

export function snapshot(over: Partial<Snapshot> = {}): Snapshot {
  return {
    online: true,
    power: true,
    running: false,
    status: 'idle',
    mode: 'recipe',
    temp: 20,
    pump: false,
    step: 0,
    stepTarget: null,
    timer: { minutes: null, remaining: null, counting: false, at: 0 },
    alert: null,
    error: 0,
    settings: {},
    deviceRecipe: null,
    additions: [],
    additionsPending: [],
    energy: { wh: 0, watts: 0 },
    ...over,
  }
}

/** Ожидаемая строка с разделителем: в тексте теста — « · », в интерфейсе — SEP (точка с широкими пробелами). */
export const dots = (text: string) => text.replaceAll(' · ', SEP)
