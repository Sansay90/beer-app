<script setup lang="ts">
const brewery = useBreweryStore()

const recipe = computed(() => brewery.snapshot?.deviceRecipe ?? null)

/** Прогресс текущего шага в процентах — только когда идёт отсчёт. */
const currentProgress = computed(() => (brewery.phase.counting ? brewery.progress : null))
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-6' }">
    <div class="flex flex-wrap items-center gap-2">
      <div class="text-xs font-medium uppercase tracking-wider text-dimmed">Программа</div>
      <span class="flex-1" />
      <UButton
        :to="recipe?.id ? `/recipes/${recipe.id}` : '/recipes'"
        size="xs"
        color="neutral"
        variant="ghost"
        trailing-icon="i-lucide-arrow-right"
        :label="recipe?.id ? 'Рецепт' : 'Рецепты'"
      />
    </div>

    <UEmpty
      v-if="!recipe"
      icon="i-lucide-book-open"
      title="Рецепт в пивоварне неизвестен"
      description="Загрузите рецепт — и здесь появится ход программы."
      :actions="[{ label: 'Выбрать рецепт', to: '/recipes', icon: 'i-lucide-book-open' }]"
      variant="naked"
      class="py-6"
    />

    <template v-else>
      <div class="mt-2 flex flex-wrap items-baseline justify-between gap-2">
        <div class="text-lg font-semibold text-highlighted">{{ recipe.name || 'Рецепт из Smart Life' }}</div>
        <div class="num text-sm text-muted">{{ recipe.steps.length }} {{ plural(recipe.steps.length, 'шаг', 'шага', 'шагов') }} · {{ fmtMinutes(Math.round(brewery.total / 60)) }}</div>
      </div>

      <ol class="mt-4">
        <li v-for="(s, i) in brewery.steps" :key="s.index" class="relative flex gap-4 pb-5 last:pb-0">
          <span
            v-if="i < brewery.steps.length - 1"
            class="absolute bottom-0 left-3.75 top-8 w-px"
            :class="s.state === 'done' ? 'bg-success/50' : 'bg-border'"
          />
          <div
            class="relative z-10 grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold"
            :class="{
              'bg-success text-inverted': s.state === 'done',
              'bg-primary text-inverted ring-4 ring-primary/20': s.state === 'current',
              'bg-elevated text-muted ring-1 ring-default': s.state === 'upcoming',
            }"
          >
            <UIcon v-if="s.state === 'done'" name="i-lucide-check" class="size-4" />
            <UIcon v-else-if="s.boil" name="i-lucide-flame" class="size-4" />
            <span v-else class="num">{{ s.index }}</span>
          </div>

          <div class="min-w-0 flex-1 pt-1">
            <div class="flex flex-wrap items-baseline justify-between gap-x-3">
              <span class="font-medium" :class="s.state === 'upcoming' ? 'text-toned' : 'text-highlighted'">{{ s.name }}</span>
              <span class="num text-sm text-muted">
                {{ s.boil ? 'кипячение' : `${fmtTemp(s.temp)} °C` }} · {{ fmtMinutes(s.minutes) }} · {{ s.watts }} W
              </span>
            </div>
            <div v-if="s.additions.length" class="mt-2 flex flex-wrap gap-1.5">
              <UBadge v-for="m in s.additions" :key="m" color="neutral" variant="soft" size="sm" icon="i-lucide-bell" :label="`за ${m} мин`" />
            </div>
            <div v-if="s.state === 'current'" class="mt-3">
              <UProgress v-if="currentProgress != null" :model-value="Math.round(currentProgress * 100)" size="sm" color="success" />
              <div v-else class="text-xs text-muted">
                {{ brewery.snapshot?.alert ? 'ждёт подтверждения' : 'нагрев — отсчёт начнётся у цели' }}
              </div>
            </div>
          </div>
        </li>
      </ol>
    </template>
  </UCard>
</template>
