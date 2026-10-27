import type { BrewEvent, HistoryPoint, Limits, ManualMode, Snapshot, SettingsUpdate } from '~/types'

const HISTORY_MAX = 10800               // 6 ч при точке раз в 2 с
const HISTORY_STEP_S = 2
const EVENTS_MAX = 200

/** Пивоварня: живое состояние из потока SSE, производные для интерфейса и команды. */
export const useBreweryStore = defineStore('brewery', () => {
  const { $api } = useNuxtApp()

  // ── состояние ──────────────────────────────────────────────────────────────
  const snapshot = ref<Snapshot | null>(null)
  const receivedAt = ref(0)              // момент снимка по часам клиента
  const connected = ref(false)           // связь с посредником
  const events = ref<BrewEvent[]>([])    // новые — первыми
  const history = ref<HistoryPoint[]>([])
  const limits = ref<Limits | null>(null)
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

  // ограничения зависят только от модели: первый снимок (undefined → модель или null) и смена модели
  watch(() => snapshot.value?.settings.model, () => loadLimits().catch(() => {}))

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
    history.value = unwrap(await $api.GET('/api/history', { params: { query: { minutes: 360 } } })) as HistoryPoint[]
  }

  async function loadEvents() {
    events.value = unwrap(await $api.GET('/api/events'))
  }

  async function loadLimits() {
    limits.value = unwrap(await $api.GET('/api/limits'))
  }

  /** Догнать посредника после (пере)подключения: то, что могло случиться без нас. */
  async function resync() {
    await Promise.allSettled([loadHistory(), loadEvents()])
  }

  // ── команды ────────────────────────────────────────────────────────────────
  const setPower = async (on: boolean) => { unwrap(await $api.POST('/api/power', { body: { on } })) }
  const setPump = async (on: boolean) => { unwrap(await $api.POST('/api/pump', { body: { on } })) }
  const setFlow = async (level: number) => { unwrap(await $api.POST('/api/flow', { body: { level } })) }
  const setManual = async (body: ManualMode) => { unwrap(await $api.POST('/api/manual', { body })) }
  const start = async () => { unwrap(await $api.POST('/api/start')) }
  const pause = async () => { unwrap(await $api.POST('/api/pause')) }
  const startRecipe = async () => { unwrap(await $api.POST('/api/recipe/start')) }
  const confirmAlert = async () => { unwrap(await $api.POST('/api/alert/confirm')) }
  const saveSettings = async (body: SettingsUpdate) => { unwrap(await $api.POST('/api/settings', { body })) }
  const ackAddition = async (minutes: number) => {
    unwrap(await $api.POST('/api/additions/{minutes}/ack', { params: { path: { minutes } } }))
  }

  return {
    snapshot, connected, events, history, limits,
    online, phase, remaining, rate, eta, progress, status, steps, additions, total, programLeft, next,
    applySnapshot, pushEvent, setConnected, resync, loadLimits,
    setPower, setPump, setFlow, setManual, start, pause, startRecipe, confirmAlert, saveSettings, ackAddition,
  }
})
