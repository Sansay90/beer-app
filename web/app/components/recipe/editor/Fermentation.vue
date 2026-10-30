<script setup lang="ts">
// Этапы брожения: температура и когда переходить к следующему — плотность дошла до цели, плотность перестала падать
// (FG) или выдержка столько дней. У «до плотности» и «до FG» дни — примерная подсказка: для графика и напоминания
// замерить; у выдержки — само условие.
import type { FermentationRow } from '~/types/recipe'

const rows = defineModel<FermentationRow[]>({ required: true })
const prefs = usePreferencesStore()

const CELSIUS = { style: 'unit', unit: 'celsius', maximumFractionDigits: 1 } as const
const DAYS = { style: 'unit', unit: 'day', unitDisplay: 'short', maximumFractionDigits: 1 } as const
const GRID = 'sm:grid sm:grid-cols-[minmax(0,1fr)_7.5rem_9.5rem_7rem_7rem_2rem]'
const UNTIL: { value: FermentationRow['until']; label: string }[] = [
  { value: 'gravity', label: 'до плотности' },
  { value: 'fg', label: 'до FG' },
  { value: 'days', label: 'выдержка' },
]
const NAMES = ['Основное брожение', 'Диацетиловая пауза', 'Холодное осветление']

const days = computed(() => rows.value.reduce((a, s) => a + (s.days || 0), 0))
const estimated = computed(() => rows.value.some(s => s.until !== 'days'))
const summary = computed(() => (days.value ? `${estimated.value ? '~' : ''}${fmtNumber(days.value, 1)} дн.` : undefined))

/** Первый этап — до конечной плотности, следующие — выдержка (пауза, холод). */
function add() {
  const last = rows.value[rows.value.length - 1]
  rows.value.push(last
    ? fermentationStep(last.temp, 2, NAMES[rows.value.length] ?? '', 'days')
    : fermentationStep(18, 7, NAMES[0], 'fg'))
}
function setUntil(s: FermentationRow, v: string) {
  s.until = v as FermentationRow['until']
  if (s.until !== 'gravity') s.gravity = null
}
</script>

<template>
  <RecipeSection title="Брожение" icon="i-lucide-thermometer-snowflake" :summary="summary">
    <template #actions>
      <UButton icon="i-lucide-plus" label="Этап" size="xs" color="neutral" variant="outline" @click="add" />
    </template>

    <RecipeEditorEmpty v-if="!rows.length" text="Этапы: температура и когда переходить дальше — по плотности, до конечной плотности или через столько дней." />
    <div v-else class="space-y-2">
      <div class="hidden items-center gap-2 px-0.5 text-xs text-dimmed" :class="GRID">
        <span>Этап</span><span class="text-center">Температура</span><span class="text-center">Переход</span>
        <span class="text-center">Плотность, {{ prefs.gravityUnit === 'plato' ? '°P' : 'SG' }}</span><span class="text-center">Дни</span><span />
      </div>
      <div v-for="(s, i) in rows" :key="i" class="flex flex-wrap items-center gap-2" :class="GRID">
        <UInput v-model="s.name" placeholder="Название этапа" size="sm" class="min-w-40 flex-1" />
        <UInputNumber v-model="s.temp" :min="-2" :max="40" :step="0.5" :step-snapping="false" :format-options="CELSIUS" size="sm" aria-label="Температура" />
        <USelect :model-value="s.until" :items="UNTIL" size="sm" aria-label="Когда переходить дальше" @update:model-value="v => setUntil(s, v as string)" />
        <RecipeEditorGravityInput v-if="s.until === 'gravity'" v-model="s.gravity" label="До какой плотности" />
        <span v-else class="hidden text-center text-sm text-dimmed sm:block">—</span>
        <UInputNumber
          v-model="s.days"
          :min="0"
          :step="1"
          :step-snapping="false"
          :format-options="DAYS"
          size="sm"
          :aria-label="s.until === 'days' ? 'Сколько дней держать' : 'Примерно сколько дней'"
        />
        <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="sm" aria-label="Убрать" @click="rows.splice(i, 1)" />
      </div>
      <p v-if="estimated" class="px-0.5 text-xs text-muted">Дни у «до плотности» и «до FG» — примерные.</p>
    </div>
  </RecipeSection>
</template>
