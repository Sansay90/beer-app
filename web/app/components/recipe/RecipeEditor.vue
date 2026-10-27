<script setup lang="ts">
// Создание и правка рецепта. id = null — новый (from — копия существующего).
import type { FitBase } from '~/utils/calc'
import type { RecipeDraft } from '~/types/recipe'

const props = defineProps<{ id: string | null; from?: string | null }>()

const recipes = useRecipesStore()
const brewery = useBreweryStore()
const equipment = useEquipmentStore()
const prefs = usePreferencesStore()
const { exec, pending } = useCommand()
const confirm = useConfirm()

const draft = ref<RecipeDraft | null>(null)
const saved = ref('')                    // сохранённая версия — чтобы знать, есть ли правки

const limits = computed(() => brewery.limits)
const dirty = computed(() => !!draft.value && JSON.stringify(draft.value) !== saved.value)
const errors = computed(() => (draft.value && limits.value ? validateRecipe(draft.value, limits.value) : []))
const back = computed(() => (props.id ? `/recipes/${props.id}` : '/recipes'))

const style = computed(() => styleByCode(draft.value?.style?.code))
const calc = computed(() => (draft.value ? calcRecipe(draft.value) : null))
const volumes = computed(() => waterVolumes(draft.value ?? {}, equipment.value?.evaporation))
const canAdjust = computed(() => (draft.value ? adjustable(draft.value) : {}))

const stats = computed(() => {
  const c = calc.value
  const n = (v: number | null | undefined, digits = 0) => (v == null ? '—' : v.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits }))
  return [
    { label: 'OG', value: fmtGravity(c?.og, prefs.gravityUnit) },
    { label: 'FG', value: fmtGravity(c?.fg, prefs.gravityUnit), note: c?.og && c.defaultAttenuation ? `сбраживание ${c.attenuation} %` : undefined },
    { label: 'ABV', value: c?.abv == null ? '—' : `${n(c.abv, 1)} %` },
    { label: 'IBU', value: n(c?.ibu) },
    { label: 'Цвет', value: c?.ebc == null ? '—' : `${n(c.ebc)} EBC` },
  ]
})

// ползунки рамок стиля: подгонка от снимка ингредиентов на начало перетаскивания
let fitFrom: FitBase | null = null
function adjust(key: 'og' | 'fg' | 'ibu' | 'ebc', value: number) {
  const d = draft.value
  if (!d) return
  fitFrom ??= fitBase(d)
  if (key === 'og') fitOg(d, fitFrom, value)
  else if (key === 'fg') fitFg(d, value)
  else if (key === 'ibu') fitIbu(d, fitFrom, value)
  else fitEbc(d, fitFrom, value)
}
const totals = computed(() => {
  const d = draft.value
  if (!d) return []
  const kg = totalKg(d.fermentables)
  const hops = d.hops.reduce((a, h) => a + (h.amount ?? 0), 0)
  return [
    { label: 'Засыпь', value: kg ? `${kg.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} кг` : '—' },
    { label: 'Хмель', value: hops ? `${hops.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} г` : '—' },
    { label: 'Программа', value: programSummary(d) },
  ]
})

async function load() {
  draft.value = null
  const l = await until(limits).toBeTruthy()
  const eq = equipment.value ?? await exec(equipment.fetch) ?? null
  if (!props.id) {
    const base = props.from ? await exec(() => recipes.get(props.from!)) : undefined
    draft.value = base ? { ...toDraft(base), name: `${base.name} (копия)` } : blankRecipe(l, eq)
    saved.value = ''
    return
  }
  const recipe = await exec(() => recipes.get(props.id!))
  if (!recipe) return navigateTo('/recipes', { replace: true })
  draft.value = toDraft(recipe)
  saved.value = JSON.stringify(draft.value)
}
watch(() => [props.id, props.from], load, { immediate: true })

async function canLeave() {
  return !dirty.value || await confirm({
    title: 'Есть несохранённые изменения',
    description: 'Если уйти, правки в рецепте пропадут.',
    confirmLabel: 'Отбросить изменения',
    color: 'warning',
  })
}
onBeforeRouteLeave(canLeave)

async function save() {
  if (!draft.value || errors.value.length) return
  const savedId = await exec(() => recipes.save(props.id, toRecipe(draft.value!)), 'Рецепт сохранён')
  if (!savedId) return
  saved.value = JSON.stringify(draft.value)
  await navigateTo(`/recipes/${savedId}`, { replace: !props.id })
}
</script>

