import type { BrewEvent, HistoryPoint, ManualMode, Snapshot, SettingsUpdate } from '~/types'

const HISTORY_MAX = 10800               // 6 ч при точке раз в 2 с
const HISTORY_STEP_S = 2
const EVENTS_MAX = 200

/** Пивоварня: живое состояние из потока SSE, производные для интерфейса и команды. Ограничения модели — useLimits. */
export const useBreweryStore = defineStore('brewery', () => {
  const { $api } = useNuxtApp()

  // ── состояние ──────────────────────────────────────────────────────────────
  const snapshot = ref<Snapshot | null>(null)
  const receivedAt = ref(0)              // момент снимка по часам клиента
  const connected = ref(false)           // связь с сервисом
  const events = ref<BrewEvent[]>([])    // новые — первыми
  const history = ref<HistoryPoint[]>([])
  const heatStart = ref<number | null>(null)
  const now = useNow({ interval: 500 })

  // ── производные ────────────────────────────────────────────────────────────
  const online = computed(() => !!snapshot.value?.online)
  const phase = computed(() => phaseOf(snapshot.value))
  const remaining = computed(() => remainingSeconds(snapshot.value, receivedAt.value, now.value.getTime() / 1000))
  const rate = computed(() => heatingRate(history.value))
  const eta = computed(() => heatingEta(snapshot.value, phase.value, rate.value))
  const progress = computed(() => stepProgress(snapshot.value, phase.value, remaining.value, heatStart.value))
  const status = computed(() => statusOf(snapshot.value, phase.value))
  const steps = computed(() => stepViews(snapshot.value, phase.value))
  const additions = computed(() => additionViews(snapshot.value, phase.value, remaining.value))
  const total = computed(() => programTotal(snapshot.value))
  const programLeft = computed(() => programRemaining(snapshot.value, phase.value, remaining.value))
  // «Программа завершена» — если последнее событие программы (не связь) — её конец
  const endedAt = computed(() => {
    const last = events.value.find(e => e.kind === 'end' || e.kind === 'step' || e.kind === 'alert' || e.kind === 'powerOff')
    return last?.kind === 'end' ? last.at : null
  })
  const next = computed(() => nextAction({
    s: snapshot.value, phase: phase.value, remaining: remaining.value, eta: eta.value,
    steps: steps.value, additions: additions.value, total: total.value,
    endedAt: endedAt.value, now: now.value.getTime() / 1000,
  }))

  // стартовая температура текущего нагрева — для полосы прогресса
  watch(() => [phase.value.heating, phase.value.step] as const, ([heating]) => {
    heatStart.value = heating ? snapshot.value?.temp ?? null : null
  })

  // ── приём данных ───────────────────────────────────────────────────────────
  function applySnapshot(s: Snapshot) {
    snapshot.value = s
    receivedAt.value = Date.now() / 1000
    if (s.online && s.temp != null) appendHistory(s.temp, s.stepTarget ?? null)   // без связи температура — последняя известная, не живая
  }

  function appendHistory(temp: number, target: number | null) {
    const t = Date.now() / 1000
    const last = history.value[history.value.length - 1]
    if (last && (t - last[0] < HISTORY_STEP_S || (last[1] === temp && last[2] === target && t - last[0] < 15))) return
    history.value = [...history.value.slice(-(HISTORY_MAX - 1)), [t, temp, target]]
  }

  function pushEvent(e: BrewEvent) {
    events.value = [e, ...events.value].slice(0, EVENTS_MAX)
  }

  function setConnected(value: boolean) {
    connected.value = value
  }

  async function loadHistory() {
    history.value = await $api('/api/history', { query: { minutes: 360 } }) as HistoryPoint[]
  }

  async function loadEvents() {
    events.value = await $api('/api/events')
  }

  /** Догнать сервис после (пере)подключения: то, что могло случиться без нас. */
  async function resync() {
    await Promise.allSettled([loadHistory(), loadEvents()])
  }

  // ── команды ────────────────────────────────────────────────────────────────
  const setPower = async (on: boolean) => { await $api('/api/power', { method: 'POST', body: { on } }) }
  const setPump = async (on: boolean) => { await $api('/api/pump', { method: 'POST', body: { on } }) }
  const setFlow = async (level: number) => { await $api('/api/flow', { method: 'POST', body: { level } }) }
  const setManual = async (body: ManualMode) => { await $api('/api/manual', { method: 'POST', body }) }
  const start = async () => { await $api('/api/start', { method: 'POST' }) }
  const pause = async () => { await $api('/api/pause', { method: 'POST' }) }
  const startRecipe = async () => { await $api('/api/recipe/start', { method: 'POST' }) }
  const confirmAlert = async () => { await $api('/api/alert/confirm', { method: 'POST' }) }
  const saveSettings = async (body: SettingsUpdate) => { await $api('/api/settings', { method: 'POST', body }) }
  const ackAddition = async (minutes: number) => {
    await $api('/api/additions/{minutes}/ack', { method: 'POST', path: { minutes } })
  }

  return {
    snapshot, connected, events, history,
    online, phase, remaining, rate, eta, progress, status, steps, additions, total, programLeft, next,
    applySnapshot, pushEvent, setConnected, resync,
    setPower, setPump, setFlow, setManual, start, pause, startRecipe, confirmAlert, saveSettings, ackAddition,
  }
})
