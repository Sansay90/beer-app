<script setup lang="ts">
// Программа пивоварни по рецепту: профиль температуры, паузы и кипячение, закладки на кипячении.
import type { Recipe } from '~/types'

const props = defineProps<{ recipe: Recipe }>()

const { data: limits } = useLimits()

const steps = computed(() => programOf(props.recipe, limits.value?.boilTemp))
const groups = computed(() => boilGroups(props.recipe))
</script>

<template>
  <RecipeSection title="Затирание и кипячение" icon="i-lucide-thermometer" :summary="programSummary(recipe)">
    <template v-if="steps.length">
      <RecipeProfile :steps="steps" :groups="groups" class="mb-4" />
      <ul class="divide-y divide-default">
        <li v-for="(s, i) in steps" :key="i" class="flex items-center gap-3 py-2">
          <span
            class="num grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold"
            :class="s.boil ? 'bg-error/10 text-error' : 'bg-primary/10 text-primary'"
          >
            <UIcon v-if="s.boil" name="i-lucide-flame" class="size-3.5" />
            <template v-else>{{ i + 1 }}</template>
          </span>
          <span class="min-w-0 flex-1 truncate text-highlighted">{{ s.name }}</span>
          <span class="num text-sm text-muted">{{ s.boil ? 'кипение' : `${fmtNumber(s.temp, 1)} °C` }} · {{ s.minutes }} мин · {{ s.watts }} W</span>
        </li>
      </ul>
      <div v-if="groups.length" class="mt-4 space-y-2 rounded-lg bg-elevated/50 p-4">
        <div class="text-xs font-medium uppercase tracking-wider text-dimmed">Закладки на кипячении</div>
        <div v-for="g in groups" :key="g.minutes" class="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-4">
          <span class="num w-44 shrink-0 text-sm text-muted">{{ whenInBoil(g.minutes, recipe.boil?.minutes) }}</span>
          <div class="flex flex-wrap gap-x-4 gap-y-1">
            <span v-for="(item, k) in g.items" :key="k" class="inline-flex items-center gap-1.5 text-sm">
              <UIcon :name="additionKind(item).icon" class="size-4" :class="additionKind(item).tint" />
              <span class="text-highlighted">{{ additionName(item) }}</span>
              <span v-if="additionAmount(item)" class="num text-muted">{{ additionAmount(item) }}</span>
              <span v-if="additionNote(item)" class="num text-xs text-muted">· {{ additionNote(item) }}</span>
            </span>
          </div>
        </div>
      </div>
    </template>
    <p v-else class="text-sm text-muted">Пауз и кипячения нет — добавьте их в редакторе, чтобы загрузить рецепт в пивоварню.</p>
  </RecipeSection>
</template>
