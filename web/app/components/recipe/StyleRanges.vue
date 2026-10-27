<script setup lang="ts">
// Показатели рецепта против рамок стиля BJCP: зелёная полоса — рамки стиля, риска — рецепт.
// У цвета полоса и шкала — в цвет пива (ebcGradient).
// adjustable — в редакторе: показатель с ручкой подгоняется перетаскиванием (adjust — цель, commit — конец);
// ингредиенты под цель меняет редактор (utils/calc.ts). ABV не подгоняется — он из OG и FG.
import type { BjcpStyle } from '~/utils/styles'

type Key = 'og' | 'fg' | 'ibu' | 'ebc'

const props = defineProps<{
  bjcp: BjcpStyle | null
  og: number | null | undefined
  fg: number | null | undefined
  ibu: number | null | undefined
  ebc: number | null | undefined
  adjustable?: Partial<Record<Key, boolean>>
  custom?: boolean                // авторский рецепт — рамок нет намеренно
}>()
const emit = defineEmits<{ adjust: [key: Key, value: number]; commit: [] }>()
const prefs = usePreferencesStore()

type Span = [number, number] | null

const rows = computed(() => {
  const unit = prefs.gravityUnit
  const plato = unit === 'plato'
  const g = (span: Span) => (span ? [gravityIn(span[0], unit), gravityIn(span[1], unit)] as [number, number] : null)
  const gv = (sg: number | null | undefined) => (sg == null ? null : gravityIn(sg, unit))
  const fmt = (v: number, digits: number) => v.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })
  const gravity = { digits: plato ? 1 : 3, step: plato ? 0.1 : 0.001, suffix: plato ? ' °P' : '' }
  const b = props.bjcp
  const list: { key: Key | 'abv'; label: string; value: number | null; span: Span; digits: number; step: number; suffix: string }[] = [
    { key: 'og', label: 'OG', value: gv(props.og), span: g(b?.og ?? null), ...gravity },
    { key: 'fg', label: 'FG', value: gv(props.fg), span: g(b?.fg ?? null), ...gravity },
    { key: 'abv', label: 'ABV', value: abvOf(props.og, props.fg), span: b?.abv ?? null, digits: 1, step: 0.1, suffix: ' %' },
    { key: 'ibu', label: 'IBU', value: props.ibu ?? null, span: b?.ibu ?? null, digits: 0, step: 1, suffix: '' },
    { key: 'ebc', label: 'EBC', value: props.ebc ?? null, span: b?.ebc ?? null, digits: 0, step: 1, suffix: '' },
  ]
  return list.map((r) => {
    let scale = null
    if (r.span) {
      // шкала — рамки стиля с полями; у ползунка шкала постоянная, у риски растягивается до значения вне рамок
      const pad = (r.span[1] - r.span[0]) * 0.6 || r.step * 10
      const slider = r.key !== 'abv' && !!props.adjustable?.[r.key]
      const lo = Math.max(0, Math.floor((Math.min(r.span[0] - pad, slider ? Infinity : r.value ?? Infinity)) / r.step) * r.step)
      const hi = Math.ceil(Math.max(r.span[1] + pad, slider ? -Infinity : r.value ?? -Infinity) / r.step) * r.step
      const at = (v: number) => `${Math.min(100, Math.max(0, ((v - lo) / (hi - lo)) * 100))}%`
      const color = r.key === 'ebc'
      scale = {
        lo, hi, slider, color,
        track: color ? { backgroundImage: ebcGradient(lo, hi) } : undefined,
        band: { left: at(r.span[0]), width: `calc(${at(r.span[1])} - ${at(r.span[0])})`, ...(color ? { backgroundImage: ebcGradient(r.span[0], r.span[1]) } : {}) },
        marker: r.value == null ? null : at(r.value),
      }
    }
    return {
      ...r,
      text: r.value == null ? '—' : fmt(r.value, r.digits) + r.suffix,
      range: r.span ? `${fmt(r.span[0], r.digits)}–${fmt(r.span[1], r.digits)}` : null,
      pos: rangePosition(r.value, r.span),
      scale,
    }
  })
})

function set(key: Key | 'abv', v: number | number[] | undefined) {
  const value = Array.isArray(v) ? v[0] : v
  if (value == null || key === 'abv') return
  const gravity = key === 'og' || key === 'fg'
  emit('adjust', key, gravity && prefs.gravityUnit === 'plato' ? sgFromPlato(value) : value)
}
</script>

<template>
  <div class="space-y-3.5">
    <div v-for="r in rows" :key="r.label">
      <div class="flex items-baseline justify-between gap-3">
        <span class="text-xs font-medium tracking-wider text-dimmed">{{ r.label }}</span>
        <span class="num text-sm font-semibold" :class="r.pos === 'low' || r.pos === 'high' ? 'text-warning' : 'text-highlighted'">
          {{ r.text }}
        </span>
      </div>

      <div v-if="r.scale?.slider" class="relative mt-1.5">
        <div class="pointer-events-none absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full" :class="r.scale.color ? 'opacity-30' : 'bg-elevated'" :style="r.scale.track" />
        <div class="pointer-events-none absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full" :class="r.scale.color ? 'ring-1 ring-default ring-inset' : 'bg-success/35'" :style="r.scale.band" />
        <USlider
          :model-value="r.value ?? (r.span![0] + r.span![1]) / 2"
          :min="r.scale.lo"
          :max="r.scale.hi"
          :step="r.step"
          size="xs"
          :aria-label="r.label"
          :ui="{
            track: 'bg-transparent h-1.5',
            range: 'bg-transparent',
            thumb: [
              'size-3.5 cursor-grab active:cursor-grabbing ring-2',
              r.value == null ? 'bg-default ring-accented' : r.pos === 'in' ? 'bg-success ring-default' : 'bg-warning ring-default',
            ].join(' '),
          }"
          @update:model-value="set(r.key, $event)"
          @change="emit('commit')"
        />
      </div>
      <div v-else-if="r.scale" class="relative mt-1.5 h-1.5 rounded-full" :class="{ 'bg-elevated': !r.scale.color }">
        <div v-if="r.scale.color" class="absolute inset-0 rounded-full opacity-30" :style="r.scale.track" />
        <div class="absolute inset-y-0 rounded-full" :class="r.scale.color ? 'ring-1 ring-default ring-inset' : 'bg-success/35'" :style="r.scale.band" />
        <div
          v-if="r.scale.marker"
          class="absolute top-1/2 h-3 w-1 -translate-1/2 rounded-full"
          :class="r.pos === 'in' ? 'bg-success' : 'bg-warning'"
          :style="{ left: r.scale.marker }"
        />
      </div>

      <div v-if="r.range" class="num mt-1 text-right text-[11px] text-dimmed">стиль {{ r.range }}</div>
    </div>
    <p v-if="!bjcp" class="text-xs text-muted">{{ custom ? 'Авторский рецепт — без рамок стиля.' : 'Выберите стиль BJCP — покажем его рамки.' }}</p>
  </div>
</template>
