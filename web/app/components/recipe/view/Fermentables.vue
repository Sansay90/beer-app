<script setup lang="ts">
import type { Fermentable } from '~/types'

const props = defineProps<{ items: Fermentable[] }>()

const ICONS = { grain: 'i-lucide-wheat', adjunct: 'i-lucide-bean', sugar: 'i-lucide-candy', extract: 'i-lucide-beaker' }

const kg = computed(() => totalKg(props.items))
</script>

<template>
  <RecipeSection title="Засыпь" icon="i-lucide-wheat" :summary="fmtNumber(kg, 2, ' кг')">
    <ul class="divide-y divide-default">
      <li v-for="(f, i) in items" :key="i" class="grid grid-cols-[1.25rem_minmax(0,1fr)_auto_3.5rem] items-center gap-3 py-2 sm:grid-cols-[1.25rem_minmax(0,1fr)_7rem_5rem_3.5rem]">
        <UIcon :name="ICONS[f.kind ?? 'grain']" class="size-4 text-muted" />
        <div class="min-w-0">
          <div class="truncate text-highlighted">{{ f.name || FERMENTABLE_KINDS[f.kind ?? 'grain'] }}</div>
          <div v-if="f.use && f.use !== 'mash'" class="text-xs text-muted">{{ whenLabel(FERMENTABLE_USES, f.use, f.minutes) }}</div>
        </div>
        <span class="num hidden text-right text-sm text-muted sm:block">{{ f.ebc != null ? `${fmtNumber(f.ebc, 1)} EBC` : '' }}</span>
        <span class="num text-right text-highlighted">{{ fmtNumber(f.amount, 3, ' кг') }}</span>
        <span class="num text-right text-sm text-muted">{{ share(f.amount, kg) == null ? '' : `${share(f.amount, kg)!.toFixed(0)} %` }}</span>
      </li>
    </ul>
  </RecipeSection>
</template>
