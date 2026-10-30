<script setup lang="ts">
// «Сварить»: новая партия по рецепту. На каком оборудовании (основное выбрано; нет ни одного — добавить тут же),
// что меняется в рецепте под его объём и эффективность — предпросмотр пересчёта, сервис посчитает так же, —
// и день варки (по умолчанию сегодня). Сварили — страница партии: рецепт партии, журнал, брожение.
// На странице рецепта рецепт уже есть; из «Моих варок» — сначала выбрать.
import type { Recipe } from '~/types'

const props = defineProps<{ recipeId?: string; recipe?: Recipe | null }>()
const open = defineModel<boolean>('open', { default: false })
const { $api } = useNuxtApp()
const { exec, pending } = useCommand()
const { exec: load, pending: loading } = useCommand()
const prefs = usePreferencesStore()

const today = () => localInput(Date.now() / 1000)
const day = ref(today())
const picked = ref<string | undefined>(props.recipeId)

// рецепты для выбора — свои и опубликованные; читаем, только когда окно открыли без рецепта
const { data: recipes, execute } = useApi('/api/recipes', { key: 'brew-recipes', default: () => [], immediate: false })
const items = computed(() => recipes.value.map(r => ({ label: r.name, value: r.id, description: styleLabel(r.style) })))
const loaded = ref<Recipe | null>(null)
const recipe = computed(() => props.recipe ?? loaded.value)
watch(picked, async (id) => {
  loaded.value = null
  if (!id || props.recipe) return
  loaded.value = (await load(() => $api('/api/recipes/{rid}', { path: { rid: id } }))) ?? null
})

// оборудование: основное выбрано; добавить можно, не уходя из окна
const { systems: equipment, data: main, refresh: refreshEquipment } = useEquipment()   // варят на варочной системе
const equipmentId = ref<string | undefined>()
const adding = ref(false)
const equipmentItems = computed(() => equipment.value.map(e => ({
  value: e.id,
  label: e.main ? `${e.name} · основная` : e.name,
  description: `${e.volume != null ? fmtNumber(e.volume, 1, ' л') : 'объём не задан'} · ${fmtNumber(e.efficiency, 0, ' %')}`,
})))
const chosen = computed(() => equipment.value.find(e => e.id === equipmentId.value) ?? null)
async function added(e: { id: string }) {
  await refreshEquipment()
  equipmentId.value = e.id
}

watch(open, (on) => {
  if (!on) return
  day.value = today()
  picked.value = props.recipeId
  equipmentId.value = main.value?.id
  if (!props.recipeId && !recipes.value.length) execute()
})
watch(main, (m) => { equipmentId.value ??= m?.id })

// предпросмотр: что станет с рецептом на этом оборудовании
const scaled = computed(() => (recipe.value && chosen.value ? scaleRecipe(recipe.value, chosen.value) : null))
const factors = computed(() => (recipe.value && chosen.value ? scaleFactors(recipe.value, chosen.value) : null))
const unchanged = computed(() => !!factors.value && factors.value.kv === 1 && factors.value.kg === 1)
const warnings = computed(() => (scaled.value && chosen.value ? kettleWarnings(scaled.value, chosen.value) : []))
const packs = (r: Recipe) => (r.yeasts ?? []).filter(y => y.amount != null)
  .map(y => `${fmtNumber(y.amount, 1)} ${unitLabel(y.unit)}`).join(' + ')
const rows = computed(() => {
  const r = recipe.value
  const s = scaled.value
  if (!r || !s || !chosen.value) return []
  const v = waterVolumes(s, chosen.value.evaporation)
  const row = (label: string, from: string, to: string) => ({ label, from: from === to ? null : from, to })
  return [
    totalKg(r.fermentables ?? []) > 0 && row('Засыпь', fmtNumber(totalKg(r.fermentables ?? []), 2, ' кг'), fmtNumber(totalKg(s.fermentables ?? []), 2, ' кг')),
    hopGrams(r) > 0 && row('Хмель', fmtNumber(hopGrams(r), 0, ' г'), fmtNumber(hopGrams(s), 0, ' г')),
    packs(r) && row('Дрожжи', packs(r), packs(s)),
    v.mash != null && v.sparge != null && row('Вода', '', `затор ${fmtNumber(v.mash, 1, ' л')} · промывка ${fmtNumber(v.sparge, 1, ' л')}`),
  ].filter(Boolean) as { label: string; from: string | null; to: string }[]
})
const figures = computed(() => {
  const t = scaled.value?.targets
  if (!t?.og) return null
  return [
    `OG ${fmtGravity(t.og, prefs.gravityUnit)}`,
    t.ibu != null && `${Math.round(t.ibu)} IBU`,
    t.ebc != null && `${Math.round(t.ebc)} EBC`,
    t.abv != null && fmtAbv(t.abv),
  ].filter(Boolean).join(' · ')
})

