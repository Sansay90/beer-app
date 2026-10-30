// Показатели рецепта по ингредиентам и подгонка ингредиентов под цель.
// OG — экстракт засыпи с учётом эффективности, FG — по сбраживанию дрожжей, IBU — Tinseth, цвет — Morey.
// Сахар сбраживается целиком, где бы его ни добавили; добавленное на брожении в OG не входит, а в крепость — входит.
// Объём — сусло после кипячения, эффективность — к нему же. Упрощения: выход экстракта — средний по типу
// и цвету сырья (справочника пока нет); IBU — по OG, вирпул и сухое охмеление горечи не дают (как у Tinseth).
import type { Fermentable, Hop, Recipe } from '~/types'
import type { RecipeDraft } from '~/types/recipe'
import { abvOf, platoFromSg, sgFromPlato } from '~/utils/beer'

/** Выход экстракта, % массы — средние значения по типу сырья; у солода зависит от цвета (yieldOf). */
export const YIELD: Record<NonNullable<Fermentable['kind']>, number> = { grain: 80, adjunct: 75, sugar: 100, extract: 95 }

/** Солод: светлый ~80 %, карамельный и специальный ~75 %, жжёный ~60 % (PPG 1.037 / 1.034 / 1.028). */
export function yieldOf(f: Fermentable) {
  const kind = f.kind ?? 'grain'
  if (kind !== 'grain') return YIELD[kind]
  const ebc = f.ebc ?? 0
  return ebc >= 400 ? 60 : ebc >= 50 ? 75 : 80
}
export const DEFAULT_EFFICIENCY = 75
export const DEFAULT_ATTENUATION = 75

type Source = Pick<Recipe, 'batch' | 'fermentables' | 'hops' | 'yeasts' | 'boil'>

export interface RecipeCalc {
  og: number | null
  fg: number | null
  abv: number | null
  ibu: number | null
  ebc: number | null
  attenuation: number            // какой взяли: из дрожжей или по умолчанию
  defaultAttenuation: boolean
}

// ── экстракт и плотность ─────────────────────────────────────────────────────
/** Сырьё, которое попадает в сусло до брожения. */
const inWort = (f: Fermentable) => f.use !== 'fermentation'
/** Сахар сбраживается целиком; остальное — на степень сбраживания дрожжей. */
const fullyFermentable = (f: Fermentable) => f.kind === 'sugar'
/** Затирается — тогда работает эффективность; сахар и экстракт растворяются целиком. */
export const mashed = (f: Fermentable) => (f.use ?? 'mash') === 'mash' && (f.kind ?? 'grain') !== 'sugar' && f.kind !== 'extract'

function efficiencyOf(r: Source) {
  return r.batch?.efficiency ?? DEFAULT_EFFICIENCY
}

/** Экстракт, кг, который строка засыпи отдаст суслу. */
export function extractOf(f: Fermentable, efficiency: number) {
  const share = (yieldOf(f) / 100) * (mashed(f) ? efficiency / 100 : 1)
  return (f.amount ?? 0) * share
}

/** Плотность (SG) сусла объёмом litres, в котором kg экстракта. */
export function sgFromExtract(kg: number, litres: number) {
  let p = (kg / litres) * 100
  for (let i = 0; i < 8; i++) p = (kg * 100) / (litres * sgFromPlato(p))
  return sgFromPlato(p)
}

/** Сколько экстракта, кг, нужно на плотность sg в litres сусла. */
export function extractForSg(sg: number, litres: number) {
  return (litres * sg * platoFromSg(sg)) / 100
}

// ── горечь и цвет ────────────────────────────────────────────────────────────
/** Минуты кипячения, которые даёт горечь: закладка на кипячении или в первое сусло. */
function boilTime(h: Hop, boilMinutes: number | undefined) {
  if (h.use === 'first_wort') return boilMinutes ?? 0
  if ((h.use ?? 'boil') === 'boil') return h.minutes ?? 0
  return 0
}

