// Журнал варки: виды записей, их единицы и показ. Значения хранятся как у сервиса (service/app/brewery/logbook.py):
// плотность — SG, pH, объём — л, температура — °C; плотность вводится и показывается в единицах пивовара.
import type { BrewEntry, BrewEvent, BrewPlan, BrewSummary } from '~/types'
import type { GravityUnit } from '~/utils/beer'
import { fmtGravity, gravityIn, sgFromPlato } from '~/utils/beer'

export type EntryKind = BrewEntry['kind']
type Unit = 'sg' | 'ph' | 'l' | 'c'
type Group = 'Варочный день' | 'Брожение и розлив' | 'Заметка'

// short — короткая подпись (поле на шаге, журнал); transition — переход к этапу или шагу: ставится кнопками,
// не из общего выбора, номер у записи не меняется
export interface EntryKindView { label: string; short?: string; icon: string; unit?: Unit; group: Group; transition?: true }

export const ENTRY_KINDS: Record<EntryKind, EntryKindView> = {
  ph: { label: 'pH затора', icon: 'i-lucide-flask-conical', unit: 'ph', group: 'Варочный день' },
  mash_temp: { label: 'Температура затора', icon: 'i-lucide-thermometer', unit: 'c', group: 'Варочный день' },
  first_wort: { label: 'Плотность первого сусла', short: 'Плотность до промывки', icon: 'i-lucide-droplet', unit: 'sg', group: 'Варочный день' },
  preboil_volume: { label: 'Объём до кипячения', short: 'Объём после промывки', icon: 'i-lucide-beaker', unit: 'l', group: 'Варочный день' },
  preboil_gravity: { label: 'Плотность до кипячения', short: 'Плотность после промывки', icon: 'i-lucide-droplet', unit: 'sg', group: 'Варочный день' },
  postboil_volume: { label: 'Объём после кипячения', icon: 'i-lucide-beaker', unit: 'l', group: 'Варочный день' },
  og: { label: 'Начальная плотность (OG)', short: 'OG', icon: 'i-lucide-droplets', unit: 'sg', group: 'Варочный день' },
  fermenter_volume: { label: 'Объём в ферментере', short: 'В ферментере', icon: 'i-lucide-beaker', unit: 'l', group: 'Варочный день' },
  pitch: { label: 'Задача дрожжей', icon: 'i-lucide-microscope', group: 'Брожение и розлив' },
  temp: { label: 'Температура брожения', short: 'Температура', icon: 'i-lucide-thermometer', unit: 'c', group: 'Брожение и розлив' },
  gravity: { label: 'Плотность на брожении', short: 'Плотность', icon: 'i-lucide-droplet', unit: 'sg', group: 'Брожение и розлив' },
  dry_hop: { label: 'Сухое охмеление', icon: 'i-lucide-hop', group: 'Брожение и розлив' },
  fg: { label: 'Конечная плотность (FG)', short: 'FG', icon: 'i-lucide-droplets', unit: 'sg', group: 'Брожение и розлив' },
  cold_crash: { label: 'Холодное осветление', icon: 'i-lucide-thermometer-snowflake', group: 'Брожение и розлив' },
  package: { label: 'Розлив', icon: 'i-lucide-beer', group: 'Брожение и розлив' },
  note: { label: 'Заметка', icon: 'i-lucide-notebook-pen', group: 'Заметка' },
  // переход к этапу брожения (value — номер этапа с нуля) и к шагу варочного дня (номер шага)
  stage: { label: 'Переход к этапу', icon: 'i-lucide-arrow-right', group: 'Брожение и розлив', transition: true },
  step: { label: 'Шаг варочного дня', icon: 'i-lucide-list-checks', group: 'Варочный день', transition: true },
}

/** Выбор вида записи — по группам, в порядке варки; переход к этапу — не отсюда. */
export function entryKindItems() {
  const groups = new Map<Group, { label: string; value: EntryKind; icon: string }[]>()
  for (const [value, k] of Object.entries(ENTRY_KINDS) as [EntryKind, EntryKindView][]) {
    if (k.transition) continue
    groups.set(k.group, [...groups.get(k.group) ?? [], { label: k.label, value, icon: k.icon }])
  }
  return [...groups].map(([group, items]) => [{ type: 'label' as const, label: group }, ...items])
}

/** Поле ввода замера: единица, шаг и пределы — в единицах пивовара. */
export function entryInput(kind: EntryKind, gravity: GravityUnit) {
  switch (ENTRY_KINDS[kind].unit) {
    case 'sg': return gravity === 'plato'
      ? { suffix: '°P', step: 0.1, min: 0, max: 40, digits: 1 }
      : { suffix: 'SG', step: 0.001, min: 0.98, max: 1.2, digits: 3 }
    case 'ph': return { suffix: 'pH', step: 0.01, min: 2, max: 9, digits: 2 }
    case 'l': return { suffix: 'л', step: 0.1, min: 0.1, max: 2000, digits: 1 }
    case 'c': return { suffix: '°C', step: 0.5, min: -5, max: 110, digits: 1 }
    default: return null
  }
}

