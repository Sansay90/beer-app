// Варочный день партии: шаги, текущий шаг и когда начат каждый приходят с сервиса (service/app/brewery/brewday.py —
// по записям «step» пивовара и событиям программы пивоварни). Здесь — что приготовить на шаге (вода и соли, засыпь,
// дрожжи, промывочная вода — из рецепта партии с испарением оборудования) и живой шаг пивоварни, пока она варит эту
// партию: k-й шаг программы — k-я пауза, кипячение — кипячение, подсказка «солод» — засыпь, «конец затирания» —
// промывка, нагрев до первой паузы — нагрев. Варочный день позади (дрожжи, «закончить», брошен) — все шаги сделаны.
// Остаток таймера считает «Сейчас» (stepRemaining): ему нужны секунды, остальной странице — нет.
import type { BrewDayStep, BrewDetail, BrewEntry, Recipe, Snapshot } from '~/types'
import type { Phase } from '~/utils/brew'
import { unitLabel } from '~/utils/additions'
import { fmtMinutes, fmtNumber, fmtTemp } from '~/utils/format'
import { WATER_AGENTS, waterAmount, waterVolumes } from '~/utils/water'

export type StepState = 'done' | 'now' | 'next'
export interface DayStep extends BrewDayStep {
  state: StepState
  details: string[]          // что приготовить
  ends: number | null        // когда истекает таймер шага
}
export interface BrewDayView {
  steps: DayStep[]
  current: number
  active: boolean            // варочный день идёт: показывать «Сейчас»
  byBrewery: boolean         // шаги ведёт пивоварня
}

/** Шаг варочного дня по живой программе пивоварни; null — программа не идёт. */
export function breweryStep(steps: BrewDayStep[], s: Snapshot | null, phase: Phase) {
  if (!s || !phase.inRecipe) return null
  const by = (kind: BrewDayStep['kind']) => steps.find(x => x.kind === kind)?.index ?? null
  if (s.alert === 'malt') return by('mash_in')
  if (s.alert === 'mashEnd') return by('sparge')
  if (phase.current?.boil) return by('boil')
  const rest = steps.filter(x => x.kind === 'rest')[phase.step - 1]
  if (!rest) return null
  return phase.step === 1 && phase.heating ? by('heat') ?? rest.index : rest.index
}

const litres = (v: number | null) => (v == null ? '—' : fmtNumber(v, 1, ' л'))

/** Что приготовить на шаге: на подготовке — вода с солями, засыпь по солодам, дрожжи; на промывке — объёмы. */
export function stepDetails(step: Pick<BrewDayStep, 'kind'>, r: Recipe | null | undefined): string[] {
  if (!r || (step.kind !== 'prepare' && step.kind !== 'sparge')) return []
  const v = waterVolumes(r, r.batch?.evaporation)
  if (step.kind === 'sparge') {
    return [v.sparge != null && `промывочная вода ${litres(v.sparge)}`, v.preBoil != null && `до кипячения ${litres(v.preBoil)}`]
      .filter(Boolean) as string[]
  }
  const out: string[] = []
  const salts = r.water?.additions ?? []
  for (const [target, label, l] of [['mash', 'Затор', v.mash], ['sparge', 'Промывка', v.sparge]] as const) {
    const mine = salts.filter(a => (a.target ?? 'mash') === target)
    if (l == null && !mine.length) continue
    const parts = mine.map(a => [(a.agent === 'other' ? a.name || 'добавка' : WATER_AGENTS[a.agent].label).toLowerCase(),
      waterAmount(a.agent, a.amount)].filter(Boolean).join(' '))
    out.push(`${label}: ${litres(l)}${parts.length ? ` — ${parts.join(', ')}` : ''}`)
  }
  const grains = (r.fermentables ?? []).filter(f => (f.use ?? 'mash') === 'mash' && f.amount)
  if (grains.length) {
    const total = grains.reduce((a, f) => a + f.amount!, 0)
    out.push(`Засыпь ${fmtNumber(total, 2, ' кг')}: ${grains.map(f => `${f.name || 'солод'} ${fmtNumber(f.amount, 3, ' кг')}`).join(' · ')}`)
  }
  const yeasts = (r.yeasts ?? []).filter(y => y.name)
  if (yeasts.length) {
    out.push(`Дрожжи: ${yeasts.map(y => y.name + (y.amount ? ` ${fmtNumber(y.amount, 1)} ${unitLabel(y.unit ?? 'pkg')}` : '')).join(', ')}`)
  }
  return out
}

export function brewDay(
  brew: Pick<BrewDetail, 'id' | 'brewDay' | 'currentStep' | 'phase' | 'snapshot'>,
  s: Snapshot | null,
  phase: Phase,
): BrewDayView {
  const steps = brew.brewDay ?? []
  const over = brew.phase !== 'brewday'
  const byBrewery = !over && s?.brewId === brew.id
  const current = (byBrewery ? breweryStep(steps, s, phase) : null) ?? brew.currentStep
  const views: DayStep[] = steps.map((st, i) => ({
    ...st,
    state: over || i < current ? 'done' : i === current ? 'now' : 'next',
    details: stepDetails(st, brew.snapshot),
    ends: st.at != null && st.minutes ? st.at + st.minutes * 60 : null,
  }))
  return { steps: views, current, active: !over, byBrewery }
}

/** Секунд до конца таймера шага; отрицательное — время вышло; null — у шага нет таймера или он не начат. */
export function stepRemaining(step: Pick<DayStep, 'ends'>, now: number) {
  return step.ends != null ? step.ends - now : null
}

/** «66,0 °C · 1 ч» — температура и время шага. */
export function stepLine(step: Pick<BrewDayStep, 'temp' | 'minutes'>) {
  return [step.temp != null && `${fmtTemp(step.temp)} °C`, step.minutes && fmtMinutes(step.minutes)].filter(Boolean).join(' · ')
}

/** Когда закладка на кипячении: «старт», «конец», «за 10 мин». */
export function additionWhen(minutes: number, boil: number | null | undefined) {
  return minutes === boil ? 'старт' : minutes === 0 ? 'конец' : `за ${minutes} мин`
}

/** Последний замер каждого вида — для чипов на шагах. */
export function lastMeasures(entries: BrewEntry[]) {
  const out = new Map<BrewEntry['kind'], BrewEntry>()
  for (const e of entries) {
    if (e.value == null) continue
    const prev = out.get(e.kind)
    if (!prev || e.at >= prev.at) out.set(e.kind, e)
  }
  return out
}
