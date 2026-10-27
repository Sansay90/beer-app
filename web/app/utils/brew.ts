// Логика представления варки — чистые функции от снимка посредника, истории и текущего времени.
// Стор пивоварни собирает из них геттеры; компоненты только отображают.
import type { Addition, DeviceStep, HistoryPoint, Snapshot } from '~/types'

export type Tone = 'primary' | 'success' | 'warning' | 'error' | 'info' | 'neutral'

export interface Phase {
  running: boolean
  paused: boolean
  counting: boolean          // таймер шага идёт (температура достигнута)
  heating: boolean           // программа идёт, отсчёт ещё не начался, подсказки нет
  boiling: boolean           // идёт отсчёт шага кипячения
  inRecipe: boolean
  step: number
  current: DeviceStep | null
}

export interface StatusView { label: string; tone: Tone; icon: string; live: boolean }

export interface StepView {
  index: number
  name: string
  temp: number
  minutes: number
  watts: number
  boil: boolean
  additions: number[]        // таймеры закладок, мин до конца
  state: 'done' | 'current' | 'upcoming'
}

export interface AdditionView {
  minutes: number
  items: Addition[]          // пусто — рецепт не из приложения, известно только время
  label: string
  until: number | null       // секунд до закладки; null — кипячение ещё не идёт
  phase: 'due' | 'done' | 'next' | 'later'   // due — пора закладывать, ждёт «Заложил»
}

export type NextActionId = 'startRecipe' | 'resume' | 'pause' | 'confirmAlert' | 'chooseRecipe' | 'ackAddition'

export interface NextAction {
  kind: string
  title: string
  description?: string
  icon: string
  tone: Tone
  countdown?: number | null
  attention?: boolean        // требует внимания человека — подсветка и пульсация
  actions: NextActionId[]
  addition?: number          // для ackAddition: минуты закладки
}

const RATE_WINDOW_S = 90
const ENDED_SHOW_S = 30 * 60   // сколько показывать «Программа завершена» после конца
const MIN_RATE = 0.05        // °C/мин: медленнее — прогноз не строим

export function phaseOf(s: Snapshot | null): Phase {
  const step = s?.step ?? 0
  const steps = s?.deviceRecipe?.steps ?? []
  const current = step > 0 ? steps[step - 1] ?? null : null
  const running = s?.status === 'running'
  const counting = !!s?.timer.counting
  return {
    running,
    paused: s?.status === 'paused',
    counting,
    heating: running && !counting && !s?.alert,
    boiling: !!current?.boil && counting,
    inRecipe: s?.mode === 'recipe' && step > 0,
    step,
    current,
  }
}

/** Остаток шага с поправкой на время, прошедшее после снимка. */
export function remainingSeconds(s: Snapshot | null, receivedAt: number, now: number): number | null {
  const t = s?.timer
  if (!t || t.remaining == null) return null
  return t.counting ? Math.max(0, t.remaining - (now - receivedAt)) : t.remaining
}

/** Скорость нагрева, °C/мин — по истории за последние ~1.5 мин. */
export function heatingRate(history: HistoryPoint[]): number | null {
  const last = history[history.length - 1]
  if (!last) return null
  for (let i = history.length - 2; i >= 0; i--) {
    const p = history[i]!
    if (last[0] - p[0] >= RATE_WINDOW_S) return (last[1] - p[1]) / ((last[0] - p[0]) / 60)
  }
  return null
}

/** Секунд до цели при нагреве. */
export function heatingEta(s: Snapshot | null, phase: Phase, rate: number | null): number | null {
  if (!phase.heating || s?.stepTarget == null || s.temp == null) return null
  const diff = s.stepTarget - s.temp
  if (diff <= 0) return 0
  return rate && rate > MIN_RATE ? (diff / rate) * 60 : null
}

/** 0…1: во время выдержки — прогресс таймера, во время нагрева — путь от стартовой температуры к цели. */
export function stepProgress(s: Snapshot | null, phase: Phase, remaining: number | null, heatStart: number | null): number | null {
  if (!s || (!phase.running && !phase.paused)) return null
  const minutes = s.mode === 'manual' ? s.manualMinutes : phase.current?.minutes
  if (phase.counting && minutes && remaining != null) return clamp01(1 - remaining / (minutes * 60))
  if (phase.heating && heatStart != null && s.stepTarget != null && s.temp != null && s.stepTarget > heatStart) {
    return clamp01((s.temp - heatStart) / (s.stepTarget - heatStart))
  }
  return null
}

