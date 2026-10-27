<script setup lang="ts">
import type { Yeast } from '~/types'

defineProps<{ items: Yeast[] }>()
</script>

<template>
  <RecipeSection title="Дрожжи" icon="i-lucide-microscope">
    <ul class="divide-y divide-default">
      <li v-for="(y, i) in items" :key="i" class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 py-2">
        <div class="min-w-0">
          <div class="truncate text-highlighted">{{ y.name }}</div>
          <div class="text-xs text-muted">
            {{ YEAST_FORMS[y.form ?? 'dry'] }}<template v-if="y.attenuation != null"> · сбраживание {{ fmtNumber(y.attenuation) }} %</template>
          </div>
        </div>
        <span class="num text-right text-highlighted">{{ y.amount != null ? `${fmtNumber(y.amount, 1)} ${unitLabel(y.unit)}` : '' }}</span>
      </li>
    </ul>
  </RecipeSection>
</template>
