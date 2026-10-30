<script setup lang="ts">
// Брожение партии (после варочного дня): где партия сейчас (день N из M; у этапов по плотности — примерно), замеры
// сегодня — плотность и температура, с этапа «до FG», на последнем и после плана ещё FG (поля пустые, прошлое
// значение подсказкой), график против плана (FermentGraph.vue). Идёт этап «до плотности» или «до FG» и его условие
// наступило — цель достигнута, брожение замедлилось до цели или плотность встала — «пора» с кнопкой следующего
// этапа (fermentAdvice); идёт выдержка, а плотность держится двое суток — «похоже, брожение закончилось». Встала на
// тёплом этапе заметно выше плана — «похоже, застряло»: что сделать, без кнопки следующего этапа (охлаждать
// недобродившее — ошибка; начать этап всё равно можно с таймлайна). Разлито или вылито — замеров и подсказок нет.
// Этапы с датами, сухое охмеление и розлив — в таймлайне партии (day/Timeline.vue). Отсчёт — от задачи дрожжей,
// её нет — от дня варки. Нет ни плана, ни замеров — карточки нет.
import type { BrewDetail } from '~/types'

const props = defineProps<{ brew: BrewDetail }>()
const emit = defineEmits<{ changed: []; stage: [index: number] }>()
const prefs = usePreferencesStore()
const now = useNow({ interval: 60_000 })

const t = computed(() => now.value.getTime() / 1000)
const start = computed(() => props.brew.fermentStart ?? props.brew.startedAt)
// разлито или вылито — брожение позади (plan.closed)
const plan = computed(() => fermentPlan(props.brew.plan, start.value, t.value, props.brew.packagedAt, props.brew.entries, props.brew.dumpedAt))
const advice = computed(() => (plan.value.closed ? null : fermentAdvice(plan.value, props.brew.plan, props.brew.entries)))
// «похоже, закончилось» — когда идёт выдержка, по замерам с её начала (у «до плотности» и «до FG» — их «пора»)
const calm = computed(() => (plan.value.closed ? null : fermentCalm(plan.value, props.brew.plan, props.brew.entries)))
// встала выше плана — «застряло» вместо «пора» и «закончилось»
const stuck = computed(() => (advice.value?.why === 'stuck' ? advice.value : calm.value?.stuck ? calm.value : null))
// следующий этап — только начиная со второго: первый начинается с задачи дрожжей, «начать» его нельзя
const nextStage = computed(() => (plan.value.next != null && plan.value.next >= 1 ? plan.value.stages[plan.value.next] : null))
const measures = computed(() => lastMeasures(props.brew.entries))
// конечная плотность — с этапа «до FG», на последнем этапе плана или когда план пройден
const final = computed(() => plan.value.stages.length > 0 && (plan.value.current >= plan.value.stages.length - 1
  || plan.value.finished || plan.value.stages.slice(0, plan.value.current + 1).some(s => s.until === 'fg')))
const hasData = computed(() => props.brew.entries.filter(e => ['og', 'gravity', 'fg', 'temp'].includes(e.kind)).length >= 2)
const shown = computed(() => plan.value.stages.length || hasData.value)

const day = computed(() => Math.floor((t.value - start.value) / 86400) + 1)
const headline = computed(() => {
  if (props.brew.dumpedAt) return `Вылито ${fmtDay(props.brew.dumpedAt)}`
  if (props.brew.packagedAt) return `Разлито ${fmtDay(props.brew.packagedAt)}`
  if (day.value < 1) return `Начало — ${fmtDay(start.value)}`
  return plan.value.days ? `День ${day.value} из ${plan.value.estimated ? '~' : ''}${fmtNumber(plan.value.days, 1)}` : `День ${day.value}`
})
// полоса по дням плана; пока последний этап не позади — не до конца (у этапов по плотности дни — прикидка);
// вылитой — не нужна
const progress = computed(() => {
  if (props.brew.dumpedAt) return null
  if (props.brew.packagedAt) return 100
  return plan.value.days ? Math.min(plan.value.finished ? 100 : 99, Math.max(0, ((t.value - start.value) / (plan.value.days * 86400)) * 100)) : null
})
const calmDays = computed(() => (calm.value ? Math.floor(calm.value.days) : 0))

