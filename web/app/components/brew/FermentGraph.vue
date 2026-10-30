<script setup lang="ts">
// Брожение партии графиком — в стиле профиля рецепта (recipe/FermentProfile.vue): две панели с общей осью времени,
// у каждой своя единица. Сверху температура: план этапов ступеньками (температура над ступенькой, название под
// осью), замеры точками, сухое охмеление зелёной точкой в свой день. Снизу плотность в единицах пивовара: план
// от OG к FG пунктиром, цели этапов «до плотности» — пунктиром над их отрезком, замеры (OG, на брожении, FG) точками. Ось — от начала брожения до конца плана (или до
// розлива / сегодня, если позже); «сейчас» — вертикальной чертой. Между замерами ничего не достраивается.
import type { BrewEntry } from '~/types'
import type { DryHopView, StageView } from '~/utils/brewlog'

const props = defineProps<{
  entries: BrewEntry[]
  stages: StageView[]
  dryHops?: DryHopView[]
  og?: number | null
  fg?: number | null
  start: number
  now: number
  packagedAt?: number | null
}>()
const prefs = usePreferencesStore()

const W = 640
const PANEL = 150
const GAP = 34
const PAD = { left: 44, right: 14, top: 24, bottom: 36 }
const H = PAD.top + PANEL + GAP + PANEL + PAD.bottom
const plotW = W - PAD.left - PAD.right
const DAY = 86400
const num = (v: number, d = 1) => fmtNumber(v, d)
const when = (t: number) => `${fmtDay(t)}, ${fmtTime(t)}`

interface Pt { x: number; y: number; t: number; text: string }

const model = computed(() => {
  // замеры брожения по видам; OG сняли до задачи дрожжей — ставим её в начало брожения
  const temps = props.entries.filter(e => e.kind === 'temp' && e.value != null).sort((a, b) => a.at - b.at)
  const gravs = props.entries.filter(e => ['og', 'gravity', 'fg'].includes(e.kind) && e.value != null)
    .map(e => (e.kind === 'og' ? { ...e, at: Math.max(e.at, props.start) } : e)).sort((a, b) => a.at - b.at)
  const planEnd = props.stages.length ? Math.max(...props.stages.map(s => s.to)) : props.start + 7 * DAY
  const last = Math.max(planEnd, props.packagedAt ?? props.now, ...temps.map(e => e.at), ...gravs.map(e => e.at))
  const t0 = props.start - DAY * 0.15
  const t1 = last + DAY * 0.3
  const x = (t: number) => PAD.left + ((t - t0) / (t1 - t0)) * plotW

  // температура
  const tScale = axisScale([...props.stages.map(s => s.temp), ...temps.map(e => e.value!)], { step: 5, margin: 4, empty: [0, 30] })
  const yT = scaleY(tScale, PAD.top, PANEL)
  const baseT = PAD.top + PANEL
  let line = ''
  const segs = props.stages.map((s, i) => {
    const x1 = x(s.from)
    const x2 = x(s.to)
    line += `${i ? ' L' : 'M'}${x1},${yT(s.temp)} L${x2},${yT(s.temp)}`
    return { x1, x2, y: yT(s.temp), temp: s.temp, name: s.name }
  })
  const area = segs.length ? `${line} L${segs[segs.length - 1]!.x2},${baseT} L${segs[0]!.x1},${baseT} Z` : ''
  const tempPts: Pt[] = temps.map(e => ({ x: x(e.at), y: yT(e.value!), t: e.at, text: `${num(e.value!)} °C` }))
  // сухое по плотности, до которой ещё не дошли, — не точкой: его день лишь прикидка
  const hops = (props.dryHops ?? []).filter(h => h.at != null && !h.estimated).map((h) => {
    const seg = props.stages.find(s => h.at! >= s.from && h.at! < s.to) ?? props.stages[props.stages.length - 1]
    return { x: x(h.at!), y: seg ? yT(seg.temp) : baseT, items: h.items, day: h.day }
  })

  // плотность — в единицах пивовара
  const gv = (sg: number) => gravityIn(sg, prefs.gravityUnit)
  const gPlan = [props.og, props.fg].filter((v): v is number => v != null).map(gv)
  const gVals = [...gPlan, ...gravs.map(e => gv(e.value!)), ...props.stages.filter(s => s.target != null).map(s => gv(s.target!))]
  // шкала — круглыми делениями: °P целыми, SG — по 0,005
  const gScale = axisScale(gVals, { step: prefs.gravityUnit === 'plato' ? 1 : 0.005, empty: [0, 1] })
  const topG = PAD.top + PANEL + GAP
  const yG = scaleY(gScale, topG, PANEL)
  const baseG = topG + PANEL
  const planG = props.og != null && props.fg != null
    ? { x1: x(props.start), y1: yG(gv(props.og)), x2: x(planEnd), y2: yG(gv(props.fg)) }
    : null
  const gravPts: Pt[] = gravs.map(e => ({ x: x(e.at), y: yG(gv(e.value!)), t: e.at, text: fmtGravity(e.value!, prefs.gravityUnit) }))
  // цели этапов «до плотности» — над своим отрезком времени
  const targets = props.stages.filter(s => s.target != null)
    .map(s => ({ x1: x(s.from), x2: x(s.to), y: yG(gv(s.target!)), text: `до ${fmtGravity(s.target!, prefs.gravityUnit)}` }))

  const nowX = !props.packagedAt && props.now >= t0 && props.now <= t1 ? x(props.now) : null
  const pkgX = props.packagedAt ? x(props.packagedAt) : null
  return { segs, line, area, tempPts, hops, yT, baseT, tTicks: tScale.ticks, planG, gravPts, targets, yG, topG, baseG,
    gTicks: gScale.ticks, nowX, pkgX }
})