<template>
  <UDashboardPanel id="recipe-editor">
    <template #header>
      <UDashboardNavbar :title="id ? 'Правка рецепта' : 'Новый рецепт'">
        <template #leading>
          <UButton icon="i-lucide-arrow-left" color="neutral" variant="ghost" :to="back" aria-label="Назад" />
        </template>
        <template v-if="draft" #right>
          <UBadge v-if="dirty" color="warning" variant="subtle" label="не сохранён" class="hidden sm:inline-flex" />
          <UButton color="neutral" variant="ghost" label="Отмена" :to="back" />
          <UButton icon="i-lucide-save" label="Сохранить" :loading="pending" :disabled="!!errors.length || (!!id && !dirty)" @click="save" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="!draft || !limits" class="m-auto">
        <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin text-muted" />
      </div>

      <div v-else class="mx-auto grid w-full max-w-7xl gap-6 pb-6 xl:grid-cols-[minmax(0,1fr)_19rem]">
        <div class="min-w-0 space-y-6">
          <UCard :ui="{ body: 'p-5 sm:p-5 space-y-5' }">
            <UInput v-model="draft.name" placeholder="Название рецепта" size="xl" variant="none" class="w-full" :ui="{ base: 'px-0 text-2xl font-semibold text-highlighted' }" />
            <div class="grid gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
              <UFormField label="Стиль">
                <RecipeStylePicker v-model="draft.style" />
              </UFormField>
              <UFormField label="Объём после кипячения" hint="л">
                <UInputNumber v-model="draft.batch.volume" :min="1" :step="1" :step-snapping="false" :increment="false" :decrement="false" :format-options="{ maximumFractionDigits: 1 }" placeholder="—" class="w-full" />
              </UFormField>
              <UFormField label="Эффективность" hint="%">
                <UInputNumber v-model="draft.batch.efficiency" :min="1" :max="100" :step="1" :step-snapping="false" :increment="false" :decrement="false" placeholder="—" class="w-full" />
              </UFormField>
            </div>
            <UFormField label="Описание">
              <UTextarea v-model="draft.notes" placeholder="Каким получится пиво: вкус, аромат, особенности рецепта. Абзацы — через пустую строку." autoresize :rows="3" :maxrows="14" class="w-full" />
            </UFormField>
            <div>
              <div class="mb-2 text-sm font-medium text-default">Расчёт по ингредиентам</div>
              <dl class="grid grid-cols-3 gap-4 rounded-lg bg-elevated/50 px-4 py-3 sm:grid-cols-5">
                <div v-for="s in stats" :key="s.label">
                  <dt class="text-xs font-medium tracking-wider text-dimmed">{{ s.label }}</dt>
                  <dd class="num mt-0.5 font-semibold" :class="s.value === '—' ? 'text-dimmed' : 'text-highlighted'">{{ s.value }}</dd>
                  <dd v-if="s.note" class="text-[11px] text-dimmed">{{ s.note }}</dd>
                </div>
              </dl>
            </div>
          </UCard>

          <!-- из чего пиво: вода, солод, хмель, дрожжи — потом всё остальное -->
          <RecipeEditorWater v-model="draft.water" :volumes="volumes" :evaporation="equipment.value?.evaporation" :boil-minutes="draft.boil?.minutes ?? 0" />
          <RecipeEditorFermentables v-model="draft.fermentables" />
          <RecipeEditorHops v-model="draft.hops" :boil-minutes="draft.boil?.minutes ?? null" :volume="draft.batch.volume" />
          <RecipeEditorYeasts v-model="draft.yeasts" />
          <RecipeEditorMiscs v-model="draft.miscs" />
          <RecipeEditorProgram v-model="draft" :limits="limits" />
          <RecipeEditorFermentation v-model="draft.fermentation" />
        </div>

        <aside class="space-y-4 xl:sticky xl:top-0 xl:self-start">
          <UCard :ui="{ body: 'p-5 sm:p-5' }">
            <div class="flex items-center gap-3">
              <RecipeGlass :ebc="calc?.ebc" :style-code="draft.style?.code" class="h-14" />
              <div class="min-w-0">
                <div class="truncate font-semibold text-highlighted">{{ draft.name || 'Без названия' }}</div>
                <div class="truncate text-sm text-muted">{{ styleLabel(draft.style) }}</div>
              </div>
            </div>
            <USeparator class="my-4" />
            <RecipeStyleRanges
              :bjcp="style"
              :custom="!!draft.style && !draft.style.code"
              :og="calc?.og"
              :fg="calc?.fg"
              :ibu="calc?.ibu"
              :ebc="calc?.ebc"
              :adjustable="canAdjust"
              @adjust="adjust"
              @commit="fitFrom = null"
            />
            <USeparator class="my-4" />
            <dl class="space-y-1.5 text-sm">
              <div v-for="t in totals" :key="t.label" class="flex justify-between gap-3">
                <dt class="text-muted">{{ t.label }}</dt>
                <dd class="num text-right text-highlighted">{{ t.value }}</dd>
              </div>
            </dl>
          </UCard>

          <UAlert v-if="errors.length" color="error" variant="subtle" icon="i-lucide-circle-alert" title="Пока нельзя сохранить">
            <template #description>
              <ul class="mt-1 list-disc space-y-0.5 pl-4">
                <li v-for="e in errors" :key="e">{{ e }}</li>
              </ul>
            </template>
          </UAlert>
        </aside>
      </div>
    </template>
  </UDashboardPanel>
</template>
