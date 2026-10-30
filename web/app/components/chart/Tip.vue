<script setup lang="ts">
// Подсказка у точки SVG-графика: под точкой, у краёв прижата внутрь (tipPlace, utils/chart.ts). Содержимое — слот.
import type { TipPlace } from '~/utils/chart'

defineProps<{ place: TipPlace }>()
</script>

<template>
  <div
    class="pointer-events-none absolute z-10 whitespace-nowrap rounded-lg bg-elevated px-3 py-2 text-xs shadow-lg ring ring-default"
    :style="{ left: place.left, top: place.top, transform: `translate(${place.shift}, 14px)` }"
  >
    <slot />
  </div>
</template>
