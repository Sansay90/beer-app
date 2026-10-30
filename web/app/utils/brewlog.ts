// Журнал варки: виды записей, их единицы и показ. Значения хранятся как у сервиса (service/app/brewery/logbook.py):
// плотность — SG, pH, объём — л, температура — °C; плотность вводится и показывается в единицах пивовара.
import type { BrewEntry, BrewEvent, BrewPlan, BrewSummary } from '~/types'
import type { GravityUnit } from '~/utils/beer'
import { fmtGravity, gravityIn, sgFromPlato } from '~/utils/beer'
import { fmtNumber } from '~/utils/format'

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
export type StageUntil = 'gravity' | 'fg' | 'days'
export interface StageView {
  name: string
  temp: number
  days: number               // until = days — сколько держать; gravity и fg — примерно
  until: StageUntil
  target: number | null      // until = gravity: цель партии — от фактической OG, SG
  from: number
  to: number
  state: PlanState
  manual: boolean
}
export interface DryHopView {
  day: number | null
  target: number | null      // при какой плотности, SG — цель партии
  items: string[]
  at: number | null          // когда: по плотности — замер, на котором дошли; иначе — по дню (у плотности — примерно)
  estimated: boolean         // at — лишь прикидка по дню: по плотности ещё не дошли
  state: PlanState
}

export const COLD = 8                    // °C: этап не теплее — холодное осветление
const STABLE_SG = 0.001                  // ≈ 0,25 °P — в пределах ошибки ареометра
const STABLE_DAYS = 2
const DROP_SG = 0.005                    // «стоит» — только когда плотность уже пошла вниз (не лаг-фаза)
const SLOW_SG = 0.002                    // ≈ 0,5 °P в сутки: медленнее — брожение замедлилось
const SLOW_SPAN = DAY                    // скорость — по двум замерам не ближе суток: шаг ареометра 0,001 не мешает

type Fact = Pick<BrewEntry, 'kind' | 'at' | 'value'>
// план партии (BrewPlan); у планов до плотностей этапы без условия — по дням
type PlanIn = Pick<BrewPlan, 'og'> & {
  fermentation?: { name?: string | null; temp: number; days: number; until?: StageUntil | null; gravity?: number | null }[] | null
  dryHops?: { day?: number | null; gravity?: number | null; items: string[] }[] | null
}

/** Цель по плотности в партии: та же доля сбраживания от фактической OG; OG или цели нет — как в рецепте.
 *  Как у сервиса (reminders.py, target_of). */
export function targetOf(target: number | null | undefined, planOg: number | null | undefined, og: number | null | undefined) {
  if (target == null) return null
  if (!og || !planOg || planOg <= 1) return target
  return 1 + ((target - 1) * (og - 1)) / (planOg - 1)
}

/** Условие этапа кратко: «до 6,0 °P · ~5 дн.», «до FG · ~4 дн.», «2 дн.». */
export function stageCondition(s: { until?: StageUntil | null; gravity?: number | null; days: number }, unit: GravityUnit) {
  const until = s.until ?? 'days'
  const days = fmtNumber(s.days, 1)
  if (until === 'days') return `${days} дн.`
  const goal = until === 'fg' ? 'до FG' : `до ${fmtGravity(s.gravity, unit)}`
  return s.days ? `${goal} · ~${days} дн.` : goal
}

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

const gravityOf = (entries: Fact[]) => entries
  .filter(e => (e.kind === 'gravity' || e.kind === 'fg') && e.value != null).sort((a, b) => a.at - b.at)
/** OG партии — последний замер OG; нет — null. */
export const ogOf = (entries: Fact[]) => [...entries].sort((a, b) => a.at - b.at).findLast(e => e.kind === 'og' && e.value)?.value ?? null

/** План брожения от его начала (задача дрожжей, иначе конец варочного дня): этапы с датами и состоянием. Этап
 *  начинается после предыдущего или по факту (переход к этапу, холодное осветление), следующие идут от него.
 *  «Выдержка» кончается через свои дни; «до плотности» и «до FG» — по замерам: их дни — прикидка, и пока идущий
 *  такой этап не закончен переходом, он не кончается раньше now — следующие сдвигаются. Цель по плотности —
 *  от фактической OG. Сухое охмеление — при своей плотности (дошли — когда) или в свой день («на N-й день» —
 *  через N − 1 суток). finished — план пройден: последний этап позади. Разлито — всё позади. Так же считает
 *  напоминания сервис (service/app/brewery/reminders.py, Ferment); общие примеры — shared/ferment-cases.json. */
