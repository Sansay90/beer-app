<script setup lang="ts">
// Сводка сбоку: бокал, рамки стиля с ползунками подгонки ингредиентов, итоги засыпи, хмеля и программы.
import type { RecipeDraft } from '~/types/recipe'
import type { FitBase, RecipeCalc } from '~/utils/calc'

const draft = defineModel<RecipeDraft>({ required: true })
defineProps<{ calc: RecipeCalc | null }>()

const style = computed(() => styleByCode(draft.value.style?.code))
const canAdjust = computed(() => adjustable(draft.value))

// ползунки рамок стиля: подгонка от снимка ингредиентов на начало перетаскивания
let fitFrom: FitBase | null = null
function adjust(key: 'og' | 'fg' | 'ibu' | 'ebc', value: number) {
  const d = draft.value
  fitFrom ??= fitBase(d)
  if (key === 'og') fitOg(d, fitFrom, value)
  else if (key === 'fg') fitFg(d, value)
  else if (key === 'ibu') fitIbu(d, fitFrom, value)
  else fitEbc(d, fitFrom, value)
}

const totals = computed(() => {
  const d = draft.value
  const kg = totalKg(d.fermentables)
  const hops = d.hops.reduce((a, h) => a + (h.amount ?? 0), 0)
  return [
    { label: 'Засыпь', value: kg ? `${kg.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} кг` : '—' },
    { label: 'Хмель', value: hops ? `${hops.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} г` : '—' },
    { label: 'Программа', value: programSummary(d) },
  ]
})
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-5' }">
    <div class="flex items-center gap-3">
      <RecipeGlass :ebc="calc?.ebc" :style-code="draft.style?.code" class="h-14" />
      <div class="min-w-0">
        <div class="truncate font-semibold text-highlighted">{{ draft.name || 'Без названия' }}</div>
        <div class="truncate text-sm text-muted">{{ styleLabel(draft.style) }}</div>
      </div>
    </div>
    <USeparator class="my-4" />
    <RecipeStyleRanges
      :bjcp="style"
      :custom="!!draft.style && !draft.style.code"
      :og="calc?.og"
      :fg="calc?.fg"
      :ibu="calc?.ibu"
      :ebc="calc?.ebc"
      :adjustable="canAdjust"
      @adjust="adjust"
      @commit="fitFrom = null"
    />
    <USeparator class="my-4" />
    <dl class="space-y-1.5 text-sm">
      <div v-for="t in totals" :key="t.label" class="flex justify-between gap-3">
        <dt class="text-muted">{{ t.label }}</dt>
        <dd class="num text-right text-highlighted">{{ t.value }}</dd>
      </div>
    </dl>
  </UCard>
</template>