export function statusOf(s: Snapshot | null, phase: Phase): StatusView {
  if (!s) return { label: 'Нет данных', tone: 'neutral', icon: 'i-lucide-circle', live: false }
  if (!s.online) return { label: 'Не в сети', tone: 'error', icon: 'i-lucide-wifi-off', live: false }
  if (!s.power) return { label: 'Ожидание', tone: 'neutral', icon: 'i-lucide-power', live: false }
  if (phase.paused) return { label: 'Пауза', tone: 'warning', icon: 'i-lucide-circle-pause', live: false }
  if (phase.running) {
    if (s.alert) return { label: 'Ждёт вас', tone: 'warning', icon: 'i-lucide-hand', live: true }
    if (phase.boiling) return { label: 'Кипячение', tone: 'error', icon: 'i-lucide-flame', live: true }
    if (phase.heating) return { label: 'Нагрев', tone: 'primary', icon: 'i-lucide-thermometer-sun', live: true }
    return { label: 'Выдержка', tone: 'success', icon: 'i-lucide-timer', live: true }
  }
  return { label: 'Включена', tone: 'info', icon: 'i-lucide-power', live: false }
}

export function stepViews(s: Snapshot | null, phase: Phase): StepView[] {
  return (s?.deviceRecipe?.steps ?? []).map((d, i) => ({
    index: i + 1,
    name: d.name || (d.boil ? 'Кипячение' : `Пауза ${d.temp} °C`),
    temp: d.temp,
    minutes: d.minutes,
    watts: d.watts,
    boil: d.boil,
    additions: d.additions,
    state: !phase.inRecipe ? 'upcoming' : i + 1 < phase.step ? 'done' : i + 1 === phase.step ? 'current' : 'upcoming',
  }))
}

/** Секунд всего в программе (без нагрева). */
export function programTotal(s: Snapshot | null): number {
  return (s?.deviceRecipe?.steps ?? []).reduce((a, d) => a + d.minutes * 60, 0)
}

/** Остаток программы: текущий шаг + следующие (без нагрева). */
export function programRemaining(s: Snapshot | null, phase: Phase, remaining: number | null): number | null {
  if (!phase.inRecipe) return null
  return (s?.deviceRecipe?.steps ?? []).slice(phase.step).reduce((a, d) => a + d.minutes * 60, remaining ?? 0)
}

export function additionViews(s: Snapshot | null, phase: Phase, remaining: number | null): AdditionView[] {
  const pending = new Set((s?.additionsPending ?? []).map(a => a.minutes))
  let nextMarked = false
  return (s?.additions ?? []).map((a) => {
    const until = phase.boiling && remaining != null ? remaining - a.minutes * 60 : null
    let state: AdditionView['phase'] = 'later'
    if (pending.has(a.minutes)) state = 'due'
    else if (until != null && until <= 0) state = 'done'
    else if (!nextMarked && (phase.running || phase.paused)) { state = 'next'; nextMarked = true }
    return { minutes: a.minutes, items: a.items, label: a.label, until, phase: state }
  })
}

interface NextContext {
  s: Snapshot | null
  phase: Phase
  remaining: number | null
  eta: number | null
  steps: StepView[]
  additions: AdditionView[]
  total: number
  endedAt: number | null     // конец последней программы, unix-время (событие end)
  now: number
}