export function fermentPlan(plan: PlanIn | null | undefined, start: number, now: number, packagedAt?: number | null, entries: Fact[] = []) {
  const list = plan?.fermentation ?? []
  const starts = stageStarts(list, entries)
  const latest = Math.max(0, ...starts.keys())
  const og = ogOf(entries)
  const stages: StageView[] = []
  let from = start
  list.forEach((s, i) => {
    from = starts.get(i) ?? from
    const until = (s.until ?? 'days') as StageUntil
    let to = starts.get(i + 1) ?? from + s.days * DAY
    if (!starts.has(i + 1) && i >= latest && from <= now && until !== 'days' && !packagedAt) to = Math.max(to, now)
    to = Math.max(to, from)
    stages.push({ name: s.name || `Этап ${i + 1}`, temp: s.temp, days: s.days, until,
      target: until === 'gravity' ? targetOf(s.gravity, plan?.og, og) : null, from, to, state: 'next', manual: starts.has(i) })
    from = to
  })
  // идёт — последний начатый к now (ни один — −1); лишь по прикидке начинающийся ровно сейчас ещё не идёт
  const current = stages.findLastIndex(s => s.from < now || (s.manual && s.from <= now))
  stages.forEach((s, i) => {
    s.state = packagedAt || i < current || (i === current && s.until === 'days' && now >= s.to) ? 'done' : i === current ? 'now' : 'next'
  })
  const gravity = gravityOf(entries)
  const dryHops: DryHopView[] = (plan?.dryHops ?? []).map((d) => {
    const target = d.gravity ? targetOf(d.gravity, plan?.og, og) : null
    const reached = target != null ? gravity.find(e => e.at >= start && e.value! <= target + 1e-9) ?? null : null
    const at = reached?.at ?? (d.day ? start + (d.day - 1) * DAY : null)
    let state: PlanState = 'next'
    if (packagedAt) state = 'done'
    else if (target != null) state = reached ? 'now' : 'next'
    else if (at != null) state = now >= at + DAY ? 'done' : now >= at ? 'now' : 'next'
    return { day: d.day ?? null, target, items: d.items, at, estimated: target != null && !reached, state }
  })
  const last = stages[stages.length - 1]
  const end = last ? last.to : start
  return { stages, dryHops, days: (end - start) / DAY, end, current, og,
    finished: !!packagedAt || last?.state === 'done',
    estimated: stages.some(s => s.until !== 'days'), next: !packagedAt && current + 1 < stages.length ? current + 1 : null }
}
export type FermentPlanView = ReturnType<typeof fermentPlan>

/** Плотность стабильна: последние замеры на брожении (и FG) за STABLE_DAYS суток и больше расходятся не больше
 *  STABLE_SG — похоже, брожение закончилось. top — OG: плотность должна уже пойти вниз, иначе лаг-фаза сойдёт
 *  за конец. Как у сервиса (reminders.py, stable). */
export function gravityStable(entries: Fact[], top: number | null = null) {
  const gravity = gravityOf(entries)
  const last = gravity[gravity.length - 1]
  if (!last || gravity.length < 2) return null
  if (top != null && last.value! > top - DROP_SG) return null
  let oldest = last
  for (let i = gravity.length - 2; i >= 0 && Math.abs(gravity[i]!.value! - last.value!) <= STABLE_SG; i--) oldest = gravity[i]!
  const days = (last.at - oldest.at) / DAY
  return days >= STABLE_DAYS ? { value: last.value!, since: oldest.at, at: last.at, days } : null
}

/** Замер, на котором брожение замедлилось до цели: пройдена половина пути от top (плотность на начало этапа)
 *  к target, а плотность падает медленнее SLOW_SG в сутки (по двум замерам не ближе суток). Как у сервиса
 *  (reminders.py, slowdown). */
function slowdown(measures: Fact[], top: number | null, target: number) {
  const last = measures[measures.length - 1]
  if (top == null || !last || measures.length < 2 || last.value! > top - (top - target) / 2) return null
  const prev = measures.slice(0, -1).findLast(e => last.at - e.at >= SLOW_SPAN)
  if (!prev) return null
  return (prev.value! - last.value!) / ((last.at - prev.at) / DAY) < SLOW_SG ? last : null
}