const poly = (pts: Pt[]) => pts.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ')

// подсказка у точки
const active = ref<{ x: number; y: number; title: string; lines: string[] } | null>(null)
const tip = computed(() => active.value && { ...active.value, ...tipPlace(active.value.x, active.value.y, W, H) })
const gravityLabel = (g: number) => (prefs.gravityUnit === 'plato' ? num(g, 1) : num(g, 3))
const showPt = (p: Pt) => { active.value = { x: p.x, y: p.y, title: when(p.t), lines: [p.text] } }
const showHop = (h: { x: number; y: number; items: string[]; day: number | null }) => {
  active.value = { x: h.x, y: h.y, title: `Сухое охмеление${h.day != null ? ` · ${h.day}-й день` : ''}`, lines: h.items }
}
</script>

<template>
  <div class="relative w-full">
    <svg :viewBox="`0 0 ${W} ${H}`" class="h-auto w-full" role="img" aria-label="Брожение: температура и плотность против плана">
      <defs>
        <linearGradient id="ferment-graph-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--ui-primary)" stop-opacity="0.18" />
          <stop offset="100%" stop-color="var(--ui-primary)" stop-opacity="0" />
        </linearGradient>
      </defs>

      <!-- температура -->
      <text :x="PAD.left" :y="PAD.top - 10" font-size="11" font-weight="600" fill="var(--ui-text-muted)">Температура, °C</text>
      <ChartGrid :ticks="model.tTicks" :y="model.yT" :x1="PAD.left" :x2="W - PAD.right" />
      <path v-if="model.area" :d="model.area" fill="url(#ferment-graph-fill)" />
      <path v-if="model.line" :d="model.line" fill="none" stroke="var(--ui-primary)" stroke-width="2" stroke-linejoin="round" stroke-dasharray="6 4" />
      <g v-for="(s, i) in model.segs" :key="`s${i}`">
        <text v-if="s.x2 - s.x1 > 36" :x="(s.x1 + s.x2) / 2" :y="s.y - 7" text-anchor="middle" font-size="11" font-weight="600" fill="var(--ui-text-highlighted)">{{ num(s.temp) }}°</text>
        <text v-if="s.x2 - s.x1 > 70" :x="(s.x1 + s.x2) / 2" :y="model.baseT + 14" text-anchor="middle" font-size="10" fill="var(--ui-text-muted)">{{ s.name }}</text>
      </g>
      <path v-if="model.tempPts.length > 1" :d="poly(model.tempPts)" fill="none" stroke="var(--ui-info)" stroke-width="2" stroke-linejoin="round" />
      <g v-for="(p, i) in model.tempPts" :key="`tp${i}`" class="cursor-default" @pointerenter="showPt(p)" @pointerleave="active = null">
        <circle :cx="p.x" :cy="p.y" r="11" fill="transparent" />
        <circle :cx="p.x" :cy="p.y" r="4.5" fill="var(--ui-info)" stroke="var(--ui-bg)" stroke-width="2" />
      </g>
      <g v-for="(h, i) in model.hops" :key="`h${i}`" class="cursor-default" @pointerenter="showHop(h)" @pointerleave="active = null">
        <circle :cx="h.x" :cy="h.y" r="11" fill="transparent" />
        <circle :cx="h.x" :cy="h.y" r="5" fill="var(--ui-success)" stroke="var(--ui-bg)" stroke-width="2" />
      </g>

      <!-- плотность -->
      <text :x="PAD.left" :y="model.topG - 10" font-size="11" font-weight="600" fill="var(--ui-text-muted)">Плотность, {{ prefs.gravityUnit === 'plato' ? '°P' : 'SG' }}</text>
      <ChartGrid :ticks="model.gTicks" :y="model.yG" :x1="PAD.left" :x2="W - PAD.right" :label="gravityLabel" />
      <template v-if="model.planG">
        <line :x1="model.planG.x1" :y1="model.planG.y1" :x2="model.planG.x2" :y2="model.planG.y2" stroke="var(--ui-primary)" stroke-width="2" stroke-dasharray="6 4" />
        <text :x="model.planG.x2 - 4" :y="model.planG.y2 - 12" text-anchor="end" font-size="10" fill="var(--ui-text-muted)">FG по плану {{ fmtGravity(fg!, prefs.gravityUnit) }}</text>
      </template>
      <g v-for="(t, i) in model.targets" :key="`tg${i}`">
        <line :x1="t.x1" :x2="t.x2" :y1="t.y" :y2="t.y" stroke="var(--ui-warning)" stroke-width="1.5" stroke-dasharray="3 3" />
        <text v-if="t.x2 - t.x1 > 50" :x="t.x1 + 4" :y="t.y - 5" font-size="10" fill="var(--ui-warning)">{{ t.text }}</text>
      </g>
      <path v-if="model.gravPts.length > 1" :d="poly(model.gravPts)" fill="none" stroke="var(--ui-info)" stroke-width="2" stroke-linejoin="round" />
      <g v-for="(p, i) in model.gravPts" :key="`gp${i}`" class="cursor-default" @pointerenter="showPt(p)" @pointerleave="active = null">
        <circle :cx="p.x" :cy="p.y" r="11" fill="transparent" />
        <circle :cx="p.x" :cy="p.y" r="4.5" fill="var(--ui-info)" stroke="var(--ui-bg)" stroke-width="2" />
      </g>

      <!-- ось времени: границы этапов, сейчас, розлив -->
      <g font-size="10" fill="var(--ui-text-dimmed)">
        <template v-for="(s, i) in model.segs" :key="`d${i}`">
          <line :x1="s.x1" :x2="s.x1" :y1="PAD.top" :y2="model.baseG" stroke="var(--ui-border)" />
          <text :x="s.x1 + 3" :y="model.baseG + 14">{{ fmtDay(stages[i]!.from) }}</text>
        </template>
        <template v-if="model.nowX != null">
          <line :x1="model.nowX" :x2="model.nowX" :y1="PAD.top" :y2="model.baseG" stroke="var(--ui-primary)" stroke-width="1.5" />
          <text :x="model.nowX" :y="model.baseG + 28" text-anchor="middle" font-weight="600" fill="var(--ui-primary)">сейчас</text>
        </template>
        <template v-if="model.pkgX != null">
          <line :x1="model.pkgX" :x2="model.pkgX" :y1="PAD.top" :y2="model.baseG" stroke="var(--ui-success)" stroke-width="1.5" />
          <text :x="model.pkgX" :y="model.baseG + 28" text-anchor="middle" font-weight="600" fill="var(--ui-success)">розлив</text>
        </template>
      </g>
    </svg>
    <ChartTip v-if="tip" :place="tip">
      <div class="num mb-1 text-muted">{{ tip.title }}</div>
      <div v-for="(l, k) in tip.lines" :key="k" class="num font-medium text-highlighted">{{ l }}</div>
    </ChartTip>
  </div>
</template>
