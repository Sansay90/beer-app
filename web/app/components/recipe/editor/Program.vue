<script setup lang="ts">
// Программа пивоварни: паузы затирания и кипячение. Закладки на кипячении здесь только видны —
// задаются в хмеле, засыпи и «Другом» (use = кипячение).
import type { Limits } from '~/types'
import type { RecipeDraft } from '~/types/recipe'

const draft = defineModel<RecipeDraft>({ required: true })
const props = defineProps<{ limits: Limits }>()

const CELSIUS = { style: 'unit', unit: 'celsius', maximumFractionDigits: 1 } as const
const MINUTES = { style: 'unit', unit: 'minute', unitDisplay: 'short' } as const
const GRID = 'sm:grid sm:grid-cols-[1.75rem_minmax(0,1fr)_8.5rem_8rem_8rem_6rem]'

const watts = computed(() => wattOptions(props.limits))
const maxWatts = computed(() => watts.value[0]!.value)
const steps = computed(() => programOf(draft.value, props.limits.boilTemp))
const groups = computed(() => boilGroups(draft.value))
const full = computed(() => steps.value.length >= props.limits.maxSteps)

function addPause() {
  const last = draft.value.mash[draft.value.mash.length - 1]
  draft.value.mash.push(mashStep(last?.watts ?? maxWatts.value, last ? Math.min(last.temp + 6, 78) : 66, last ? 10 : 60))
}

function move(i: number, delta: number) {
  const mash = draft.value.mash
  const j = i + delta
  if (j < 0 || j >= mash.length) return
  ;[mash[i], mash[j]] = [mash[j]!, mash[i]!]
}

function setBoil(on: boolean) {
  draft.value.boil = on ? { minutes: 60, watts: maxWatts.value } : null
}
</script>

<template>
  <RecipeSection title="Затирание и кипячение" icon="i-lucide-thermometer" :summary="programSummary(draft)">
    <template #actions>
      <UButton icon="i-lucide-plus" label="Пауза" size="xs" color="neutral" variant="outline" :disabled="full" @click="addPause" />
    </template>

    <RecipeProfile v-if="steps.length" :steps="steps" :groups="groups" class="mb-5" />

    <div class="space-y-2">
      <div class="hidden items-center gap-2 px-0.5 text-xs text-dimmed" :class="GRID">
        <span /><span>Шаг</span><span class="text-center">Температура</span><span class="text-center">Длительность</span>
        <span>Мощность</span><span />
      </div>

      <div v-for="(s, i) in draft.mash" :key="i" class="flex flex-wrap items-center gap-2" :class="GRID">
        <span class="num grid size-7 place-items-center rounded-full bg-primary/10 text-xs font-semibold text-primary">{{ i + 1 }}</span>
        <UInput v-model="s.name" :placeholder="`Пауза ${i + 1}`" size="sm" class="min-w-40 flex-1" />
        <UInputNumber v-model="s.temp" :min="limits.minTemp" :max="limits.maxTemp" :step="0.5" :step-snapping="false" :format-options="CELSIUS" size="sm" aria-label="Температура" />
        <UInputNumber v-model="s.minutes" :min="1" :step="1" :format-options="MINUTES" size="sm" aria-label="Длительность" />
        <USelect v-model="s.watts" :items="watts" size="sm" aria-label="Мощность" />
        <div class="flex justify-end">
          <UButton icon="i-lucide-arrow-up" color="neutral" variant="ghost" size="sm" :disabled="i === 0" aria-label="Выше" @click="move(i, -1)" />
          <UButton icon="i-lucide-arrow-down" color="neutral" variant="ghost" size="sm" :disabled="i === draft.mash.length - 1" aria-label="Ниже" @click="move(i, 1)" />
          <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="sm" aria-label="Убрать паузу" @click="draft.mash.splice(i, 1)" />
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 border-t border-default pt-3" :class="GRID">
        <span class="grid size-7 place-items-center rounded-full bg-error/10 text-error"><UIcon name="i-lucide-flame" class="size-4" /></span>
        <USwitch :model-value="!!draft.boil" label="Кипячение" :disabled="!draft.boil && full" @update:model-value="setBoil" />
        <template v-if="draft.boil">
          <span class="text-center text-sm text-muted">кипение</span>
          <UInputNumber v-model="draft.boil.minutes" :min="1" :step="1" :format-options="MINUTES" size="sm" aria-label="Длительность кипячения" />
          <USelect v-model="draft.boil.watts" :items="watts" size="sm" aria-label="Мощность кипячения" />
          <span />
        </template>
      </div>
    </div>

    <div v-if="groups.length" class="mt-5 space-y-2 rounded-lg bg-elevated/50 p-4">
      <div class="text-xs font-medium uppercase tracking-wider text-dimmed">Закладки на кипячении</div>
      <div v-for="g in groups" :key="g.minutes" class="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-4">
        <span class="num w-44 shrink-0 text-sm text-muted">{{ whenInBoil(g.minutes, draft.boil?.minutes) }}</span>
        <div class="flex flex-wrap gap-x-4 gap-y-1">
          <span v-for="(item, k) in g.items" :key="k" class="inline-flex items-center gap-1.5 text-sm">
            <UIcon :name="additionKind(item).icon" class="size-4" :class="additionKind(item).tint" />
            <span class="text-highlighted">{{ additionName(item) }}</span>
            <span v-if="additionAmount(item)" class="num text-muted">{{ additionAmount(item) }}</span>
          </span>
        </div>
      </div>
    </div>
  </RecipeSection>
</template>
