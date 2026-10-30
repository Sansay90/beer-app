// Варочный день партии: шаги, текущий шаг и когда начат каждый приходят с сервиса (service/app/brewery/brewday.py —
// по записям «step» пивовара и событиям программы пивоварни). Здесь — что приготовить на шаге (вода и соли, засыпь,
// дрожжи, промывочная вода, объём и плотность до кипячения — из рецепта партии с испарением оборудования) и живой шаг пивоварни, пока она варит эту
// партию: k-й шаг программы — k-я пауза, кипячение — кипячение, подсказка «солод» — засыпь, «конец затирания» —
// промывка, нагрев до первой паузы — нагрев. Варочный день позади (дрожжи, «закончить», брошен) — все шаги сделаны;
// вылили в варочный день, без дрожжей, — пройденное сделано, остальное так и не случилось.
// Остаток таймера считает «Сейчас» (stepRemaining): ему нужны секунды, остальной странице — нет.
import type { InjectionKey } from 'vue'
import type { BrewDayStep, BrewDetail, BrewEntry, Recipe, Snapshot } from '~/types'
import type { GravityUnit } from '~/utils/beer'
import type { Phase } from '~/utils/brew'
import { additionAmount, additionName, unitLabel } from '~/utils/additions'
import { fmtGravity } from '~/utils/beer'
import { preBoilSg } from '~/utils/calc'
import { fmtMinutes, fmtNumber, fmtTemp, SEP } from '~/utils/format'
import { WATER_AGENTS, waterAmount, waterVolumes } from '~/utils/water'

export type StepState = 'done' | 'now' | 'next'

/** Дописать введённые замеры шага: поле пишет значение через паузу или уходя из фокуса — «Дальше», нажатое сразу
 *  после ввода, сначала дожидается записи (day/NowCard.vue ↔ day/MeasureInput.vue). */
export const MEASURE_FLUSH: InjectionKey<Set<() => Promise<unknown>>> = Symbol('measure-flush')
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

/** «Brewtan B 0,5 г», «Hallertau 20 г» — хмель и прочее рецепта с этим применением. */
function usedAt(r: Recipe, hopUse: string, miscUse: string | null) {
  return [
    ...(r.hops ?? []).filter(h => h.use === hopUse).map(h => ({ kind: 'hop' as const, name: h.name, amount: h.amount, unit: 'g' as const })),
    ...(r.miscs ?? []).filter(m => miscUse != null && m.use === miscUse),
  ].map(a => [additionName(a), additionAmount(a)].filter(Boolean).join(' '))
}

/** Что приготовить на шаге: на подготовке — вода с солями и тем, что идёт в затор (хмель, Brewtan B…), засыпь по
 *  солодам, дрожжи; на промывке — объёмы, плотность до кипячения (в единицах пивовара) и хмель на первое сусло. */
export function stepDetails(step: Pick<BrewDayStep, 'kind'>, r: Recipe | null | undefined, unit: GravityUnit = 'plato'): string[] {
  if (!r || (step.kind !== 'prepare' && step.kind !== 'sparge')) return []
  const v = waterVolumes(r, r.batch?.evaporation)
  if (step.kind === 'sparge') {
    const firstWort = usedAt(r, 'first_wort', null)
    const sg = v.preBoil != null ? preBoilSg(r, v.preBoil) : null
    return [v.sparge != null && `промывочная вода ${litres(v.sparge)}`,
      v.preBoil != null && `до кипячения ${litres(v.preBoil)}${sg != null && sg > 1 ? `${SEP}${fmtGravity(sg, unit)}` : ''}`,
      firstWort.length > 0 && `на первое сусло: ${firstWort.join(', ')}`]
      .filter(Boolean) as string[]
  }
  const out: string[] = []
  const salts = r.water?.additions ?? []
  for (const [target, label, l] of [['mash', 'Затор', v.mash], ['sparge', 'Промывка', v.sparge]] as const) {
    const mine = salts.filter(a => (a.target ?? 'mash') === target)
    const parts = mine.map(a => [(a.agent === 'other' ? a.name || 'добавка' : WATER_AGENTS[a.agent].label).toLowerCase(),
      waterAmount(a.agent, a.amount)].filter(Boolean).join(' '))
    if (target === 'mash') parts.push(...usedAt(r, 'mash', 'mash'))
    if (l == null && !parts.length) continue
    out.push(`${label}: ${litres(l)}${parts.length ? ` — ${parts.join(', ')}` : ''}`)
  }
  const grains = (r.fermentables ?? []).filter(f => (f.use ?? 'mash') === 'mash' && f.amount)
  if (grains.length) {
    const total = grains.reduce((a, f) => a + f.amount!, 0)
    out.push(`Засыпь ${fmtNumber(total, 2, ' кг')}: ${grains.map(f => `${f.name || 'солод'} ${fmtNumber(f.amount, 3, ' кг')}`).join(SEP)}`)
  }
  const yeasts = (r.yeasts ?? []).filter(y => y.name)
  if (yeasts.length) {
    out.push(`Дрожжи: ${yeasts.map(y => y.name + (y.amount ? ` ${fmtNumber(y.amount, 1)} ${unitLabel(y.unit ?? 'pkg')}` : '')).join(', ')}`)
  }
  return out
}

export function brewDay(
  brew: Pick<BrewDetail, 'id' | 'brewDay' | 'currentStep' | 'phase' | 'snapshot' | 'fermentStart'>,
  s: Snapshot | null,
  phase: Phase,
  unit: GravityUnit = 'plato',
): BrewDayView {
  const steps = brew.brewDay ?? []
  const over = brew.phase !== 'brewday'
  const cut = brew.phase === 'dumped' && brew.fermentStart == null
  const byBrewery = !over && s?.brewId === brew.id
  const current = (byBrewery ? breweryStep(steps, s, phase) : null) ?? brew.currentStep
  const views: DayStep[] = steps.map((st, i) => ({
    ...st,
    state: cut ? (i < current ? 'done' : 'next') : over || i < current ? 'done' : i === current ? 'now' : 'next',
    details: stepDetails(st, brew.snapshot, unit),
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
  return [step.temp != null && `${fmtTemp(step.temp)} °C`, step.minutes && fmtMinutes(step.minutes)].filter(Boolean).join(SEP)
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
