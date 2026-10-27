<script setup lang="ts">
// Бокал с пивом: форма — по стилю BJCP, цвет — по EBC, пена у тёмных — бежевая. Цвета нет — пустой бокал.
// Размер задаёт родитель высотой (h-20), ширина — по пропорции 3 : 5.
const props = defineProps<{ ebc: number | null | undefined; styleCode?: string | null }>()

type Shape = {
  body: string               // внутренний контур — по нему обрезаются пиво и пена
  stem?: string              // ножка и донышко — стекло без пива
  rim: number                // верх пены
  foam: number               // граница пены и пива
  shine: string              // блик
}

// viewBox 0 0 48 80
const STEM = 'M22.8 43 H25.2 V70.5 H22.8 Z M13 74 Q13 70.5 24 70.5 Q35 70.5 35 74 Q35 76.5 24 76.5 Q13 76.5 13 74 Z'
const SHAPES: Record<string, Shape> = {
  pint: {
    body: 'M7 5 H41 L41.6 15 Q42.4 19 40.8 23 L37 73 Q36.8 76 34 76 H14 Q11.2 76 11 73 L7.2 23 Q5.6 19 6.4 15 Z',
    rim: 8, foam: 15, shine: 'M10.6 19 L12.6 19 L15.2 70 L13.4 70 Z',
  },
  pilsner: {
    body: 'M8 3 H40 L31 63 H17 Z',
    stem: 'M17 63 H31 L32.5 74 Q32.6 77 30 77 H18 Q15.4 77 15.5 74 Z',
    rim: 6, foam: 13, shine: 'M12.2 9 L14.4 9 L19 57 L17.6 57 Z',
  },
  stange: {
    body: 'M14 4 H34 V73 Q34 76 31 76 H17 Q14 76 14 73 Z',
    rim: 7, foam: 13, shine: 'M17 10 H19 V70 H17 Z',
  },
  weizen: {
    body: 'M10 3 H38 Q41.5 15 37.5 29 Q33.5 42 32.5 56 L31.6 72 Q31.4 76 28 76 H20 Q16.6 76 16.4 72 L15.5 56 Q14.5 42 10.5 29 Q6.5 15 10 3 Z',
    rim: 6, foam: 14, shine: 'M12.8 10 L14.8 10 L19.2 62 L17.8 62 Z',
  },
  tulip: {
    body: 'M11 4 H37 Q38.5 10 38 16 Q37 34 24 44 Q11 34 10 16 Q9.5 10 11 4 Z',
    stem: STEM,
    rim: 7, foam: 14, shine: 'M13.6 11 L15.6 11 L17.4 30 L15.8 30 Z',
  },
  snifter: {
    body: 'M15 8 H33 Q41 20 40 32 Q39 46 24 47 Q9 46 8 32 Q7 20 15 8 Z',
    stem: STEM.replace('M22.8 43', 'M22.8 46'),
    rim: 22, foam: 25, shine: 'M11.8 26 L13.8 26 L15 38 L13.2 38 Z',
  },
}

// Бокал по коду стиля BJCP 2021: лагеры — пилснерный, Kölsch и альт — штанга, пшеничные — вайценский,
// бельгийские и кислые — тюльпан, крепкие (доппельбок, барливайн, имперский стаут…) — снифтер, остальное — пинта.
const SNIFTER = new Set(['9A', '9B', '9C', '17B', '17C', '17D', '20C', '22C', '22D'])
function glassOf(code: string | null | undefined) {
  if (!code) return 'pint'
  if (code === '5B' || code === '7B') return 'stange'
  if (SNIFTER.has(code)) return 'snifter'
  const category = Number.parseInt(code)
  if (category === 10) return 'weizen'
  if (category >= 23 && category <= 26) return 'tulip'
  if (category >= 1 && category <= 8) return 'pilsner'
  return 'pint'
}

const shape = computed(() => SHAPES[glassOf(props.styleCode)]!)
const color = computed(() => beerColor(props.ebc))
const foamColor = computed(() => ((props.ebc ?? 0) >= 60 ? '#E3C9A0' : '#FBF3DF'))
const bubbles = computed(() => Array.from({ length: 9 }, (_, i) => 3 + i * 5.4))

/** Смесь цвета с белым (amount > 0) или чёрным (amount < 0). */
function tint(hex: string, amount: number) {
  const target = amount > 0 ? 255 : 0
  const k = Math.abs(amount)
  const ch = (i: number) => Math.round(Number.parseInt(hex.slice(i, i + 2), 16) * (1 - k) + target * k)
  return `rgb(${ch(1)} ${ch(3)} ${ch(5)})`
}

const id = useId().replace(/[^\w-]/g, '')
</script>

<template>
  <svg
    viewBox="0 0 48 80"
    class="aspect-3/5 w-auto shrink-0 overflow-visible text-default"
    role="img"
    :aria-label="ebc != null ? `Цвет ${Math.round(ebc)} EBC` : 'Цвет не задан'"
  >
    <defs>
      <clipPath :id="`${id}-glass`"><path :d="shape.body" /></clipPath>
      <linearGradient v-if="color" :id="`${id}-beer`" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" :stop-color="tint(color, 0.1)" />
        <stop offset="1" :stop-color="tint(color, -0.25)" />
      </linearGradient>
    </defs>

    <g :clip-path="`url(#${id}-glass)`">
      <path :d="shape.body" fill="currentColor" fill-opacity="0.05" />
      <template v-if="color">
        <rect x="0" :y="shape.foam" width="48" height="80" :fill="`url(#${id}-beer)`" />
        <rect x="0" :y="shape.rim + 1.5" width="48" :height="shape.foam - shape.rim - 1.5" :fill="foamColor" />
        <circle v-for="x in bubbles" :key="x" :cx="x" :cy="shape.rim + 1.5" r="2.6" :fill="foamColor" />
      </template>
      <path :d="shape.shine" fill="#fff" :fill-opacity="color ? 0.28 : 0.08" />
    </g>
    <path :d="shape.body" fill="none" stroke="currentColor" stroke-opacity="0.3" stroke-width="1.4" stroke-linejoin="round" />
    <path v-if="shape.stem" :d="shape.stem" fill="currentColor" fill-opacity="0.12" stroke="currentColor" stroke-opacity="0.3" stroke-width="1.2" stroke-linejoin="round" />
  </svg>
</template>
