// Рецепт под другое оборудование: то же пиво — OG, горечь, цвет, крепость — на другом объёме и при другой
// эффективности. Сервис считает так же, когда заводит партию (service/app/recipes/scale.py): правила одни, менять
// вместе; общие примеры обеих реализаций — shared/scale-cases.json.
//
// Объём меняет всё, что кладут в сусло, пропорционально; эффективность — только то, что затирается (сахар и экстракт
// растворяются целиком). Хмель — по объёму: при той же OG использование то же, значит та же горечь; сухое охмеление
// и вирпул — те же граммы на литр. Соли в затор — по засыпи (заторная вода — гидромодуль × засыпь), в промывку —
// по объёму. Дрожжи: пачки — по объёму с округлением вверх, граммы — пропорционально. Паузы, кипячение, гидромодуль,
// профиль воды и брожение — без изменений. Показатели пересчитываются по новым количествам (calc.ts).
// Нет объёма у рецепта или у оборудования — по объёму не пересчитывается, только по эффективности.
import type { Equipment, Recipe } from '~/types'
import { calcRecipe, DEFAULT_EFFICIENCY, mashed } from '~/utils/calc'
import { fmtNumber } from '~/utils/format'
import { totalKg } from '~/utils/recipe'
import { waterVolumes } from '~/utils/water'

const WHOLE = new Set(['pkg', 'pcs'])   // штучное: пачки дрожжей, таблетки — целое вверх

/** Половина — вверх (Math.round); сервис округляет так же. */
const rounded = (x: number, digits: number) => {
  const k = 10 ** digits
  return Math.floor(x * k + 0.5) / k
}

/** Целое вверх с допуском на плавающую точку: 2,0000000001 — это 2. */
const wholeUp = (x: number) => Math.ceil(x - 1e-9)

export interface ScaleFactors {
  kv: number                 // множитель для того, что кладут в сусло: по объёму
  kg: number                 // множитель для того, что затирается: объём и эффективность
  volume: number | null      // л после кипячения у партии
  efficiency: number | null  // % у партии; ни у рецепта, ни у оборудования — пусто
}

type Target = { volume?: number | null; efficiency?: number | null }

export function scaleFactors(r: Pick<Recipe, 'batch'>, to: Target): ScaleFactors {
  const v1 = r.batch?.volume ?? null
  const e1 = r.batch?.efficiency ?? null
  const volume = to.volume || v1
  const efficiency = to.efficiency || e1
  const kv = v1 && volume ? volume / v1 : 1
  return { kv, kg: kv * (e1 || DEFAULT_EFFICIENCY) / (efficiency || DEFAULT_EFFICIENCY), volume, efficiency }
}

const scaled = (amount: number | null | undefined, k: number, digits: number) => (amount == null ? amount : rounded(amount * k, digits))
const whole = (amount: number | null | undefined, k: number) => (amount == null ? amount : amount > 0 ? wholeUp(amount * k) : 0)

/** Копия рецепта под объём (л после кипячения) и эффективность оборудования. Те же объём и эффективность —
 *  копия без изменений. */
export function scaleRecipe(r: Recipe, to: Target): Recipe {
  const { kv, kg, volume, efficiency } = scaleFactors(r, to)
  const out: Recipe = JSON.parse(JSON.stringify(r))   // рецепт — JSON; structuredClone не берёт реактивные прокси
  out.batch = { ...r.batch, volume, efficiency }
  if (kv !== 1 || kg !== 1) {
    for (const f of out.fermentables ?? []) f.amount = scaled(f.amount, mashed(f) ? kg : kv, 3)
    for (const h of out.hops ?? []) h.amount = scaled(h.amount, kv, 1)
    for (const m of out.miscs ?? []) {
      const unit = m.unit ?? 'g'
      m.amount = WHOLE.has(unit) ? whole(m.amount, kv) : scaled(m.amount, kv, unit === 'kg' ? 3 : 1)
    }
    for (const y of out.yeasts ?? []) y.amount = WHOLE.has(y.unit ?? 'pkg') ? whole(y.amount, kv) : scaled(y.amount, kv, 1)
    for (const a of out.water?.additions ?? []) a.amount = scaled(a.amount, (a.target ?? 'mash') === 'mash' ? kg : kv, 2)
  }
  const c = calcRecipe(out)
  out.targets = { og: c.og, fg: c.fg, ibu: c.ibu, ebc: c.ebc, abv: c.abv }
  return out
}

/** Сколько места занимает засыпь в воде, л/кг: при полном затирании в котле вода и дробина вместе. */
export const GRAIN_DISPLACEMENT = 0.67

/** Чем варка не влезает в котёл: затор (вода и засыпь) или объём перед кипячением больше котла.
 *  Пусто — влезает или объём котла не задан. */
export function kettleWarnings(r: Recipe, e: Pick<Equipment, 'kettle' | 'evaporation'>): string[] {
  if (!e.kettle) return []
  const v = waterVolumes(r, e.evaporation)
  const grain = totalKg((r.fermentables ?? []).filter(f => mashed(f)))
  const mash = v.mash != null ? v.mash + grain * GRAIN_DISPLACEMENT : null
  const out: string[] = []
  const l = (x: number) => fmtNumber(x, 1, ' л')
  if (mash != null && mash > e.kettle) out.push(`Затор — вода и засыпь — займёт ${l(mash)}, а котёл ${l(e.kettle)}.`)
  if (v.preBoil != null && v.preBoil > e.kettle) out.push(`Перед кипячением будет ${l(v.preBoil)}, а котёл ${l(e.kettle)}.`)
  return out
}
