<script setup lang="ts">
// Температурный профиль рецепта: паузы ступеньками, кипячение, точки закладок (одна точка — одна минута).
// Подъёмы между паузами нарисованы условной ширины — реальное время нагрева зависит от объёма.
import type { Addition } from '~/types'
import type { AdditionGroup, ProgramStep } from '~/utils/recipe'

// groups — закладки кипячения (boilGroups): точки на отрезке кипячения
const props = defineProps<{ steps: ProgramStep[]; groups?: AdditionGroup[] }>()

const W = 640
const H = 180
const PAD = { left: 38, right: 14, top: 26, bottom: 26 }
const plotW = W - PAD.left - PAD.right
const plotH = H - PAD.top - PAD.bottom

const model = computed(() => {
  const steps = props.steps.filter(s => s.minutes > 0)
  if (!steps.length) return null
  const scale = axisScale(steps.map(s => (s.boil ? 100 : s.temp)), { step: 10, margin: 8, max: 100 })
  const total = steps.reduce((a, s) => a + s.minutes, 0)
  const ramp = Math.max(4, total * 0.04)
  const span = total + ramp * (steps.length - 1)
  const x = (m: number) => PAD.left + (m / span) * plotW
  const y = scaleY(scale, PAD.top, plotH)

  let m = 0
  const segs: { x1: number; x2: number; y: number; temp: number; minutes: number; boil: boolean }[] = []
  const slots: { cx: number; cy: number; minutes: number; boil: number; items: Addition[] }[] = []
  let line = ''
  steps.forEach((s, i) => {
    const t = s.boil ? 100 : s.temp
    if (i > 0) m += ramp
    const x1 = x(m)
    const x2 = x(m + s.minutes)
    line += i === 0 ? `M${x1},${y(t)}` : ` L${x1},${y(t)}`
    line += ` L${x2},${y(t)}`
    segs.push({ x1, x2, y: y(t), temp: t, minutes: s.minutes, boil: s.boil })
    if (s.boil) {
      for (const g of props.groups ?? []) {
        if (g.minutes >= 0 && g.minutes <= s.minutes) {
          slots.push({ cx: x(m + s.minutes - g.minutes), cy: y(t), minutes: g.minutes, boil: s.minutes, items: g.items })
        }
      }
    }
    m += s.minutes
  })
  const baseY = PAD.top + plotH
  const area = `${line} L${segs[segs.length - 1]!.x2},${baseY} L${segs[0]!.x1},${baseY} Z`
  return { segs, slots, line, area, ticks: scale.ticks, y, baseY }
})

// подсказка под точкой (кипячение — всегда у верхнего края); у краёв прижимается внутрь графика
const active = ref<number | null>(null)
const tip = computed(() => {
  const slot = active.value == null ? null : model.value?.slots[active.value]
  if (!slot) return null
  return {
    ...tipPlace(slot.cx, slot.cy, W, H),
    when: whenInBoil(slot.minutes, slot.boil),
    items: slot.items.map(a => ({ ...additionKind(a), name: additionName(a), amount: additionAmount(a), note: additionNote(a) })),
  }
})
</script>

<template>
  <div class="relative w-full">
    <svg v-if="model" :viewBox="`0 0 ${W} ${H}`" class="h-auto w-full" role="img" aria-label="Температурный профиль рецепта">
      <defs>
        <linearGradient id="profile-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--ui-primary)" stop-opacity="0.22" />
          <stop offset="100%" stop-color="var(--ui-primary)" stop-opacity="0" />
        </linearGradient>
      </defs>

      <ChartGrid :ticks="model.ticks" :y="model.y" :x1="PAD.left" :x2="W - PAD.right" />

      <path :d="model.area" fill="url(#profile-fill)" />
      <path :d="model.line" fill="none" stroke="var(--ui-primary)" stroke-width="2.5" stroke-linejoin="round" />

      <g v-for="(s, i) in model.segs" :key="i">
        <line v-if="s.boil" :x1="s.x1" :x2="s.x2" :y1="s.y" :y2="s.y" stroke="var(--ui-error)" stroke-width="3.5" stroke-linecap="round" />
        <text :x="(s.x1 + s.x2) / 2" :y="s.y - 9" text-anchor="middle" font-size="12" font-weight="600" fill="var(--ui-text-highlighted)">
          {{ s.boil ? 'кип' : `${s.temp}°` }}
        </text>
        <text :x="(s.x1 + s.x2) / 2" :y="model.baseY + 17" text-anchor="middle" font-size="11" fill="var(--ui-text-muted)">
          {{ s.minutes }} мин
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
        <UIcon :name="item.icon" class="size-4 shrink-0" :class="item.tint" />
        <span class="font-medium text-highlighted">{{ item.name }}</span>
        <span v-if="item.amount" class="num ml-auto pl-3 text-muted">{{ item.amount }}</span>
        <span v-if="item.note" class="num text-muted">·&ensp;{{ item.note }}</span>
      </div>
    </ChartTip>
  </div>
</template>
