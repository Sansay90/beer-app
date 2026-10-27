<script setup lang="ts">
import type { FermentationRow } from '~/types/recipe'

const rows = defineModel<FermentationRow[]>({ required: true })

const CELSIUS = { style: 'unit', unit: 'celsius', maximumFractionDigits: 1 } as const
const DAYS = { style: 'unit', unit: 'day', unitDisplay: 'short' } as const
const GRID = 'sm:grid sm:grid-cols-[minmax(0,1fr)_8.5rem_8rem_2rem]'
const NAMES = ['Основное брожение', 'Диацетиловая пауза', 'Холодное осветление']

const days = computed(() => rows.value.reduce((a, s) => a + (s.days || 0), 0))

function add() {
  const last = rows.value[rows.value.length - 1]
  rows.value.push(fermentationStep(last ? last.temp : 18, last ? 2 : 7, NAMES[rows.value.length] ?? ''))
}
</script>

<template>
  <RecipeSection title="Брожение" icon="i-lucide-thermometer-snowflake" :summary="days ? `${days.toLocaleString('ru-RU')} дн.` : undefined">
    <template #actions>
      <UButton icon="i-lucide-plus" label="Этап" size="xs" color="neutral" variant="outline" @click="add" />
    </template>

    <RecipeEditorEmpty v-if="!rows.length" text="Температура и длительность этапов: основное брожение, пауза, осветление." />
    <div v-else class="space-y-2">
      <div class="hidden items-center gap-2 px-0.5 text-xs text-dimmed" :class="GRID">
        <span>Этап</span><span class="text-center">Температура</span><span class="text-center">Длительность</span><span />
      </div>
      <div v-for="(s, i) in rows" :key="i" class="flex flex-wrap items-center gap-2" :class="GRID">
        <UInput v-model="s.name" placeholder="Название этапа" size="sm" class="min-w-40 flex-1" />
        <UInputNumber v-model="s.temp" :min="-2" :max="40" :step="0.5" :step-snapping="false" :format-options="CELSIUS" size="sm" aria-label="Температура" />
        <UInputNumber v-model="s.days" :min="0" :step="1" :step-snapping="false" :format-options="DAYS" size="sm" aria-label="Дней" />
        <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="sm" aria-label="Убрать" @click="rows.splice(i, 1)" />
      </div>
    </div>
  </RecipeSection>
</template>
