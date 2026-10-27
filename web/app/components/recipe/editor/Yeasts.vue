<script setup lang="ts">
import type { YeastRow } from '~/types/recipe'

const rows = defineModel<YeastRow[]>({ required: true })

const FORMS = options(YEAST_FORMS)
const GRID = 'sm:grid sm:grid-cols-[minmax(0,1fr)_7rem_10.5rem_5.5rem_2rem]'
</script>

<template>
  <RecipeSection title="Дрожжи" icon="i-lucide-microscope">
    <template #actions>
      <UButton icon="i-lucide-plus" label="Добавить" size="xs" color="neutral" variant="outline" @click="rows.push(newYeast())" />
    </template>

    <RecipeEditorEmpty v-if="!rows.length" text="Штамм, количество и степень сбраживания." />
    <div v-else class="space-y-2">
      <div class="hidden items-center gap-2 px-0.5 text-xs text-dimmed" :class="GRID">
        <span>Штамм</span><span>Форма</span><span>Сколько</span><span class="text-center">Сбраж., %</span><span />
      </div>
      <div v-for="(y, i) in rows" :key="i" class="flex flex-wrap items-center gap-2" :class="GRID">
        <UInput v-model="y.name" placeholder="Fermentis US-05, Lallemand Nottingham…" size="sm" class="min-w-40 flex-1" />
        <USelect v-model="y.form" :items="FORMS" size="sm" class="w-28 sm:w-auto" aria-label="Форма" />
        <UFieldGroup size="sm" class="w-42 sm:w-auto">
          <UInputNumber v-model="y.amount" :min="0" :step="1" :step-snapping="false" :format-options="{ maximumFractionDigits: 1 }" :increment="false" :decrement="false" placeholder="—" class="min-w-0 flex-1" aria-label="Количество" />
          <USelect v-model="y.unit" :items="ADDITION_UNITS" class="w-20" aria-label="Единица" />
        </UFieldGroup>
        <UInputNumber v-model="y.attenuation" :min="0" :max="100" :step="1" :step-snapping="false" :increment="false" :decrement="false" placeholder="—" size="sm" class="w-20 sm:w-auto" aria-label="Степень сбраживания, %" />
        <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="sm" aria-label="Убрать" @click="rows.splice(i, 1)" />
      </div>
    </div>
  </RecipeSection>
</template>
