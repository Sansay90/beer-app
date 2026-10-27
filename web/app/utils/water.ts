// Вода рецепта: объёмы заторной и промывочной воды, соли и кислоты, профиль ионов.
// Ионы на 1 г соли в 1 л (мг/л) — из молярных масс; мел в заторе считается как 2 HCO₃⁻ на CaCO₃.
import type { Batch, Boil, Fermentable, WaterAddition, WaterAgent, WaterProfile } from '~/types'

export const IONS = ['ca', 'mg', 'na', 'cl', 'so4', 'hco3'] as const
export type Ion = typeof IONS[number]
export type Ions = Record<Ion, number>
export const ION_LABELS: Record<Ion, string> = { ca: 'Ca', mg: 'Mg', na: 'Na', cl: 'Cl', so4: 'SO₄', hco3: 'HCO₃' }

export interface WaterAgentMeta {
  label: string
  formula?: string
  unit: 'g' | 'ml'
  ions: Partial<Ions>         // мг иона на 1 г соли
  note?: string
}

export const WATER_AGENTS: Record<WaterAgent, WaterAgentMeta> = {
  cacl2: { label: 'Хлорид кальция', formula: 'CaCl₂·2H₂O', unit: 'g', ions: { ca: 272.6, cl: 482.3 } },
  cacl2_anhydrous: { label: 'Хлорид кальция безводный', formula: 'CaCl₂', unit: 'g', ions: { ca: 361.1, cl: 638.9 } },
  gypsum: { label: 'Гипс', formula: 'CaSO₄·2H₂O', unit: 'g', ions: { ca: 232.8, so4: 557.9 } },
  nacl: { label: 'Поваренная соль', formula: 'NaCl', unit: 'g', ions: { na: 393.4, cl: 606.6 } },
  nahco3: { label: 'Пищевая сода', formula: 'NaHCO₃', unit: 'g', ions: { na: 273.7, hco3: 726.3 } },
  caco3: { label: 'Мел', formula: 'CaCO₃', unit: 'g', ions: { ca: 400.4, hco3: 1219.3 }, note: 'в воде почти не растворяется — только в заторе' },
  epsom: { label: 'Английская соль', formula: 'MgSO₄·7H₂O', unit: 'g', ions: { mg: 98.6, so4: 389.7 } },
  lactic80: { label: 'Молочная кислота 80 %', unit: 'ml', ions: {} },
  lactic88: { label: 'Молочная кислота 88 %', unit: 'ml', ions: {} },
  other: { label: 'Другое', unit: 'g', ions: {} },
}

const zero = (): Ions => ({ ca: 0, mg: 0, na: 0, cl: 0, so4: 0, hco3: 0 })

type Source = { additions?: WaterAddition[]; source?: Partial<WaterProfile> }
type Litres = Pick<WaterVolumes, 'mash' | 'sparge'>

/** Сколько мг ионов даёт добавка (на весь объём). */
function addedMg(w: Source, target: 'mash' | 'sparge' | null) {
  const mg = zero()
  for (const a of w.additions ?? []) {
    if (target && (a.target ?? 'mash') !== target) continue
    for (const ion of IONS) mg[ion] += (a.amount ?? 0) * (WATER_AGENTS[a.agent].ions[ion] ?? 0)
  }
  return mg
}

function profile(w: Source, litres: number, target: 'mash' | 'sparge' | null): Ions {
  const added = addedMg(w, target)
  const out = zero()
  for (const ion of IONS) out[ion] = (w.source?.[ion] ?? 0) + added[ion] / litres
  return out
}

/** Профиль заторной, промывочной и всей воды, мг/л; null — объём неизвестен. */
export function waterProfiles(w: Source, v: Litres) {
  return {
    mash: v.mash ? profile(w, v.mash, 'mash') : null,
    sparge: v.sparge ? profile(w, v.sparge, 'sparge') : null,
    total: v.mash && v.sparge ? profile(w, v.mash + v.sparge, null) : null,
  }
}

/** Что добавка даёт своей воде: «Ca +55 · Cl +96 мг/л»; null — объём неизвестен или ионов нет. */
export function additionEffect(w: Source, v: Litres, i: number) {
  const a = w.additions?.[i]
  const litres = a ? ((a.target ?? 'mash') === 'mash' ? v.mash : v.sparge) : null
  if (!a || !litres || !a.amount) return null
  const parts = IONS.filter(ion => WATER_AGENTS[a.agent].ions[ion])
    .map(ion => `${ION_LABELS[ion]} +${Math.round((a.amount! * WATER_AGENTS[a.agent].ions[ion]!) / litres)}`)
  return parts.length ? `${parts.join(' · ')} мг/л` : null
}

/** Хлорид к сульфату: > 1 — солодовый сдвиг, < 1 — хмелевой; null — сульфата нет. */
export function chlorideSulfate(p: Ions | null) {
  return p && p.so4 > 0 ? p.cl / p.so4 : null
}

export function waterAmount(agent: WaterAgent, amount: number | null | undefined) {
  if (amount == null) return null
  return `${amount.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${WATER_AGENTS[agent].unit === 'ml' ? 'мл' : 'г'}`
}

// ── объёмы воды ──────────────────────────────────────────────────────────────
/** Сколько воды удерживает отжатая дробина, л/кг: у корзинных систем 0,7–1, точнее не нужно — промывку всё равно
 *  останавливают по плотности, и расчётный объём промывочной воды — это запас, а не норма. */
export const GRAIN_ABSORPTION = 0.8

export interface WaterVolumes {
  mash: number | null        // л: гидромодуль × засыпь
  sparge: number | null      // л: остальное до объёма перед кипячением, не меньше нуля
  preBoil: number | null     // л перед кипячением
  absorbed: number           // л удержит дробина
  total: number | null       // л всей воды
  excess: boolean            // заторной воды больше, чем нужно на всю варку
}

const tenth = (v: number) => Math.round(v * 10) / 10

type VolumeSource = {
  batch?: Pick<Batch, 'volume'>
  boil?: Pick<Boil, 'minutes'> | null
  fermentables?: Pick<Fermentable, 'amount' | 'use'>[]
  water?: { ratio?: number | null }
}

/** Вода на варку: вся = после кипячения + испарение × время кипячения + удержание дробиной;
 *  заторная — по гидромодулю рецепта, промывочная — остальное. Испарение — из профиля оборудования. */
export function waterVolumes(r: VolumeSource, evaporation: number | null | undefined): WaterVolumes {
  const grain = (r.fermentables ?? []).filter(f => (f.use ?? 'mash') === 'mash').reduce((a, f) => a + (f.amount ?? 0), 0)
  const ratio = r.water?.ratio
  const mash = ratio && grain ? ratio * grain : null
  const preBoil = r.batch?.volume && evaporation != null ? r.batch.volume + evaporation * ((r.boil?.minutes ?? 0) / 60) : null
  const absorbed = grain * GRAIN_ABSORPTION
  const total = preBoil != null && grain ? preBoil + absorbed : null
  const sparge = total != null && mash != null ? Math.max(0, total - mash) : null
  return {
    mash: mash == null ? null : tenth(mash),
    sparge: sparge == null ? null : tenth(sparge),
    preBoil: preBoil == null ? null : tenth(preBoil),
    absorbed: tenth(absorbed),
    total: total == null ? null : tenth(total),
    excess: total != null && mash != null && mash > total,
  }
}
