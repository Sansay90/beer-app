<script setup lang="ts">
// «Сейчас» — текущий шаг варочного дня. Без пивоварни: шаг, что приготовить, что дальше, «Дальше» (запись «step»;
// на последнем шаге — «Дрожжи заданы», веха pitch); справа — таймер шага (если у шага есть время) или поля его
// замеров (не записаны — «Дальше» спрашивает: эти цифры потом не восстановить). Звук здесь же: время шага вышло — сигнал повторяется, пока не нажали «Дальше»; закладка на кипячении
// в свою минуту — сигнал закладки (на пивоварне звучат её события). На подключённой пивоварне: программа партии
// ещё не в ней — загрузить; в ней — «Сейчас» и «Дальше» самой пивоварни, шаги она ведёт сама.
import type { BrewDetail } from '~/types'
import type { BrewDayView } from '~/utils/brewday'

const props = defineProps<{ brew: BrewDetail; view: BrewDayView; connected: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const brewery = useBreweryStore()
const { $api } = useNuxtApp()
const { exec, pending } = useCommand()
const confirm = useConfirm()
const sound = useSound()
const now = useNow({ interval: 1000 })             // секунды нужны только таймеру — карточка живёт, пока идёт день

const step = computed(() => props.view.steps[props.view.current]!)
const next = computed(() => props.view.steps[props.view.current + 1] ?? null)
const measures = computed(() => lastMeasures(props.brew.entries))
const loaded = computed(() => brewery.snapshot?.deviceRecipe?.brewId === props.brew.id)
const programActive = computed(() => brewery.phase.running || brewery.phase.paused)
// пивоварня: программа ещё не загружена или ждёт запуска — пока её шаги не идут, рукой доходим до старта
const breweryIdle = computed(() => props.connected && !props.view.byBrewery)
// справа есть что показать (таймер, замеры, «Дальше» пивоварни) — иначе карточка шага на всю ширину
const aside = computed(() => !!step.value.minutes || step.value.measures.length > 0 || (breweryIdle.value && loaded.value))

const remaining = computed(() => stepRemaining(step.value, now.value.getTime() / 1000))
const over = computed(() => remaining.value != null && remaining.value <= 0)
const progress = computed(() => (remaining.value != null && step.value.minutes
  ? Math.min(100, Math.max(0, 100 * (1 - remaining.value / (step.value.minutes * 60))))
  : null))

// время шага вышло — сигнал, пока не перешли дальше
const REPEAT_MS = 4_000
let repeat: ReturnType<typeof setInterval> | undefined
watch(over, (ring) => {
  clearInterval(repeat)
  if (ring) {
    sound.play('end')
    repeat = setInterval(() => sound.play('end'), REPEAT_MS)
  }
}, { immediate: true })
onBeforeUnmount(() => clearInterval(repeat))
// закладки кипячения — по таймеру шага: пришла минута закладки — один сигнал (вернулись позже минуты — молча)
const sounded = new Set<number>()
watch(() => props.view.current, () => sounded.clear())
watch(remaining, (left) => {
  if (step.value.kind !== 'boil' || left == null || !step.value.minutes) return
  const elapsed = step.value.minutes * 60 - left
  for (const a of step.value.additions) {
    const at = (step.value.minutes - a.minutes) * 60
    if (sounded.has(a.minutes) || elapsed < at) continue
    sounded.add(a.minutes)
    if (elapsed < at + 60) sound.play('addition')
  }
})

async function advance() {
  const missing = step.value.measures.filter(m => !measures.value.get(m))
  if (missing.length && !await confirm({
    title: 'Замеры не записаны',
    description: `${missing.map(m => ENTRY_KINDS[m].short ?? ENTRY_KINDS[m].label).join(', ')} — поля на этом шаге пустые. Идти дальше без записи?`,
    confirmLabel: 'Дальше без записи',
    confirmIcon: 'i-lucide-arrow-right',
  })) return
  const body = step.value.kind === 'pitch'
    ? { kind: 'pitch' as const }
    : { kind: 'step' as const, value: props.view.current + 1 }
  if (await exec(() => $api('/api/brews/{bid}/entries', { method: 'POST', path: { bid: props.brew.id }, body }))) emit('changed')
}
const uploadHint = computed(() => (!brewery.online ? 'Пивоварня не в сети' : programActive.value ? 'Программа идёт — заменить можно после её окончания' : 'Паузы, кипячение и закладки рецепта партии'))
async function upload() {
  await exec(() => $api('/api/brews/{bid}/upload', { method: 'POST', path: { bid: props.brew.id } }), 'Программа партии в пивоварне')
}
</script>

<template>
  <!-- пивоварня ведёт шаги: её «Сейчас» и «Дальше» -->
  <div v-if="view.byBrewery" class="grid gap-4 sm:gap-6 lg:grid-cols-2">
    <BrewNowCard />
    <BrewNextCard />
  </div>

  <!-- две карточки, как «Варка» и «Журнал» ниже: слева шаг, справа таймер или замеры -->
  <div v-else class="grid gap-4 sm:gap-6" :class="aside && 'xl:grid-cols-[minmax(0,1fr)_24rem]'">
    <UCard :ui="{ body: 'p-5 sm:p-6' }" class="ring-1 ring-primary/40">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-xl font-semibold text-highlighted">Сейчас</h2>
          <div class="flex flex-wrap items-center gap-2 text-sm text-muted">
            <UBadge :label="`шаг ${view.current + 1} из ${view.steps.length}`" color="primary" variant="subtle" />
            <span v-if="step.at != null">начат в {{ fmtTime(step.at) }}</span>
          </div>
        </div>
      </template>
      <div class="text-3xl font-semibold text-highlighted">
        {{ step.name }}<span v-if="stepLine(step)" class="ms-3 text-xl font-normal whitespace-nowrap text-muted">{{ stepLine(step) }}</span>
      </div>
      <ul v-if="step.details.length" class="mt-2 space-y-1 text-base text-toned">
        <li v-for="d in step.details" :key="d">{{ d }}</li>
      </ul>
      <ol v-if="step.additions.length" class="mt-3 space-y-1">
        <li v-for="a in step.additions" :key="a.minutes" class="flex items-baseline gap-3 text-base">
          <span class="num w-16 shrink-0 font-semibold text-highlighted">{{ additionWhen(a.minutes, step.minutes) }}</span>
          <span class="text-toned">{{ a.label }}</span>
        </li>
      </ol>
      <div v-if="next" class="mt-3 text-base text-muted">
        дальше — <span class="text-highlighted">{{ next.name }}</span><template v-if="stepLine(next)"> {{ stepLine(next) }}</template>
      </div>

      <!-- пивоварня: программу надо загрузить — пока она в простое, шаги до старта проходим рукой -->
      <div v-if="breweryIdle && !loaded" class="mt-4 flex flex-wrap items-center gap-3 rounded-lg bg-elevated/60 px-4 py-3">
        <UIcon name="i-lucide-plug" class="size-5 text-primary" />
        <span class="min-w-0 flex-1 text-base text-toned">Программа партии ещё не в пивоварне</span>
        <UBadge :color="brewery.status.tone" variant="soft" :label="brewery.status.label" />
        <UTooltip :text="uploadHint">
          <UButton label="Загрузить" icon="i-lucide-upload" size="lg" :loading="pending" :disabled="!brewery.online || programActive" @click="upload" />
        </UTooltip>
      </div>

      <UButton
        :label="step.kind === 'pitch' ? 'Дрожжи заданы' : next ? `Дальше: ${next.name}` : 'Готово'"
        :icon="step.kind === 'pitch' ? 'i-lucide-microscope' : 'i-lucide-check'"
        size="xl"
        class="mt-5"
        :class="(!step.minutes || over) && 'call-pulse'"
        :loading="pending"
        @click="advance"
      />
    </UCard>

    <UCard v-if="step.minutes" :ui="{ body: 'p-5 sm:p-6' }" class="h-full">
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-xl font-semibold text-highlighted">Таймер</h2>
          <span class="flex items-center gap-1.5 text-sm text-muted"><UIcon name="i-lucide-bell" class="size-4" />{{ over ? 'время вышло' : 'напомним' }}</span>
        </div>
      </template>
      <div class="num text-6xl font-semibold tracking-tight" :class="over ? 'text-warning' : 'text-highlighted'">
        {{ remaining != null ? (over ? '+' : '') + fmtDuration(Math.abs(remaining)) : fmtMinutes(step.minutes) }}
      </div>
      <UProgress v-if="progress != null" :model-value="Math.round(progress)" size="sm" :color="over ? 'warning' : 'primary'" class="mt-3" />
      <div v-if="step.at != null && step.ends != null" class="num mt-2 text-sm text-muted">
        {{ fmtTime(step.at) }} → {{ fmtTime(step.ends) }}
      </div>
    </UCard>
    <!-- замеры шага (у шагов с таймером замеров нет) -->
    <UCard v-else-if="step.measures.length" :ui="{ body: 'p-5 sm:p-6' }" class="h-full">
      <template #header>
        <h2 class="text-xl font-semibold text-highlighted">Замеры</h2>
      </template>
      <div class="flex flex-col gap-3">
        <BrewDayMeasureInput v-for="m in step.measures" :key="m" :brew-id="brew.id" :kind="m" :last="measures.get(m)" @saved="emit('changed')" />
      </div>
    </UCard>
    <BrewNextCard v-else-if="breweryIdle && loaded" class="h-full" />
  </div>
</template>
