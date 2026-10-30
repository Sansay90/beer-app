<script setup lang="ts">
// Профиль брожения рецепта — как температурный профиль программы (RecipeProfile.vue): этапы ступеньками,
// температура над ступенькой, дни под осью, сухое охмеление — точкой в свой день («на N-й день» — через N − 1
// суток от начала), при наведении — что закладывать. Переходы между этапами нарисованы условной ширины.
import type { FermentationStep } from '~/types'

const props = defineProps<{ steps: FermentationStep[]; dryHops?: { day: number | null; items: string[] }[] }>()

const W = 640
const H = 180
const PAD = { left: 38, right: 14, top: 26, bottom: 26 }
const plotW = W - PAD.left - PAD.right
const plotH = H - PAD.top - PAD.bottom
const num = (v: number) => v.toLocaleString('ru-RU', { maximumFractionDigits: 1 })

const model = computed(() => {
  const steps = props.steps.filter(s => s.days > 0)
  if (!steps.length) return null
  const scale = axisScale(steps.map(s => s.temp), { step: 5, margin: 4 })
  const total = steps.reduce((a, s) => a + s.days, 0)
  const ramp = Math.max(0.3, total * 0.04)
  const span = total + ramp * (steps.length - 1)
  const x = (d: number) => PAD.left + (d / span) * plotW
  const y = scaleY(scale, PAD.top, plotH)

  let d = 0               // по оси: дни этапов и условные переходы
  let day = 0             // дни брожения — для сухого охмеления
  const segs: { x1: number; x2: number; y: number; temp: number; days: number }[] = []
  const slots: { cx: number; cy: number; day: number; items: string[] }[] = []
  let line = ''
  steps.forEach((s, i) => {
    if (i > 0) d += ramp
    const x1 = x(d)
    const x2 = x(d + s.days)
    line += i === 0 ? `M${x1},${y(s.temp)}` : ` L${x1},${y(s.temp)}`
    line += ` L${x2},${y(s.temp)}`
    segs.push({ x1, x2, y: y(s.temp), temp: s.temp, days: s.days })
    for (const g of props.dryHops ?? []) {
      const at = g.day == null ? null : g.day - 1
      if (at != null && at >= day && (at < day + s.days || (i === steps.length - 1 && at <= day + s.days))) {
        slots.push({ cx: x(d + at - day), cy: y(s.temp), day: g.day!, items: g.items })
      }
    }
    d += s.days
    day += s.days
  })
  const baseY = PAD.top + plotH
  const area = `${line} L${segs[segs.length - 1]!.x2},${baseY} L${segs[0]!.x1},${baseY} Z`
  return { segs, slots, line, area, ticks: scale.ticks, y, baseY }
})

// подсказка под точкой; у краёв прижимается внутрь графика
const active = ref<number | null>(null)
const tip = computed(() => {
  const slot = active.value == null ? null : model.value?.slots[active.value]
  if (!slot) return null
  return {
    ...tipPlace(slot.cx, slot.cy, W, H),
    when: `Сухое охмеление · ${slot.day}-й день брожения`,
    items: slot.items,
  }
})
</script>

<template>
  <div class="relative w-full">
    <svg v-if="model" :viewBox="`0 0 ${W} ${H}`" class="h-auto w-full" role="img" aria-label="Профиль брожения рецепта">
      <defs>
        <linearGradient id="ferment-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--ui-primary)" stop-opacity="0.22" />
          <stop offset="100%" stop-color="var(--ui-primary)" stop-opacity="0" />
        </linearGradient>
      </defs>
      <ChartGrid :ticks="model.ticks" :y="model.y" :x1="PAD.left" :x2="W - PAD.right" />

      <path :d="model.area" fill="url(#ferment-fill)" />
      <path :d="model.line" fill="none" stroke="var(--ui-primary)" stroke-width="2.5" stroke-linejoin="round" />

      <g v-for="(s, i) in model.segs" :key="i">
        <text :x="(s.x1 + s.x2) / 2" :y="s.y - 9" text-anchor="middle" font-size="12" font-weight="600" fill="var(--ui-text-highlighted)">
          {{ num(s.temp) }}°
        </text>
        <text :x="(s.x1 + s.x2) / 2" :y="model.baseY + 17" text-anchor="middle" font-size="11" fill="var(--ui-text-muted)">
          {{ num(s.days) }} дн.
        </text>
      </g>

      <g
        v-for="(h, i) in model.slots"
        :key="`h${i}`"
        class="cursor-default"
        @pointerenter="active = i"
        @pointerleave="active = null"
      >
        <circle :cx="h.cx" :cy="h.cy" r="12" fill="transparent" />
        <circle
          :cx="h.cx"
          :cy="h.cy"
          :r="active === i ? 6.5 : 5"
          fill="var(--ui-success)"
          stroke="var(--ui-bg)"
          stroke-width="2"
          class="transition-[r] duration-150"
        />
      </g>
    </svg>
    <ChartTip v-if="tip" :place="tip">
      <div class="num mb-1.5 text-muted">{{ tip.when }}</div>
      <div v-for="(item, k) in tip.items" :key="k" class="flex items-center gap-2 py-0.5">
        <UIcon name="i-lucide-hop" class="size-4 shrink-0 text-success" />
        <span class="font-medium text-highlighted">{{ item }}</span>
      </div>
    </ChartTip>
  </div>
</template>
