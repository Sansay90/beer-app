<script setup lang="ts">
import type { FermentableRow, KindOption } from '~/types/recipe'

const rows = defineModel<FermentableRow[]>({ required: true })

const KINDS: KindOption<FermentableRow['kind']>[] = [
  { value: 'grain', label: FERMENTABLE_KINDS.grain, icon: 'i-lucide-wheat', tint: 'text-amber-500 dark:text-amber-400' },
  { value: 'adjunct', label: FERMENTABLE_KINDS.adjunct, icon: 'i-lucide-bean', tint: 'text-lime-600 dark:text-lime-400' },
  { value: 'sugar', label: FERMENTABLE_KINDS.sugar, icon: 'i-lucide-candy', tint: 'text-pink-500 dark:text-pink-400' },
  { value: 'extract', label: FERMENTABLE_KINDS.extract, icon: 'i-lucide-beaker', tint: 'text-orange-500 dark:text-orange-400' },
]
const USES = options(FERMENTABLE_USES)
const GRID = 'sm:grid sm:grid-cols-[2rem_minmax(0,1fr)_5.5rem_4.5rem_3rem_17rem_2rem]'

const total = computed(() => totalKg(rows.value))
const fmtKg = (kg: number) => `${kg.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} кг`
</script>

<template>
  <RecipeSection title="Засыпь" icon="i-lucide-wheat" :summary="total ? fmtKg(total) : undefined">
    <template #actions>
      <UButton icon="i-lucide-plus" label="Добавить" size="xs" color="neutral" variant="outline" @click="rows.push(newFermentable())" />
    </template>

    <RecipeEditorEmpty v-if="!rows.length" text="Солод, несоложёное, сахар — с массой и цветом." />
    <div v-else class="space-y-2">
      <div class="hidden items-center gap-2 px-0.5 text-xs text-dimmed" :class="GRID">
        <span /><span>Название</span><span class="text-center">кг</span><span class="text-center">EBC</span>
        <span class="text-right">%</span><span>Когда</span><span />
      </div>
      <div v-for="(f, i) in rows" :key="i" class="flex flex-wrap items-center gap-2" :class="GRID">
        <RecipeEditorKindButton v-model="f.kind" :options="KINDS" />
        <UInput v-model="f.name" placeholder="Pilsner, Munich, Caramunich…" size="sm" class="min-w-40 flex-1" />
        <UInputNumber v-model="f.amount" :min="0" :step="0.1" :step-snapping="false" :format-options="{ maximumFractionDigits: 3 }" :increment="false" :decrement="false" placeholder="—" size="sm" class="w-22 sm:w-auto" aria-label="Масса, кг" />
        <UInputNumber v-model="f.ebc" :min="0" :step="1" :step-snapping="false" :format-options="{ maximumFractionDigits: 1 }" :increment="false" :decrement="false" placeholder="—" size="sm" class="w-18 sm:w-auto" aria-label="Цвет, EBC" />
        <span class="num w-12 text-right text-sm text-muted sm:w-auto">{{ share(f.amount, total)?.toFixed(0) ?? '—' }}</span>
        <RecipeEditorWhen v-model:use="f.use" v-model:minutes="f.minutes" :items="USES" class="w-68 sm:w-auto" />
        <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="sm" aria-label="Убрать" @click="rows.splice(i, 1)" />
      </div>
    </div>
  </RecipeSection>
</template>