/** Введённое пивоваром → как хранит сервис (плотность — в SG). */
export function toStored(kind: EntryKind, input: number, gravity: GravityUnit) {
  return ENTRY_KINDS[kind].unit === 'sg' && gravity === 'plato' ? Math.round(sgFromPlato(input) * 10000) / 10000 : input
}

/** Хранимое → в поле ввода пивовара. */
export function fromStored(kind: EntryKind, value: number, gravity: GravityUnit) {
  return ENTRY_KINDS[kind].unit === 'sg' ? gravityIn(value, gravity) : value
}

/** Значение замера для показа: «12,8 °P», «1,052», «pH 5,32», «23,5 л», «18 °C». */
export function entryValue(kind: EntryKind, value: number | null | undefined, gravity: GravityUnit) {
  if (value == null) return ''
  const n = (v: number, d: number) => v.toLocaleString('ru-RU', { maximumFractionDigits: d })
  switch (ENTRY_KINDS[kind].unit) {
    case 'sg': return fmtGravity(value, gravity)
    case 'ph': return `pH ${n(value, 2)}`
    case 'l': return `${n(value, 1)} л`
    case 'c': return `${n(value, 1)} °C`
    default: return ''
  }
}

/** Итог варки одной строкой: «12,8 → 2,9 °P · 5,2 % · 23,5 л»; пока нет FG — «OG 12,8 °P · 23,5 л». */
export function brewFacts(b: Pick<BrewSummary, 'og' | 'fg' | 'abv' | 'volume'>, gravity: GravityUnit) {
  const parts: string[] = []
  if (b.og != null && b.fg != null) parts.push(`${fmtGravity(b.og, gravity)} → ${fmtGravity(b.fg, gravity)}`)
  else if (b.og != null) parts.push(`OG ${fmtGravity(b.og, gravity)}`)
  else if (b.fg != null) parts.push(`FG ${fmtGravity(b.fg, gravity)}`)
  if (b.abv != null) parts.push(`${b.abv.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} %`)
  if (b.volume != null) parts.push(`${b.volume.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} л`)
  return parts.join(' · ')
}

/** События пивоварни: значок и тон — на экране варки и в журнале. */
export const EVENT_LOOK: Record<BrewEvent['kind'], { icon: string; tone: string }> = {
  alert: { icon: 'i-lucide-hand', tone: 'text-warning' },
  alertCleared: { icon: 'i-lucide-circle-check', tone: 'text-success' },
  addition: { icon: 'i-lucide-bell-ring', tone: 'text-warning' },
  added: { icon: 'i-lucide-circle-check', tone: 'text-success' },
  step: { icon: 'i-lucide-arrow-right', tone: 'text-info' },
  end: { icon: 'i-lucide-flag', tone: 'text-success' },
  powerOff: { icon: 'i-lucide-power', tone: 'text-muted' },
  error: { icon: 'i-lucide-circle-alert', tone: 'text-error' },
  offline: { icon: 'i-lucide-wifi-off', tone: 'text-error' },
  online: { icon: 'i-lucide-wifi', tone: 'text-success' },
}

const DAY = 86400

export type PlanState = 'done' | 'now' | 'next'
export interface StageView { name: string; temp: number; days: number; from: number; to: number; state: PlanState; manual: boolean }
export interface DryHopView { day: number | null; items: string[]; at: number | null; state: PlanState }

export const COLD = 8                    // °C: этап не теплее — холодное осветление
const STABLE_SG = 0.001                  // ≈ 0,25 °P — в пределах ошибки ареометра
const STABLE_DAYS = 2

type Fact = Pick<BrewEntry, 'kind' | 'at' | 'value'>

/** {номер этапа: когда начат по факту} — по записям «переход к этапу» и «холодное осветление» (начинает первый
 *  этап не теплее COLD). */
function stageStarts(stages: { temp: number }[], entries: Fact[]) {
  const cold = stages.findIndex((s, i) => i > 0 && s.temp <= COLD)
  const starts = new Map<number, number>()
  for (const e of [...entries].sort((a, b) => a.at - b.at)) {
    if (e.kind === 'stage' && e.value != null && e.value >= 1 && e.value < stages.length) starts.set(Math.trunc(e.value), e.at)
    else if (e.kind === 'cold_crash' && cold > 0 && !starts.has(cold)) starts.set(cold, e.at)
  }
  return starts
}

