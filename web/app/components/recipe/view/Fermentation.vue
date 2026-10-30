<script setup lang="ts">
// Брожение рецепта — как программа пивоварни (Program.vue): профиль ступеньками, этапы списком, сухое охмеление
// по дням брожения.
import type { FermentationStep, Hop } from '~/types'

const props = defineProps<{ items: FermentationStep[]; hops?: Hop[] }>()
const dryHops = computed(() => dryHopDays(props.hops ?? []))
const total = computed(() => props.items.reduce((sum, s) => sum + s.days, 0))
</script>

<template>
  <RecipeSection title="Брожение" icon="i-lucide-thermometer-snowflake" :summary="`${fmtNumber(total, 1)} дн.`">
    <RecipeFermentProfile :steps="items" :dry-hops="dryHops" class="mb-4" />
    <ul class="divide-y divide-default">
      <li v-for="(s, i) in items" :key="i" class="flex items-center gap-3 py-2">
        <span class="num grid size-6 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-semibold text-primary">{{ i + 1 }}</span>
        <span class="min-w-0 flex-1 truncate text-highlighted">{{ s.name || `Этап ${i + 1}` }}</span>
        <span class="num text-sm text-muted">{{ fmtNumber(s.temp, 1) }} °C · {{ fmtNumber(s.days, 1) }} дн.</span>
      </li>
    </ul>
    <div v-if="dryHops.length" class="mt-4 space-y-2 rounded-lg bg-elevated/50 p-4">
      <div class="text-xs font-medium tracking-wider text-dimmed uppercase">Сухое охмеление</div>
      <div v-for="g in dryHops" :key="g.day ?? 'any'" class="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-4">
        <span class="num w-44 shrink-0 text-sm text-muted">{{ g.day != null ? `${g.day}-й день брожения` : 'день не указан' }}</span>
        <div class="flex flex-wrap gap-x-4 gap-y-1">
          <span v-for="(item, k) in g.items" :key="k" class="inline-flex items-center gap-1.5 text-sm">
            <UIcon name="i-lucide-hop" class="size-4 text-success" />
            <span class="text-highlighted">{{ item }}</span>
          </span>
        </div>
      </div>
    </div>
  </RecipeSection>
</template>