/** Что делать дальше и какие действия предложить. */
export function nextAction({ s, phase, remaining, eta, steps, additions, total, endedAt, now }: NextContext): NextAction {
  if (!s) return { kind: 'wait', title: 'Подключаемся…', icon: 'i-lucide-loader-circle', tone: 'neutral', actions: [] }
  if (!s.online) {
    return { kind: 'offline', title: 'Пивоварня не в сети', description: 'Она включена в розетку и подключена к той же Wi-Fi?', icon: 'i-lucide-wifi-off', tone: 'error', actions: [] }
  }
  if (s.alert) {
    const text = {
      malt: { title: 'Засыпьте солод', description: 'Подтвердите, когда солод будет в корзине.', icon: 'i-lucide-wheat' },
      mashEnd: { title: 'Затирание закончено', description: 'Выньте солодовую корзину и подтвердите — после этого начнётся кипячение.', icon: 'i-lucide-package-open' },
    }[s.alert as 'malt' | 'mashEnd'] ?? { title: 'Пивоварня ждёт подтверждения', icon: 'i-lucide-hand' }
    return { kind: 'alert', ...text, tone: 'warning', attention: true, actions: ['confirmAlert', 'pause'] }
  }
  if (phase.paused) {
    return { kind: 'paused', title: 'Пауза', description: 'Таймер остановлен. Продолжите, когда будете готовы.', icon: 'i-lucide-circle-pause', tone: 'warning', actions: ['resume'] }
  }
  // закладка ждёт «Заложил» даже после конца программы — напоминание не должно потеряться
  const due = (s.additionsPending ?? [])[0]
  if (due) {
    return {
      kind: 'additionNow',
      title: due.items.length ? `Заложите: ${due.label}` : 'Время закладки',
      description: `Закладка за ${due.minutes} мин до конца кипячения`,
      icon: slotIcon(due.items),
      tone: 'warning',
      attention: true,
      actions: ['ackAddition'],
      addition: due.minutes,
    }
  }
  if (phase.running) {
    const next = additions.find(a => a.phase === 'next' && a.until != null)
    if (next) {
      return { kind: 'addition', title: next.items.length ? next.label : `Закладка за ${next.minutes} мин`, description: 'Следующая закладка', icon: slotIcon(next.items), tone: 'primary', countdown: next.until, actions: ['pause'] }
    }
    if (phase.heating) {
      const title = phase.current?.boil ? 'Нагрев до кипения' : `Нагрев до ${fmtTemp(s.stepTarget)} °C`
      const description = eta != null ? `Осталось примерно ${fmtMinutes(Math.max(1, Math.round(eta / 60)))}` : 'Прогноз появится через пару минут нагрева'
      return { kind: 'heating', title, description, icon: 'i-lucide-thermometer-sun', tone: 'primary', actions: ['pause'] }
    }
    if (phase.inRecipe && phase.step === steps.length && phase.counting && remaining === 0) {
      return { kind: 'finishing', title: 'Программа завершается', icon: 'i-lucide-flag', tone: 'success', actions: [] }
    }
    if (phase.inRecipe && phase.step < steps.length) {
      const n = steps[phase.step]!
      return { kind: 'nextStep', title: `Дальше: ${n.name}`, description: n.boil ? 'Нагрев до кипения' : `Нагрев до ${fmtTemp(n.temp)} °C`, icon: 'i-lucide-timer', tone: 'success', countdown: remaining, actions: ['pause'] }
    }
    return { kind: 'finish', title: s.mode === 'manual' ? 'Ручной режим' : 'Последний шаг', description: 'До конца', icon: 'i-lucide-flag', tone: 'success', countdown: remaining, actions: ['pause'] }
  }
  if (endedAt != null && now - endedAt < ENDED_SHOW_S) {
    return { kind: 'ended', title: 'Программа завершена', description: `Закончилась в ${new Date(endedAt * 1000).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}. Сусло готово к охлаждению.`, icon: 'i-lucide-flag', tone: 'success', actions: [] }
  }
  if (!s.deviceRecipe) {
    return { kind: 'noRecipe', title: 'Загрузите рецепт', description: 'В пивоварне нет известного рецепта — выберите его в разделе «Рецепты».', icon: 'i-lucide-book-open', tone: 'neutral', actions: ['chooseRecipe'] }
  }
  return {
    kind: 'ready',
    title: s.deviceRecipe.name ? `«${s.deviceRecipe.name}»` : 'Рецепт из Smart Life',
    description: `${s.deviceRecipe.steps.length} шагов · ${fmtMinutes(Math.round(total / 60))} без учёта нагрева`,
    icon: 'i-lucide-circle-play',
    tone: 'primary',
    actions: ['startRecipe'],
  }
}

function clamp01(x: number) {
  return Math.min(1, Math.max(0, x))
}
