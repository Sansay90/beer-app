<script setup lang="ts">
// Итог варки против плана рецепта: начальная и конечная плотность, крепость — с разницей; объём в ферментере —
// рядом с объёмом рецепта после кипячения (это разные объёмы, разницу не считаем). Нет замера — «—».
import type { BrewDetail } from '~/types'

const props = defineProps<{ brew: BrewDetail }>()
const prefs = usePreferencesStore()

const num = fixed
const signed = (d: number, digits: number, unit: string) =>
  Math.abs(d) < 10 ** -digits / 2 ? 'как в рецепте' : `${d > 0 ? '+' : '−'}${num(Math.abs(d), digits)}${unit}`

const tiles = computed(() => {
  const b = props.brew
  const p = b.plan ?? {}
  const unit = prefs.gravityUnit
  const gDelta = (fact?: number | null, plan?: number | null) => (fact == null || plan == null
    ? null
    : unit === 'plato'
      ? signed(gravityIn(fact, 'plato') - gravityIn(plan, 'plato'), 1, ' °P')
      : signed(fact - plan, 3, ''))
  return [
    { label: 'Начальная плотность', fact: fmtGravity(b.og, unit), plan: p.og != null ? fmtGravity(p.og, unit) : null, delta: gDelta(b.og, p.og) },
    { label: 'Конечная плотность', fact: fmtGravity(b.fg, unit), plan: p.fg != null ? fmtGravity(p.fg, unit) : null, delta: gDelta(b.fg, p.fg) },
    {
      label: 'Крепость',
      fact: b.abv != null ? `${num(b.abv, 1)} %` : '—',
      plan: p.abv != null ? `${num(p.abv, 1)} %` : null,
      delta: b.abv != null && p.abv != null ? signed(b.abv - p.abv, 1, ' %') : null,
    },
    {
      label: 'В ферментере',
      fact: b.volume != null ? `${num(b.volume, 1)} л` : '—',
      plan: p.volume != null ? `${num(p.volume, 1)} л после кипячения` : null,
      delta: null,
    },
  ]
})
</script>

<template>
  <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
    <div v-for="t in tiles" :key="t.label" class="rounded-lg bg-elevated/50 px-4 py-3">
      <div class="text-sm text-muted">{{ t.label }}</div>
      <div class="num mt-1 text-2xl font-semibold text-highlighted">{{ t.fact }}</div>
      <div v-if="t.plan" class="num mt-1 text-sm text-dimmed">
        по рецепту {{ t.plan }}<template v-if="t.delta"> · <span class="text-toned">{{ t.delta }}</span></template>
      </div>
    </div>
  </div>
</template>
