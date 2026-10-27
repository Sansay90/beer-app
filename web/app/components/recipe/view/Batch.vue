<script setup lang="ts">
// Партия: объём, эффективность и сколько всего засыпи и хмеля.
import type { Recipe } from '~/types'

const props = defineProps<{ recipe: Recipe }>()

const rows = computed(() => {
  const kg = totalKg(props.recipe.fermentables ?? [])
  const grams = (props.recipe.hops ?? []).reduce((a, h) => a + (h.amount ?? 0), 0)
  return [
    { label: 'Объём после кипячения', value: fmtNumber(props.recipe.batch?.volume, 1, ' л') },
    { label: 'Эффективность', value: fmtNumber(props.recipe.batch?.efficiency, 0, ' %') },
    { label: 'Засыпь', value: kg ? fmtNumber(kg, 2, ' кг') : '—' },
    { label: 'Хмель', value: grams ? fmtNumber(grams, 1, ' г') : '—' },
  ]
})
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-5' }">
    <div class="mb-3 text-xs font-medium uppercase tracking-wider text-dimmed">Партия</div>
    <dl class="space-y-1.5 text-sm">
      <div v-for="b in rows" :key="b.label" class="flex justify-between gap-3">
        <dt class="text-muted">{{ b.label }}</dt>
        <dd class="num text-right" :class="b.value === '—' ? 'text-dimmed' : 'text-highlighted'">{{ b.value }}</dd>
      </div>
    </dl>
  </UCard>
</template>
