<script setup lang="ts">
import type { Hop } from '~/types'

const props = defineProps<{ items: Hop[] }>()

const grams = computed(() => props.items.reduce((a, h) => a + (h.amount ?? 0), 0))
</script>

<template>
  <RecipeSection title="Хмель" icon="i-lucide-hop" :summary="fmtNumber(grams, 1, ' г')">
    <ul class="divide-y divide-default">
      <li v-for="(h, i) in items" :key="i" class="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-3 py-2 sm:grid-cols-[1.25rem_minmax(0,1fr)_5rem_5rem]">
        <UIcon name="i-lucide-hop" class="size-4 text-success" />
        <div class="min-w-0">
          <div class="truncate text-highlighted">{{ h.name || 'Хмель' }}</div>
          <div class="text-xs text-muted">{{ whenLabel(HOP_USES, h.use ?? 'boil', h.minutes, h.day) }}</div>
        </div>
        <span class="num hidden text-right text-sm text-muted sm:block">{{ h.alpha != null ? `α ${fmtNumber(h.alpha, 1)} %` : '' }}</span>
        <span class="num text-right text-highlighted">{{ fmtNumber(h.amount, 1, ' г') }}</span>
      </li>
    </ul>
  </RecipeSection>
</template>
