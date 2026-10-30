<script setup lang="ts">
// Температура и цель шага за всю варку на пивоварне (страница партии): факт линией, цель ступенькой, подсказка
// при наведении — время, температура, цель.
import uPlot from 'uplot'
import type { HistoryPoint } from '~/types'

const props = defineProps<{ points: HistoryPoint[] }>()
const colorMode = useColorMode()
const el = useTemplateRef<HTMLDivElement>('plot')
const HEIGHT = 260
let chart: uPlot | null = null

const tip = reactive({ show: false, left: 0, top: 0, time: '', temp: '', target: '' })

function onCursor(u: uPlot) {
  const [xs, temps, targets] = u.data as [number[], (number | null)[], (number | null)[]]
  const i = u.cursor.idx
  const t = i == null ? null : xs[i]
  const temp = i == null ? null : temps[i]
  if (t == null || temp == null) {
    tip.show = false
    return
  }
  const target = targets[i!]
  tip.show = true
  tip.left = u.valToPos(t, 'x') + u.over.offsetLeft
  tip.top = u.valToPos(temp, 'y') + u.over.offsetTop
  tip.time = new Date(t * 1000).toLocaleTimeString('ru-RU')
  tip.temp = `${fmtTemp(temp)} °C`
  tip.target = target == null ? '' : `цель ${fmtTemp(target)} °C`
}

const data = (): uPlot.AlignedData => [props.points.map(p => p[0]), props.points.map(p => p[1]), props.points.map(p => p[2])]

function build() {
  if (!el.value) return
  chart?.destroy()
  const grid = { stroke: cssColor('--ui-border', 0.7), width: 1 }
  const axis = { stroke: cssColor('--ui-text-dimmed'), grid, ticks: { show: false }, font: '12px Inter, system-ui' }
  chart = new uPlot({
    width: el.value.clientWidth,
    height: HEIGHT,
    legend: { show: false },
    cursor: {
      x: true,
      y: false,
      drag: { x: false, y: false },
      points: { size: 9, width: 2, fill: cssColor('--ui-bg'), stroke: cssColor('--ui-primary') },
    },
    hooks: { setCursor: [onCursor] },
    scales: {
      x: { time: true },
      y: { range: (_u, min, max) => [Math.floor(Math.min(min, 15) / 10) * 10, Math.ceil(Math.max(max, 40) / 10) * 10 + 5] },
    },
    axes: [
      { ...axis, values: (_u, ticks) => ticks.map(t => fmtTime(t)) },
      { ...axis, size: 44, values: (_u, ticks) => ticks.map(t => `${t}°`) },
    ],
    series: [
      {},
      {
        stroke: cssColor('--ui-primary'),
        width: 2.5,
        points: { show: false },
        fill: (u) => {
          const g = u.ctx.createLinearGradient(0, u.bbox.top, 0, u.bbox.top + u.bbox.height)
          g.addColorStop(0, cssColor('--ui-primary', 0.28))
          g.addColorStop(1, cssColor('--ui-primary', 0))
          return g
        },
      },
      // цель — ступенькой: меняется скачком на смене шага
      { stroke: cssColor('--ui-text-muted', 0.8), width: 1.5, dash: [6, 6], points: { show: false }, paths: uPlot.paths.stepped!({ align: 1 }) },
    ],
  }, data(), el.value)
}

onMounted(build)
onBeforeUnmount(() => chart?.destroy())
useResizeObserver(el, () => el.value && chart?.setSize({ width: el.value.clientWidth, height: HEIGHT }))
watch(() => props.points, () => chart?.setData(data()))
watch(() => colorMode.value, () => nextTick(build))
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-6' }">
    <div class="flex flex-wrap items-center gap-2">
      <div class="text-xs font-medium uppercase tracking-wider text-dimmed">Температура</div>
      <span class="flex items-center gap-1.5 text-xs text-muted">
        <span class="inline-block h-0.5 w-4 rounded bg-primary" /> факт
        <span class="ml-2 inline-block w-4 border-t border-dashed border-muted" /> цель
      </span>
    </div>
    <div class="relative mt-4" @mouseleave="tip.show = false">
      <div ref="plot" class="w-full" />
      <div
        v-show="tip.show"
        class="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-[calc(100%+12px)] whitespace-nowrap rounded-lg bg-elevated px-3 py-2 text-xs shadow-lg ring ring-default"
        :style="{ left: `${tip.left}px`, top: `${tip.top}px` }"
      >
        <div class="num text-base font-semibold text-highlighted">{{ tip.temp }}</div>
        <div class="num text-muted">{{ tip.time }}</div>
        <div v-if="tip.target" class="num text-dimmed">{{ tip.target }}</div>
      </div>
    </div>
  </UCard>
</template>