function hopIbu(h: Hop, og: number, litres: number, boilMinutes: number | undefined) {
  const t = boilTime(h, boilMinutes)
  if (!t || !h.alpha || !h.amount) return 0
  const utilisation = 1.65 * 0.000125 ** (og - 1) * ((1 - Math.exp(-0.04 * t)) / 4.15)
  return utilisation * (h.alpha / 100) * h.amount * 1000 / litres
}

const LB_PER_KG = 2.20462
const L_PER_GAL = 3.78541

/** Цвет солода EBC → °L для Morey: EBC → SRM (÷ 1.97), SRM → °L = (SRM + 0.76) / 1.3546.
 *  Брать EBC ÷ 1.97 за °L нельзя — °L и SRM расходятся, у тёмных солодов на треть. */
function lovibond(ebc: number) {
  return (ebc / 1.97 + 0.76) / 1.3546
}

/** MCU Morey: °L × фунты / галлоны. */
function mcuOf(f: Fermentable, litres: number) {
  return f.ebc && f.amount ? (f.amount * LB_PER_KG * lovibond(f.ebc)) / (litres / L_PER_GAL) : 0
}

function ebcFromMcu(mcu: number) {
  return 1.4922 * mcu ** 0.6859 * 1.97
}

// ── расчёт ───────────────────────────────────────────────────────────────────
/** Экстракт, кг, строк засыпи, которые отбирает keep. */
function extractWhere(r: Source, keep: (f: Fermentable) => boolean) {
  return (r.fermentables ?? []).filter(keep).reduce((a, f) => a + extractOf(f, efficiencyOf(r)), 0)
}

/** Плотность от того, что сбраживается на степень дрожжей: всё, кроме сахара. От неё считается FG. */
function attenuableSg(r: Source, litres: number) {
  return sgFromExtract(extractWhere(r, f => !fullyFermentable(f)), litres)
}

export function calcRecipe(r: Source): RecipeCalc {
  const litres = r.batch?.volume ?? null
  const yeast = (r.yeasts ?? []).find(y => y.attenuation != null)
  const attenuation = yeast?.attenuation ?? DEFAULT_ATTENUATION
  const out: RecipeCalc = { og: null, fg: null, abv: null, ibu: null, ebc: null, attenuation, defaultAttenuation: !yeast }
  if (!litres) return out

  const fermentables = r.fermentables ?? []
  const wort = extractWhere(r, inWort)
  if (wort > 0) {
    out.og = sgFromExtract(wort, litres)
    out.fg = 1 + (attenuableSg(r, litres) - 1) * (1 - attenuation / 100)
    // крепость — со всем сбраживаемым, и с сахаром, добавленным на брожении
    out.abv = abvOf(sgFromExtract(extractWhere(r, () => true), litres), out.fg)
  }
  const hops = r.hops ?? []
  if (hops.length) out.ibu = hops.reduce((a, h) => a + hopIbu(h, out.og ?? 1.05, litres, r.boil?.minutes), 0)
  const mcu = fermentables.reduce((a, f) => a + mcuOf(f, litres), 0)
  if (mcu > 0) out.ebc = ebcFromMcu(mcu)
  return out
}

// ── подгонка под цель (ползунки рамок стиля) ─────────────────────────────────
// Подгонка считается от снимка ингредиентов на начало перетаскивания — округление не копится.
export interface FitBase {
  fermentables: (number | null)[]
  hops: (number | null)[]
}

export function fitBase(d: RecipeDraft): FitBase {
  return { fermentables: d.fermentables.map(f => f.amount), hops: d.hops.map(h => h.amount) }
}

const round = (v: number, step: number) => Math.round(v / step) * step

/** Какие показатели можно подогнать: есть объём и то, что двигать. */
export function adjustable(d: RecipeDraft) {
  const litres = d.batch.volume
  const calc = calcRecipe(d)
  const bittering = bitteringHops(d, fitBase(d))
  return {
    og: !!litres && d.fermentables.some(f => inWort(f) && (f.amount ?? 0) > 0),
    fg: calc.og != null && d.yeasts.length > 0,
    ibu: !!litres && bittering.length > 0,
    ebc: !!litres && darkest(d) != null,
  }
}

