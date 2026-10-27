<script setup lang="ts">
import type { Misc } from '~/types'

defineProps<{ items: Misc[] }>()
</script>

<template>
  <RecipeSection title="Другое" icon="i-lucide-flask-conical">
    <ul class="divide-y divide-default">
      <li v-for="(m, i) in items" :key="i" class="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-3 py-2">
        <UIcon :name="additionKind(m).icon" class="size-4" :class="additionKind(m).tint" />
        <div class="min-w-0">
          <div class="truncate text-highlighted">{{ additionName(m) }}</div>
          <div class="text-xs text-muted">{{ whenLabel(MISC_USES, m.use ?? 'boil', m.minutes) }}</div>
        </div>
        <span class="num text-right text-highlighted">{{ additionAmount(m) ?? '' }}</span>
      </li>
    </ul>
  </RecipeSection>
</template>