async function create() {
  if (!picked.value) return
  // сегодня — время записи; другой день — его полдень по местному времени
  const startedAt = day.value === today() ? undefined : new Date(`${day.value}T12:00`).getTime() / 1000
  const brew = await exec(() => $api('/api/brews', { method: 'POST', body: { recipeId: picked.value!, startedAt, equipmentId: equipmentId.value } }))
  if (!brew) return
  // подключённая пивоварня: программа партии — сразу в неё; не вышло (не в сети, программа идёт) — со страницы партии
  if (chosen.value?.connected && startedAt === undefined) {
    await exec(() => $api('/api/brews/{bid}/upload', { method: 'POST', path: { bid: brew.id } }), 'Программа партии в пивоварне')
  }
  open.value = false
  await navigateTo(`/brews/${brew.id}`)
}
</script>

<template>
  <UModal v-model:open="open" title="Сварить" :description="recipe ? `По рецепту «${recipe.name}»` : 'По своему рецепту или из каталога'">
    <template #body>
      <form id="brew-start" class="space-y-5" @submit.prevent="create">
        <UFormField v-if="!recipeId" label="Рецепт">
          <USelectMenu v-model="picked" :items="items" value-key="value" placeholder="Выберите рецепт" size="lg" class="w-full" />
        </UFormField>

        <UFormField label="На чём варите">
          <URadioGroup v-if="equipmentItems.length" v-model="equipmentId" :items="equipmentItems" variant="card" size="lg" />
          <p v-else class="rounded-lg bg-elevated/50 px-4 py-3 text-sm text-muted">
            Нет ни одной варочной системы. Добавьте кастрюлю, котёл или пивоварню — рецепт пересчитается под её объём и эффективность.
          </p>
          <UButton label="Добавить варочную систему" icon="i-lucide-plus" color="neutral" variant="ghost" size="lg" class="mt-1" @click="adding = true" />
        </UFormField>

        <div v-if="loading" class="flex items-center gap-2 text-sm text-muted">
          <UIcon name="i-lucide-loader-circle" class="size-4 animate-spin" />Читаю рецепт…
        </div>
        <div v-else-if="scaled && chosen && recipe" class="space-y-3 rounded-lg bg-elevated/50 px-4 py-3">
          <div class="text-base font-medium text-highlighted">
            <template v-if="unchanged">Как в рецепте: {{ batchLine(scaled) }}</template>
            <template v-else>Под «{{ chosen.name }}»: {{ batchLine(scaled) }} <span class="font-normal text-muted">— в рецепте {{ batchLine(recipe) }}</span></template>
          </div>
          <dl v-if="rows.length" class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
            <template v-for="r in rows" :key="r.label">
              <dt class="text-muted">{{ r.label }}</dt>
              <dd class="num text-highlighted">
                <template v-if="r.from"><span class="text-dimmed line-through">{{ r.from }}</span> → </template>{{ r.to }}
              </dd>
            </template>
          </dl>
          <div v-if="figures" class="num text-sm text-muted">{{ figures }}</div>
          <UAlert v-for="w in warnings" :key="w" :title="w" color="warning" variant="subtle" icon="i-lucide-triangle-alert" />
        </div>

        <UFormField label="День варки">
          <UInput v-model="day" type="date" :max="today()" size="lg" />
        </UFormField>
      </form>
      <EquipmentModal v-model:open="adding" systems-only @saved="added" />
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton label="Отмена" color="neutral" variant="ghost" size="lg" @click="open = false" />
        <UButton type="submit" form="brew-start" label="Сварить" icon="i-lucide-flame" size="lg" :loading="pending" :disabled="!picked || loading" />
      </div>
    </template>
  </UModal>
</template>