export interface FermentAdvice { stage: number; why: 'target' | 'slow' | 'stable'; value: number; at: number }

/** Пора ли кончать идущий этап «до плотности» или «до FG»: цель достигнута, брожение замедлилось до цели (половина
 *  пути — от плотности на начало этапа) или плотность встала. p — уже посчитанный план. Как у сервиса
 *  (reminders.py, Ferment.advice). */
export function fermentAdvice(p: FermentPlanView, plan: PlanIn | null | undefined, entries: Fact[] = []): FermentAdvice | null {
  const st = p.stages[p.current]
  if (p.finished || !st || st.until === 'days') return null
  const gravity = gravityOf(entries)
  const top = p.og ?? plan?.og ?? null
  const since = gravity.filter(e => e.at >= st.from)
  const hit = (why: FermentAdvice['why'], e: { value: number; at: number }) => ({ stage: p.current, why, value: e.value, at: e.at })
  if (st.until === 'gravity') {
    const reached = since.find(e => e.value! <= st.target! + 1e-9)
    if (reached) return hit('target', { value: reached.value!, at: reached.at })
    const before = gravity.filter(e => e.at <= st.from)
    const slow = slowdown(since, before.length ? before[before.length - 1]!.value! : top, st.target!)
    return slow ? hit('slow', { value: slow.value!, at: slow.at }) : null
  }
  const calm = gravityStable(since, top)
  return calm ? hit('stable', calm) : null
}

/** «Похоже, брожение закончилось»: идёт выдержка (или этапов нет), а плотность с начала этапа стоит двое суток.
 *  У «до плотности» и «до FG» это их собственное «пора» (fermentAdvice). Как у сервиса (reminders.py, Ferment.calm). */
export function fermentCalm(p: FermentPlanView, plan: PlanIn | null | undefined, entries: Fact[] = []) {
  const st = p.stages[p.current]
  if (st && st.until !== 'days') return null
  const gravity = gravityOf(entries)
  return gravityStable(st ? gravity.filter(e => e.at >= st.from) : gravity, p.og ?? plan?.og ?? null)
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

/** Сухое охмеление рецепта: [{day, gravity, items: ['Citra 75 г', …]}] — по плотности (день — примерный) или по
 *  дню брожения. По дню (у плотности — примерному) — раньше выше; только по плотности — после них, выше плотность —
 *  раньше; без дня и плотности — в конце. Так же сервис кладёт его в план варки (service/app/brewery/logbook.py,
 *  dry_hops_of). */
export function dryHopDays(hops: { name?: string | null; amount?: number | null; use?: string | null; day?: number | null; gravity?: number | null }[]) {
  const groups = new Map<string, { day: number | null; gravity: number | null; items: string[] }>()
  for (const h of hops) {
    if (h.use !== 'dry_hop') continue
    const label = (h.name || 'Хмель') + (h.amount ? ` ${h.amount.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} г` : '')
    const key = `${h.gravity ?? ''}|${h.day ?? ''}`
    const g = groups.get(key) ?? { day: h.day ?? null, gravity: h.gravity ?? null, items: [] }
    g.items.push(label)
    groups.set(key, g)
  }
  const rank = (g: { day: number | null; gravity: number | null }) =>
    [g.gravity == null && g.day == null ? 1 : 0, g.day == null ? 1 : 0, g.day ?? 0, -(g.gravity ?? 0)]
  return [...groups.values()].sort((a, b) => {
    const [x, y] = [rank(a), rank(b)]
    return x[0]! - y[0]! || x[1]! - y[1]! || x[2]! - y[2]! || x[3]! - y[3]!
  })
}

/** Когда сухое охмеление: «при 4,4 °P · ~4-й день», «4-й день брожения», «день не указан». */
export function dryHopWhen(d: { day: number | null; gravity?: number | null; target?: number | null }, unit: GravityUnit) {
  const g = d.target ?? d.gravity ?? null
  if (g != null) return `при ${fmtGravity(g, unit)}${d.day != null ? ` · ~${d.day}-й день` : ''}`
  return d.day != null ? `${d.day}-й день брожения` : 'день не указан'
}

/** На чём варили: «Кастрюля 20 л»; оборудование удалили — «без пивоварни» или «на пивоварне». */
export function equipmentLabel(b: Pick<BrewSummary, 'equipment' | 'manual'>) {
  return b.equipment?.name ?? (b.manual ? 'без пивоварни' : 'на пивоварне')
}
