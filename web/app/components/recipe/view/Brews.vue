<script setup lang="ts">
// Свои варки по рецепту, новые первыми: с пивоварни — сами, остальные — через «Сварить». Пункт — страница варки
// с журналом. Показывается вошедшему (страница рецепта решает), и автору, и тому, кто варит по чужому рецепту.
import type { BrewSummary, Recipe } from '~/types'

const props = defineProps<{ recipeId: string; recipe: Recipe }>()
const prefs = usePreferencesStore()
// где партия — пока не разлита: варка идёт, брожение и какой день; вылитая — «вылито»
const now = useNow({ interval: 60_000 })
const live = (b: BrewSummary) => (b.phase === 'packaged' ? null : batchStatus(b, now.value.getTime() / 1000))

const rid = toRef(() => props.recipeId)
const { data: brews, error } = useApi('/api/brews', { query: { recipe: rid }, key: () => `brews:${rid.value}`, default: () => [] })
useErrorToast(error)
const creating = ref(false)
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-5' }">
    <div class="mb-3 text-xs font-medium tracking-wider text-dimmed uppercase">Мои варки</div>
    <ul v-if="brews.length" class="-mx-2 mb-3 space-y-0.5">
      <li v-for="b in brews" :key="b.id">
        <NuxtLink :to="`/brews/${b.id}`" class="flex gap-2.5 rounded-lg px-2 py-2 hover:bg-elevated/60">
          <UIcon :name="b.manual ? 'i-lucide-notebook-pen' : 'i-lucide-flame'" class="mt-0.5 size-4 shrink-0 text-muted" />
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
              <!-- дата — в часовом поясе посетителя: NuxtTime поправляет её до оживления страницы, без расхождения с сервером -->
              <NuxtTime :datetime="b.startedAt * 1000" locale="ru-RU" day="numeric" month="long" year="numeric" class="num text-sm whitespace-nowrap text-highlighted" />
              <UBadge v-if="live(b)" :label="live(b)!.label" :color="live(b)!.color" variant="subtle" size="sm" />
            </div>
            <div v-if="brewFacts(b, prefs.gravityUnit)" class="num mt-0.5 truncate text-sm text-muted">{{ brewFacts(b, prefs.gravityUnit) }}</div>
          </div>
        </NuxtLink>
      </li>
    </ul>
    <p v-else class="mb-3 text-sm text-muted">Вы ещё не варили по этому рецепту.</p>
    <UButton :label="brews.length ? 'Сварить ещё раз' : 'Сварить'" icon="i-lucide-flame" color="neutral" variant="outline" block @click="creating = true" />
    <BrewStartModal v-model:open="creating" :recipe-id="recipeId" :recipe="recipe" />
  </UCard>
</template>
