<script setup lang="ts">
import type { HopRow } from '~/types/recipe'

const rows = defineModel<HopRow[]>({ required: true })
const props = defineProps<{ boilMinutes: number | null; volume: number | null }>()

const USES = options(HOP_USES)
const GRID = 'sm:grid sm:grid-cols-[minmax(0,1fr)_4.5rem_4.5rem_17rem_2rem]'

const total = computed(() => rows.value.reduce((a, h) => a + (h.amount ?? 0), 0))
const summary = computed(() => {
  if (!total.value) return undefined
  const perLitre = props.volume ? ` · ${(total.value / props.volume).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} г/л` : ''
  return `${total.value.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} г${perLitre}`
})

/** Первый хмель — на горечь, с начала кипячения; следующие — поздние. */
function add() {
  rows.value.push(newHop(rows.value.length ? 10 : props.boilMinutes ?? 60))
}
</script>

<template>
  <RecipeSection title="Хмель" icon="i-lucide-hop" :summary="summary">
    <template #actions>
      <UButton icon="i-lucide-plus" label="Добавить" size="xs" color="neutral" variant="outline" @click="add" />
    </template>

    <RecipeEditorEmpty v-if="!rows.length" text="Сорт, альфа-кислоты с пачки, граммы и когда закладывать." />
    <div v-else class="space-y-2">
      <div class="hidden items-center gap-2 px-0.5 text-xs text-dimmed" :class="GRID">
        <span>Сорт</span><span class="text-center">α, %</span><span class="text-center">г</span>
        <span>Когда</span><span />
      </div>
      <div v-for="(h, i) in rows" :key="i" class="flex flex-wrap items-center gap-2" :class="GRID">
        <UInput v-model="h.name" placeholder="Magnum, Saaz, Citra…" size="sm" class="min-w-40 flex-1" :ui="{ leading: 'ps-2' }">
          <template #leading>
            <UIcon name="i-lucide-hop" class="size-4 text-success" />
          </template>
        </UInput>
        <UInputNumber v-model="h.alpha" :min="0" :max="30" :step="0.1" :step-snapping="false" :format-options="{ maximumFractionDigits: 1 }" :increment="false" :decrement="false" placeholder="—" size="sm" class="w-18 sm:w-auto" aria-label="Альфа-кислоты, %" />
        <UInputNumber v-model="h.amount" :min="0" :step="1" :step-snapping="false" :format-options="{ maximumFractionDigits: 1 }" :increment="false" :decrement="false" placeholder="—" size="sm" class="w-18 sm:w-auto" aria-label="Масса, г" />
        <RecipeEditorWhen v-model:use="h.use" v-model:minutes="h.minutes" v-model:day="h.day" :items="USES" class="w-68 sm:w-auto" />
        <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="sm" aria-label="Убрать" @click="rows.splice(i, 1)" />
      </div>
    </div>
  </RecipeSection>
</template>
