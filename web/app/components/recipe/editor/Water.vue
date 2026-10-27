<script setup lang="ts">
// Вода: гидромодуль, соли и кислоты, профиль ионов. Литры заторной и промывочной воды считаются (utils/water.ts).
// Исходная вода по умолчанию — осмос (нули).
import type { DropdownMenuItem } from '@nuxt/ui'
import type { WaterAgent } from '~/types'
import type { WaterDraft } from '~/types/recipe'
import type { WaterAgentMeta, WaterVolumes } from '~/utils/water'

const water = defineModel<WaterDraft>({ required: true })
// evaporation — из профиля оборудования, undefined — профиль ещё не загружен
const props = defineProps<{ volumes: WaterVolumes; evaporation?: number; boilMinutes: number }>()

const AGENTS = (Object.entries(WATER_AGENTS) as [WaterAgent, WaterAgentMeta][])
  .map(([value, a]) => ({ value, label: a.formula ? `${a.label} · ${a.formula}` : a.label, description: a.note }))
const TARGETS = [{ label: 'Затор', value: 'mash' }, { label: 'Промывка', value: 'sparge' }]
const GRID = 'sm:grid sm:grid-cols-[15rem_minmax(0,1fr)_6.5rem_8rem_2rem]'

const addItems: DropdownMenuItem[] = AGENTS.map(a => ({ label: a.label, onSelect: () => water.value.additions.push(newWaterAddition(a.value)) }))

const summary = computed(() => {
  const { mash, sparge } = props.volumes
  if (mash == null) return undefined
  return sparge == null ? `затор ${fmtL(mash)}` : `затор ${fmtL(mash)} · промывка ${fmtL(sparge)}`
})
const fmtL = (l: number) => `${l.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} л`
const fmtNum = (v: number) => v.toLocaleString('ru-RU', { maximumFractionDigits: 1 })

const profiles = computed(() => waterProfiles(water.value, props.volumes))
const rows = computed(() => [
  { label: 'Затор', ions: profiles.value.mash },
  { label: 'Промывка', ions: profiles.value.sparge },
  { label: 'Всего', ions: profiles.value.total },
].filter(r => r.ions))

const sourceOpen = ref(IONS.some(ion => water.value.source[ion]))
const sourceZero = computed(() => IONS.every(ion => !water.value.source[ion]))

const fmtPpm = (v: number) => Math.round(v).toString()
const fmtRatio = (v: number | null) => (v == null ? '—' : v.toLocaleString('ru-RU', { maximumFractionDigits: 2 }))
</script>

