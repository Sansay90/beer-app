<script setup lang="ts">
// Сетка SVG-графика: пунктир на делениях шкалы и подпись слева от оси (по умолчанию — градусы).
withDefaults(defineProps<{
  ticks: number[]
  y: (v: number) => number
  x1: number
  x2: number
  label?: (v: number) => string
}>(), { label: (v: number) => `${fmtNumber(v, 0)}°` })
</script>

<template>
  <g fill="var(--ui-text-dimmed)" font-size="11">
    <template v-for="(t, i) in ticks" :key="i">
      <line :x1="x1" :x2="x2" :y1="y(t)" :y2="y(t)" stroke="var(--ui-border)" stroke-dasharray="3 4" />
      <text :x="x1 - 8" :y="y(t) + 4" text-anchor="end">{{ label(t) }}</text>
    </template>
  </g>
</template>