/** OG: вся засыпь пропорционально, доли сохраняются. */
export function fitOg(d: RecipeDraft, base: FitBase, sg: number) {
  const litres = d.batch.volume
  if (!litres) return
  const baseExtract = d.fermentables.reduce((a, f, i) => a + (inWort(f) ? extractOf({ ...f, amount: base.fermentables[i] }, efficiencyOf(d)) : 0), 0)
  if (baseExtract <= 0) return
  const k = extractForSg(sg, litres) / baseExtract
  d.fermentables.forEach((f, i) => {
    const kg = base.fermentables[i]
    if (inWort(f) && kg != null) f.amount = round(kg * k, 0.01)
  })
}

/** Горькая закладка — самая ранняя на кипячении (с альфой и массой); их может быть несколько на одной минуте. */
function bitteringHops(d: RecipeDraft, base: FitBase) {
  const timed = d.hops.map((h, i) => ({ i, t: boilTime(h, d.boil?.minutes) }))
    .filter(({ i, t }) => t > 0 && d.hops[i]!.alpha && base.hops[i])
  const longest = Math.max(0, ...timed.map(x => x.t))
  return timed.filter(x => x.t === longest).map(x => x.i)
}

/** IBU: меняется только горькая закладка, поздний хмель не трогаем. */
export function fitIbu(d: RecipeDraft, base: FitBase, ibu: number) {
  const litres = d.batch.volume
  if (!litres) return
  const og = calcRecipe(d).og ?? 1.05
  const bitter = new Set(bitteringHops(d, base))
  const at = (i: number) => hopIbu({ ...d.hops[i]!, amount: base.hops[i] }, og, litres, d.boil?.minutes)
  const bitterIbu = [...bitter].reduce((a, i) => a + at(i), 0)
  if (bitterIbu <= 0) return
  const rest = d.hops.reduce((a, _, i) => a + (bitter.has(i) ? 0 : at(i)), 0)
  const k = Math.max(0, ibu - rest) / bitterIbu
  for (const i of bitter) d.hops[i]!.amount = round(base.hops[i]! * k, 0.1)
}

/** FG: степень сбраживания дрожжей (сахар сбраживается целиком и в ней не участвует). */
export function fitFg(d: RecipeDraft, sg: number) {
  const litres = d.batch.volume
  const yeast = d.yeasts.find(y => y.attenuation != null) ?? d.yeasts[0]
  if (!litres || !yeast || !calcRecipe(d).og) return
  const attenuable = attenuableSg(d, litres)
  if (attenuable <= 1) return
  yeast.attenuation = Math.min(100, Math.max(0, Math.round(((attenuable - sg) / (attenuable - 1)) * 100)))
}

/** Самый тёмный солод — им подгоняется цвет. */
function darkest(d: RecipeDraft) {
  let best: number | null = null
  d.fermentables.forEach((f, i) => {
    if ((f.ebc ?? 0) > 0 && (best == null || f.ebc! > d.fermentables[best]!.ebc!)) best = i
  })
  return best
}

/** Цвет: масса самого тёмного солода, остальная засыпь как есть. */
export function fitEbc(d: RecipeDraft, base: FitBase, ebc: number) {
  const litres = d.batch.volume
  const i = darkest(d)
  if (!litres || i == null) return
  const others = d.fermentables.reduce((a, f, j) => a + (j === i ? 0 : mcuOf({ ...f, amount: base.fermentables[j] }, litres)), 0)
  const need = (ebc / 1.97 / 1.4922) ** (1 / 0.6859)
  const f = d.fermentables[i]!
  const kg = ((need - others) * (litres / L_PER_GAL)) / (LB_PER_KG * lovibond(f.ebc!))
  f.amount = Math.max(0, round(kg, 0.01))
}