/** План брожения от его начала (задача дрожжей, иначе день варки): этапы с датами и состоянием — этап начинается
 *  через дни этапов до него или по факту (переход к этапу, холодное осветление), следующие идут от него; сухое
 *  охмеление — в свой день («на N-й день» — через N − 1 суток от начала). Разлито — всё позади. Так же считает
 *  напоминания сервис (service/app/brewery/reminders.py). */
export function fermentPlan(plan: BrewPlan | null | undefined, start: number, now: number, packagedAt?: number | null, entries: Fact[] = []) {
  const state = (from: number, to: number): PlanState => (packagedAt || now >= to ? 'done' : now >= from ? 'now' : 'next')
  const list = plan?.fermentation ?? []
  const starts = stageStarts(list, entries)
  const froms: number[] = []
  list.forEach((_, i) => froms.push(starts.get(i) ?? (i ? froms[i - 1]! + list[i - 1]!.days * DAY : start)))
  const stages: StageView[] = list.map((s, i) => {
    const from = froms[i]!
    const to = Math.max(from, i + 1 < list.length ? froms[i + 1]! : from + s.days * DAY)
    return { name: s.name || `Этап ${i + 1}`, temp: s.temp, days: s.days, from, to, state: state(from, to), manual: starts.has(i) }
  })
  const dryHops: DryHopView[] = (plan?.dryHops ?? []).map((d) => {
    const at = d.day ? start + (d.day - 1) * DAY : null
    return { day: d.day ?? null, items: d.items, at, state: at == null ? 'next' : state(at, at + DAY) }
  })
  const end = stages.length ? stages[stages.length - 1]!.to : start
  const current = stages.findLastIndex(s => s.from <= now)
  return { stages, dryHops, days: (end - start) / DAY, end, current, next: !packagedAt && current + 1 < stages.length ? current + 1 : null }
}

/** Плотность стабильна: последние замеры на брожении (и FG) за STABLE_DAYS суток и больше расходятся не больше
 *  STABLE_SG — похоже, брожение закончилось. Как у сервиса (reminders.py, stable). */
export function gravityStable(entries: Fact[]) {
  const gravity = entries.filter(e => (e.kind === 'gravity' || e.kind === 'fg') && e.value != null).sort((a, b) => a.at - b.at)
  const last = gravity[gravity.length - 1]
  if (!last || gravity.length < 2) return null
  let oldest = last
  for (let i = gravity.length - 2; i >= 0 && Math.abs(gravity[i]!.value! - last.value!) <= STABLE_SG; i--) oldest = gravity[i]!
  const days = (last.at - oldest.at) / DAY
  return days >= STABLE_DAYS ? { value: last.value!, since: oldest.at, at: last.at, days } : null
}

/** Где партия: варочный день (идёт программа пивоварни — «варка идёт») → брожение, день N → разлито. Брожения
 *  не видно (ни задачи дрожжей, ни плана — например, проверка пивоварни на воде) или давно без розлива (больше
 *  STALE дней) — не гадаем. */
const STALE = 60
export function batchStatus(b: Pick<BrewSummary, 'phase' | 'status' | 'manual' | 'fermentStart'>, now: number) {
  if (b.phase === 'brewday') return { label: !b.manual && b.status === 'running' ? 'варка идёт' : 'варочный день', color: 'info' as const }
  if (b.phase === 'packaged') return { label: 'разлито', color: 'success' as const }
  if (b.fermentStart == null) return null
  const day = Math.floor((now - b.fermentStart) / DAY) + 1
  if (day < 1 || day > STALE) return null
  return { label: `брожение · день ${day}`, color: 'primary' as const }
}

/** Сухое охмеление рецепта по дням брожения: [{day, items: ['Citra 75 г', …]}]; без дня — в конце, day null.
 *  Так же сервис кладёт его в план варки (service/app/brewery/logbook.py, dry_hops_of). */
export function dryHopDays(hops: { name?: string | null; amount?: number | null; use?: string | null; day?: number | null }[]) {
  const days = new Map<number | null, string[]>()
  for (const h of hops) {
    if (h.use !== 'dry_hop') continue
    const label = (h.name || 'Хмель') + (h.amount ? ` ${h.amount.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} г` : '')
    days.set(h.day ?? null, [...days.get(h.day ?? null) ?? [], label])
  }
  return [...days].sort((a, b) => (a[0] ?? Infinity) - (b[0] ?? Infinity)).map(([day, items]) => ({ day, items }))
}

/** На чём варили: «Кастрюля 20 л»; оборудование удалили — «без пивоварни» или «на пивоварне». */
export function equipmentLabel(b: Pick<BrewSummary, 'equipment' | 'manual'>) {
  return b.equipment?.name ?? (b.manual ? 'без пивоварни' : 'на пивоварне')
}
