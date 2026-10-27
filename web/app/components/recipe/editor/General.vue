<script setup lang="ts">
// Название, стиль, партия и описание; под ними — показатели, посчитанные по ингредиентам.
import type { RecipeDraft } from '~/types/recipe'
import type { RecipeCalc } from '~/utils/calc'

const draft = defineModel<RecipeDraft>({ required: true })
const props = defineProps<{ calc: RecipeCalc | null }>()

const prefs = usePreferencesStore()

const stats = computed(() => {
  const c = props.calc
  const n = (v: number | null | undefined, digits = 0) => (v == null ? '—' : v.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits }))
  return [
    { label: 'OG', value: fmtGravity(c?.og, prefs.gravityUnit) },
    { label: 'FG', value: fmtGravity(c?.fg, prefs.gravityUnit), note: c?.og && c.defaultAttenuation ? `сбраживание ${c.attenuation} %` : undefined },
    { label: 'ABV', value: c?.abv == null ? '—' : `${n(c.abv, 1)} %` },
    { label: 'IBU', value: n(c?.ibu) },
    { label: 'Цвет', value: c?.ebc == null ? '—' : `${n(c.ebc)} EBC` },
  ]
})
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-5 space-y-5' }">
    <UInput v-model="draft.name" placeholder="Название рецепта" size="xl" variant="none" class="w-full" :ui="{ base: 'px-0 text-2xl font-semibold text-highlighted' }" />
    <div class="grid gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <UFormField label="Стиль">
        <RecipeStylePicker v-model="draft.style" />
      </UFormField>
      <UFormField label="Объём после кипячения" hint="л">
        <UInputNumber v-model="draft.batch.volume" :min="1" :step="1" :step-snapping="false" :increment="false" :decrement="false" :format-options="{ maximumFractionDigits: 1 }" placeholder="—" class="w-full" />
      </UFormField>
      <UFormField label="Эффективность" hint="%">
        <UInputNumber v-model="draft.batch.efficiency" :min="1" :max="100" :step="1" :step-snapping="false" :increment="false" :decrement="false" placeholder="—" class="w-full" />
      </UFormField>
    </div>
    <UFormField label="Описание">
      <UTextarea v-model="draft.notes" placeholder="Каким получится пиво: вкус, аромат, особенности рецепта. Абзацы — через пустую строку." autoresize :rows="3" :maxrows="14" class="w-full" />
    </UFormField>
    <div>
      <div class="mb-2 text-sm font-medium text-default">Расчёт по ингредиентам</div>
      <dl class="grid grid-cols-3 gap-4 rounded-lg bg-elevated/50 px-4 py-3 sm:grid-cols-5">
        <div v-for="s in stats" :key="s.label">
          <dt class="text-xs font-medium tracking-wider text-dimmed">{{ s.label }}</dt>
          <dd class="num mt-0.5 font-semibold" :class="s.value === '—' ? 'text-dimmed' : 'text-highlighted'">{{ s.value }}</dd>
          <dd v-if="s.note" class="text-[11px] text-dimmed">{{ s.note }}</dd>
        </div>
      </dl>
    </div>
  </UCard>
</template>
