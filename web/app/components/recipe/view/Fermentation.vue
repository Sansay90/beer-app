<script setup lang="ts">
import type { FermentationStep } from '~/types'

defineProps<{ items: FermentationStep[] }>()
</script>

<template>
  <RecipeSection title="Брожение" icon="i-lucide-thermometer-snowflake">
    <ul class="divide-y divide-default">
      <li v-for="(s, i) in items" :key="i" class="flex items-center gap-3 py-2">
        <span class="min-w-0 flex-1 truncate text-highlighted">{{ s.name || `Этап ${i + 1}` }}</span>
        <span class="num text-sm text-muted">{{ fmtNumber(s.temp, 1) }} °C · {{ fmtNumber(s.days, 1) }} дн.</span>
      </li>
    </ul>
  </RecipeSection>
</template>
