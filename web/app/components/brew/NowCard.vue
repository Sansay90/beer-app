<script setup lang="ts">
const brewery = useBreweryStore()

const stepLabel = computed(() => {
  const { snapshot: s, phase, steps } = brewery
  if (!s) return ''
  if (s.mode === 'manual' && (phase.running || phase.paused)) return 'Ручной режим'
  const cur = steps[phase.step - 1]
  return phase.inRecipe && cur ? `Шаг ${cur.index} из ${steps.length} · ${cur.name}` : ''
})

const stats = computed(() => {
  const { snapshot: s, phase, remaining, eta, rate, programLeft } = brewery
  const t = s?.timer
  const active = phase.running || phase.paused

  const stepLeft = !t || t.minutes == null || !active
    ? { value: '—', hint: '' }
    : t.counting || phase.paused
      ? { value: fmtDuration(remaining), hint: '' }
      : { value: fmtMinutes(t.minutes), hint: 'начнётся у цели' }

  const toTarget = !phase.heating
    ? { value: '—', hint: '' }
    : eta == null
      ? { value: '…', hint: 'считаем скорость' }
      : { value: `≈ ${fmtMinutes(Math.max(1, Math.round(eta / 60)))}`, hint: rate ? `${fmtTemp(rate)} °C/мин` : '' }

  const program = programLeft == null
    ? { value: '—', hint: '' }
    : { value: fmtDuration(programLeft), hint: 'без учёта нагрева' }

  const e = brewery.snapshot?.energy
  const energy = !e || (!e.wh && !e.watts)
    ? { value: '—', hint: 'оценка' }
    : { value: fmtEnergy(e.wh), hint: e.watts ? `ТЭН ~${e.watts} W · оценка` : 'оценка ±20–30 %' }

  return [
    { label: 'Осталось шага', ...stepLeft },
    { label: 'До цели', ...toTarget },
    { label: 'Вся программа', ...program },
    { label: 'Электричество', ...energy },
  ]
})
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-6' }">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <UBadge
        :color="brewery.status.tone"
        variant="subtle"
        size="lg"
        :icon="brewery.status.icon"
        :label="brewery.status.label"
        :ui="{ leadingIcon: brewery.status.live ? 'soft-pulse' : '' }"
      />
      <span class="truncate text-sm font-medium text-muted">{{ stepLabel }}</span>
    </div>

    <div class="mt-5 flex flex-wrap items-end gap-x-6 gap-y-1">
      <div
        class="num text-[clamp(4.5rem,9vw,7.5rem)] font-semibold leading-[0.9] tracking-tight transition-opacity"
        :class="brewery.online ? 'text-highlighted' : 'text-dimmed opacity-50'"
      >
        {{ fmtTemp(brewery.snapshot?.temp) }}<span class="ml-1 align-top text-[0.32em] font-medium text-muted">°C</span>
      </div>
      <div v-if="brewery.snapshot && !brewery.online" class="pb-2 text-sm text-muted">последнее значение</div>
      <div v-else-if="brewery.snapshot?.stepTarget != null" class="num flex items-center gap-2 pb-2 text-2xl text-muted">
        <UIcon name="i-lucide-arrow-right" class="size-6" />
        {{ fmtTemp(brewery.snapshot.stepTarget) }} °C
      </div>
    </div>

    <UProgress
      v-if="brewery.progress != null"
      :model-value="Math.round(brewery.progress * 100)"
      :color="brewery.phase.heating ? 'primary' : 'success'"
      size="md"
      class="mt-6"
    />

    <div class="mt-6 grid grid-cols-2 gap-4 border-t border-default pt-5 sm:grid-cols-4">
      <div v-for="s in stats" :key="s.label" class="min-w-0">
        <div class="text-xs font-medium uppercase tracking-wider text-dimmed">{{ s.label }}</div>
        <div class="num mt-1 truncate text-2xl font-semibold text-highlighted">{{ s.value }}</div>
        <div class="truncate text-xs text-muted">{{ s.hint }}&nbsp;</div>
      </div>
    </div>
  </UCard>
</template>