// «пора»: что случилось и что дальше
const adviceNext = computed(() => (advice.value ? plan.value.stages[advice.value.stage + 1] ?? null : null))
const adviceView = computed(() => {
  const a = advice.value
  if (!a || a.why === 'stuck') return null
  const unit = prefs.gravityUnit
  const st = plan.value.stages[a.stage]!
  const n = adviceNext.value
  const then = n
    ? ` Дальше — «${n.name}»: ${fmtNumber(n.temp, 1)} °C, ${stageCondition({ until: n.until, gravity: n.target, days: n.days }, unit).replace(/\.$/, '')}.`
    : ' Можно переливать и разливать.'
  const value = fmtGravity(a.value, unit)
  if (a.why === 'target') {
    return { title: n ? `Пора: «${n.name}»` : 'Брожение по плану закончено', text: `Плотность ${value} — цель ${fmtGravity(st.target, unit)} достигнута.${then}` }
  }
  if (a.why === 'slow') {
    return { title: 'Брожение замедлилось', text: `Плотность ${value} почти не падает, а цель ${fmtGravity(st.target, unit)} не наступила.${then}` }
  }
  return { title: 'Брожение закончилось', text: `Плотность ${value} не меняется двое суток.${then}` }
})
const stuckText = computed(() => {
  const s = stuck.value
  if (!s) return ''
  const unit = prefs.gravityUnit
  const fg = fermentFinal(plan.value, props.brew.plan)
  return `Плотность ${fmtGravity(s.value, unit)} не меняется двое суток, а по плану — ${fmtGravity(fg, unit)}. Поднимите температуру на 2–3 °C и взболтайте дрожжи.`
})
</script>

<template>
  <UCard v-if="shown" :ui="{ body: 'p-5 sm:p-6' }">
    <template #header>
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h2 class="text-xl font-semibold text-highlighted">Брожение</h2>
        <span class="num text-base text-toned">{{ headline }}</span>
      </div>
    </template>

    <UProgress v-if="progress != null && plan.stages.length" :model-value="progress" size="sm" class="mb-5" />

    <div v-if="!plan.closed" class="mb-5 flex flex-wrap items-end gap-x-6 gap-y-3">
      <span class="pb-2.5 text-sm font-medium text-highlighted">Сегодня</span>
      <BrewDayMeasureInput :brew-id="brew.id" kind="gravity" :last="measures.get('gravity')" fresh @saved="emit('changed')" />
      <BrewDayMeasureInput :brew-id="brew.id" kind="temp" :last="measures.get('temp')" fresh @saved="emit('changed')" />
      <BrewDayMeasureInput v-if="final" :brew-id="brew.id" kind="fg" :last="measures.get('fg')" fresh @saved="emit('changed')" />
    </div>

    <UAlert
      v-if="stuck"
      icon="i-lucide-triangle-alert"
      color="warning"
      variant="subtle"
      title="Похоже, брожение застряло"
      :description="stuckText"
      class="mb-5"
    />
    <UAlert
      v-else-if="adviceView"
      icon="i-lucide-bell-ring"
      color="primary"
      variant="subtle"
      :title="adviceView.title"
      :description="adviceView.text"
      :actions="adviceNext ? [{ label: `Начать «${adviceNext.name}»`, icon: 'i-lucide-arrow-right', onClick: () => emit('stage', advice!.stage + 1) }] : []"
      class="mb-5"
    />
    <UAlert
      v-else-if="calm"
      icon="i-lucide-circle-check"
      color="success"
      variant="subtle"
      title="Похоже, брожение закончилось"
      :description="`Плотность ${fmtGravity(calm.value, prefs.gravityUnit)} не меняется ${calmDays} ${plural(calmDays, 'сутки', 'суток', 'суток')}.${nextStage ? '' : ' Можно разливать.'}`"
      :actions="nextStage ? [{ label: `Начать «${nextStage.name}»`, icon: 'i-lucide-arrow-right', onClick: () => emit('stage', plan.next!) }] : []"
      class="mb-5"
    />

    <BrewFermentGraph
      :entries="brew.entries"
      :stages="plan.stages"
      :dry-hops="plan.dryHops"
      :og="brew.plan?.og"
      :fg="brew.plan?.fg"
      :start="start"
      :now="t"
      :packaged-at="brew.packagedAt"
      :dumped-at="brew.dumpedAt"
      class="mt-2"
    />
  </UCard>
</template>