<template>
  <RecipeSection title="Вода" icon="i-lucide-droplets" :summary="summary">
    <template #actions>
      <UDropdownMenu :items="addItems" :content="{ align: 'end' }">
        <UButton icon="i-lucide-plus" label="Соль или кислота" trailing-icon="i-lucide-chevron-down" size="xs" color="neutral" variant="outline" />
      </UDropdownMenu>
    </template>

    <div class="grid gap-4 sm:grid-cols-3">
      <UFormField label="Гидромодуль" hint="л/кг">
        <UInputNumber v-model="water.ratio" :min="0" :step="0.1" :step-snapping="false" :increment="false" :decrement="false" :format-options="{ maximumFractionDigits: 2 }" placeholder="—" class="w-full" />
      </UFormField>
      <UFormField label="Заторная вода">
        <div class="num flex h-8 items-center text-sm" :class="volumes.mash == null ? 'text-dimmed' : 'text-highlighted'">
          {{ volumes.mash == null ? 'гидромодуль × засыпь' : fmtL(volumes.mash) }}
        </div>
      </UFormField>
      <UFormField label="Промывочная вода">
        <div class="num flex h-8 items-center text-sm" :class="volumes.sparge == null ? 'text-dimmed' : 'text-highlighted'">
          {{ volumes.sparge != null ? fmtL(volumes.sparge) : volumes.mash == null ? 'по засыпи' : 'нужен объём после кипячения' }}
        </div>
      </UFormField>
    </div>

    <p v-if="volumes.excess" class="num mt-3 text-sm text-warning">
      Заторной воды больше, чем нужно на всю варку ({{ fmtL(volumes.total!) }}): промывки не будет, а перед кипячением выйдет больше {{ fmtL(volumes.preBoil!) }}.
    </p>
    <p v-else-if="volumes.total != null" class="num mt-3 flex flex-wrap items-center gap-x-1 text-xs text-muted">
      <span>Всего {{ fmtL(volumes.total) }}: {{ fmtL(volumes.preBoil!) }} перед кипячением и ~{{ fmtL(volumes.absorbed) }} останется в дробине.</span>
      <span>Испарение</span>
      <ULink to="/settings#equipment" class="text-muted underline decoration-dotted underline-offset-2 hover:text-highlighted">{{ fmtNum(evaporation ?? 0) }} л/ч</ULink>
      <span>× {{ boilMinutes }} мин.</span>
    </p>

    <div v-if="water.additions.length" class="mt-5 space-y-2">
      <div class="hidden items-center gap-2 px-0.5 text-xs text-dimmed" :class="GRID">
        <span>Соль или кислота</span><span /><span class="text-center">Сколько</span><span>Куда</span><span />
      </div>
      <div v-for="(a, i) in water.additions" :key="i" class="flex flex-wrap items-center gap-2" :class="GRID">
        <USelect v-model="a.agent" :items="AGENTS" size="sm" class="w-60 sm:w-auto" aria-label="Соль или кислота" />
        <UInput v-if="a.agent === 'other'" v-model="a.name" placeholder="Название" size="sm" class="min-w-40 flex-1" />
        <span v-else class="num min-w-0 truncate text-xs text-muted">{{ additionEffect(water, volumes, i) ?? WATER_AGENTS[a.agent].note ?? '' }}</span>
        <UInputNumber
          v-model="a.amount"
          :min="0"
          :step="0.1"
          :step-snapping="false"
          :increment="false"
          :decrement="false"
          :format-options="{ style: 'unit', unit: WATER_AGENTS[a.agent].unit === 'ml' ? 'milliliter' : 'gram', maximumFractionDigits: 2 }"
          placeholder="—"
          size="sm"
          class="w-26 sm:w-auto"
          aria-label="Количество"
        />
        <USelect v-model="a.target" :items="TARGETS" size="sm" class="w-32 sm:w-auto" aria-label="Куда" />
        <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="sm" aria-label="Убрать" @click="water.additions.splice(i, 1)" />
      </div>
    </div>
    <RecipeEditorEmpty v-else text="Соли и кислоты для заторной и промывочной воды." class="mt-5" />

    <div class="mt-5 rounded-lg bg-elevated/50 p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <span class="text-xs font-medium uppercase tracking-wider text-dimmed">Профиль воды, мг/л</span>
        <UButton
          size="xs"
          color="neutral"
          variant="link"
          :trailing-icon="sourceOpen ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
          :label="sourceZero ? 'Исходная вода: осмос' : 'Исходная вода задана'"
          @click="sourceOpen = !sourceOpen"
        />
      </div>

      <div v-if="sourceOpen" class="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6">
        <UFormField v-for="ion in IONS" :key="ion" :label="ION_LABELS[ion]" size="xs">
          <UInputNumber v-model="water.source[ion]" :min="0" :step="1" :step-snapping="false" :increment="false" :decrement="false" size="sm" class="w-full" />
        </UFormField>
      </div>

      <table v-if="rows.length" class="num mt-3 w-full text-sm">
        <thead>
          <tr class="text-xs text-dimmed">
            <th class="pb-1 text-left font-normal" />
            <th v-for="ion in IONS" :key="ion" class="pb-1 text-right font-normal">{{ ION_LABELS[ion] }}</th>
            <th class="pb-1 text-right font-normal">Cl : SO₄</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.label">
            <td class="py-0.5 text-muted">{{ r.label }}</td>
            <td v-for="ion in IONS" :key="ion" class="py-0.5 text-right text-highlighted">{{ fmtPpm(r.ions![ion]) }}</td>
            <td class="py-0.5 text-right text-highlighted">{{ fmtRatio(chlorideSulfate(r.ions)) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="mt-2 text-sm text-muted">Укажите гидромодуль и засыпь — посчитаем профиль.</p>
    </div>
  </RecipeSection>
</template>
