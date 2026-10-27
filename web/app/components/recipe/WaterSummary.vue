<script setup lang="ts">
// Вода рецепта для просмотра: гидромодуль и объёмы, соли и кислоты, профиль ионов.
import type { Water } from '~/types'
import type { Ions, WaterVolumes } from '~/utils/water'

const props = defineProps<{ water: Water; volumes: WaterVolumes }>()

const TARGET = { mash: 'в затор', sparge: 'в промывку' }
const profiles = computed(() => waterProfiles(props.water, props.volumes))
const rows = computed(() => [
  { label: 'Затор', ions: profiles.value.mash },
  { label: 'Промывка', ions: profiles.value.sparge },
  { label: 'Всего', ions: profiles.value.total },
].filter(r => r.ions))
const summary = computed(() => [
  props.water.ratio && `${props.water.ratio.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} л/кг`,
  props.volumes.mash != null && `затор ${fmtL(props.volumes.mash)}`,
  props.volumes.sparge != null && `промывка ${fmtL(props.volumes.sparge)}`,
].filter(Boolean).join(' · '))
const fmtL = (l: number) => `${l.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} л`
const ratio = (p: Ions | null) => {
  const r = chlorideSulfate(p)
  return r == null ? '—' : r.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}
</script>

<template>
  <RecipeSection title="Вода" icon="i-lucide-droplets" :summary="summary || undefined">
    <ul v-if="water.additions?.length" class="divide-y divide-default">
      <li v-for="(a, i) in water.additions" :key="i" class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 py-2">
        <div class="min-w-0">
          <div class="truncate text-highlighted">
            {{ a.agent === 'other' ? a.name || 'Другое' : WATER_AGENTS[a.agent].label }}
            <span v-if="WATER_AGENTS[a.agent].formula" class="text-sm text-muted">{{ WATER_AGENTS[a.agent].formula }}</span>
          </div>
          <div class="text-xs text-muted">{{ TARGET[a.target ?? 'mash'] }}<template v-if="additionEffect(water, volumes, i)"> · {{ additionEffect(water, volumes, i) }}</template></div>
        </div>
        <span class="num text-right text-highlighted">{{ waterAmount(a.agent, a.amount) ?? '' }}</span>
      </li>
    </ul>

    <table v-if="rows.length" class="num w-full text-sm" :class="{ 'mt-4': water.additions?.length }">
      <thead>
        <tr class="text-xs text-dimmed">
          <th class="pb-1 text-left font-normal">мг/л</th>
          <th v-for="ion in IONS" :key="ion" class="pb-1 text-right font-normal">{{ ION_LABELS[ion] }}</th>
          <th class="pb-1 text-right font-normal">Cl : SO₄</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.label">
          <td class="py-0.5 text-muted">{{ r.label }}</td>
          <td v-for="ion in IONS" :key="ion" class="py-0.5 text-right text-highlighted">{{ Math.round(r.ions![ion]) }}</td>
          <td class="py-0.5 text-right text-highlighted">{{ ratio(r.ions) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="!water.ratio" class="text-sm text-muted" :class="{ 'mt-3': water.additions?.length }">
      Гидромодуль не задан — без него не посчитать объёмы и профиль воды.
    </p>
  </RecipeSection>
</template>
