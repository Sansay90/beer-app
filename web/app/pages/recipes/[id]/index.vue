<script setup lang="ts">
import type { BrewSummary, Recipe } from '~/types'

const route = useRoute()
const recipes = useRecipesStore()
const brewery = useBreweryStore()
const equipment = useEquipmentStore()
const { exec, pending } = useCommand()
const confirm = useConfirm()

const id = computed(() => route.params.id as string)
const recipe = ref<Recipe | null>(null)
const brews = ref<BrewSummary[]>([])

async function load() {
  recipe.value = null
  const r = await exec(() => recipes.get(id.value))
  if (!r) return navigateTo('/recipes', { replace: true })
  recipe.value = r
  if (!equipment.value) await exec(equipment.fetch)
  brews.value = (await exec(() => recipes.brews(id.value))) ?? []
}
watch(id, load, { immediate: true })

const style = computed(() => styleByCode(recipe.value?.style?.code))
const styleLine = computed(() => styleLabel(recipe.value?.style))
const inDevice = computed(() => brewery.snapshot?.deviceRecipe?.id === id.value)
const programActive = computed(() => brewery.phase.running || brewery.phase.paused)
const steps = computed(() => (recipe.value ? programOf(recipe.value, brewery.limits?.boilTemp) : []))
const groups = computed(() => (recipe.value ? boilGroups(recipe.value) : []))
const kg = computed(() => totalKg(recipe.value?.fermentables ?? []))
const volumes = computed(() => waterVolumes(recipe.value ?? {}, equipment.value?.evaporation))
const hopGrams = computed(() => (recipe.value?.hops ?? []).reduce((a, h) => a + (h.amount ?? 0), 0))

const num = (v: number | null | undefined, digits = 0, unit = '') =>
  v == null ? '—' : `${v.toLocaleString('ru-RU', { maximumFractionDigits: digits })}${unit}`

// показатели — по ингредиентам, как в редакторе (сохранённые targets — снимок для списка); цифры — в панели «Стиль»
const calc = computed(() => (recipe.value ? calcRecipe(recipe.value) : null))

const batch = computed(() => [
  { label: 'Объём после кипячения', value: num(recipe.value?.batch?.volume, 1, ' л') },
  { label: 'Эффективность', value: num(recipe.value?.batch?.efficiency, 0, ' %') },
  { label: 'Засыпь', value: kg.value ? num(kg.value, 2, ' кг') : '—' },
  { label: 'Хмель', value: hopGrams.value ? num(hopGrams.value, 1, ' г') : '—' },
])

const FERMENTABLE_ICONS = { grain: 'i-lucide-wheat', adjunct: 'i-lucide-bean', sugar: 'i-lucide-candy', extract: 'i-lucide-beaker' }
const BREW_STATUS = {
  finished: { label: 'завершена', color: 'success' as const },
  stopped: { label: 'прервана', color: 'warning' as const },
  running: { label: 'идёт', color: 'info' as const },
}

const uploadHint = computed(() => {
  if (!steps.value.length) return 'В рецепте нет программы — добавьте паузы или кипячение'
  if (!brewery.online) return 'Пивоварня не в сети'
  if (programActive.value) return 'Программа идёт — заменить рецепт можно после её окончания'
  return 'Записать программу рецепта в пивоварню'
})

async function upload() {
  const current = brewery.snapshot?.deviceRecipe
  const ok = await confirm({
    title: 'Загрузить в пивоварню?',
    description: current
      ? `${current.name ? `«${current.name}»` : 'Текущая программа'} будет заменена на «${recipe.value!.name}».`
      : `В пивоварню запишется «${recipe.value!.name}».`,
    confirmLabel: 'Загрузить',
    confirmIcon: 'i-lucide-upload',
  })
  if (ok) await exec(() => recipes.upload(id.value), 'Рецепт загружен в пивоварню')
}

async function remove() {
  const ok = await confirm({
    title: 'Удалить рецепт?',
    description: `«${recipe.value?.name}» будет удалён без возможности восстановления. История варок останется.`,
    confirmLabel: 'Удалить',
    confirmIcon: 'i-lucide-trash-2',
    color: 'error',
  })
  if (ok && await exec(() => recipes.remove(id.value), 'Рецепт удалён')) navigateTo('/recipes')
}

const menu = computed(() => [
  [{ label: 'Дублировать', icon: 'i-lucide-copy', to: { path: '/recipes/new', query: { from: id.value } } }],
  [{ label: 'Удалить', icon: 'i-lucide-trash-2', color: 'error' as const, onSelect: remove }],
])
</script>

<template>
  <UDashboardPanel id="recipe">
    <template #header>
      <UDashboardNavbar :title="recipe?.name ?? 'Рецепт'">
        <template #leading>
          <UButton icon="i-lucide-arrow-left" color="neutral" variant="ghost" to="/recipes" aria-label="К рецептам" />
        </template>
        <template v-if="recipe" #right>
          <UBadge v-if="inDevice" color="success" variant="subtle" icon="i-lucide-check" label="в пивоварне" class="hidden sm:inline-flex" />
          <UButton icon="i-lucide-pencil" label="Изменить" color="neutral" variant="outline" :to="`/recipes/${id}/edit`" />
          <UTooltip :text="uploadHint">
            <UButton
              icon="i-lucide-upload"
              label="В пивоварню"
              :loading="pending"
              :disabled="!steps.length || !brewery.online || programActive"
              @click="upload"
            />
          </UTooltip>
          <UDropdownMenu :items="menu" :content="{ align: 'end' }">
            <UButton icon="i-lucide-ellipsis-vertical" color="neutral" variant="ghost" aria-label="Ещё" />
          </UDropdownMenu>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="!recipe" class="m-auto">
        <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin text-muted" />
      </div>

      <div v-else class="mx-auto grid w-full max-w-7xl gap-6 pb-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div class="min-w-0 space-y-6">
          <!-- шапка: бокал, название, стиль, описание, фото пива -->
          <UCard :ui="{ body: 'p-5 sm:p-6' }">
            <div class="flex items-center gap-4">
              <RecipeGlass :ebc="calc?.ebc" :style-code="recipe.style?.code" class="h-20" />
              <div class="min-w-0">
                <h1 class="truncate text-2xl font-semibold text-highlighted">{{ recipe.name }}</h1>
                <div class="truncate text-muted">{{ styleLine }}</div>
              </div>
            </div>
            <RecipeDescription v-if="recipe.notes" :text="recipe.notes" class="mt-5 max-w-3xl" />
            <RecipePhotos :recipe-id="id" class="mt-5" />
          </UCard>

          <RecipeWaterSummary v-if="recipe.water && (recipe.water.ratio || recipe.water.additions?.length)" :water="recipe.water" :volumes="volumes" />

          <RecipeSection v-if="recipe.fermentables?.length" title="Засыпь" icon="i-lucide-wheat" :summary="num(kg, 2, ' кг')">
            <ul class="divide-y divide-default">
              <li v-for="(f, i) in recipe.fermentables" :key="i" class="grid grid-cols-[1.25rem_minmax(0,1fr)_auto_3.5rem] items-center gap-3 py-2 sm:grid-cols-[1.25rem_minmax(0,1fr)_7rem_5rem_3.5rem]">
                <UIcon :name="FERMENTABLE_ICONS[f.kind ?? 'grain']" class="size-4 text-muted" />
                <div class="min-w-0">
                  <div class="truncate text-highlighted">{{ f.name || FERMENTABLE_KINDS[f.kind ?? 'grain'] }}</div>
                  <div v-if="f.use && f.use !== 'mash'" class="text-xs text-muted">{{ whenLabel(FERMENTABLE_USES, f.use, f.minutes) }}</div>
                </div>
                <span class="num hidden text-right text-sm text-muted sm:block">{{ f.ebc != null ? `${num(f.ebc, 1)} EBC` : '' }}</span>
                <span class="num text-right text-highlighted">{{ num(f.amount, 3, ' кг') }}</span>
                <span class="num text-right text-sm text-muted">{{ share(f.amount, kg) == null ? '' : `${share(f.amount, kg)!.toFixed(0)} %` }}</span>
              </li>
            </ul>
          </RecipeSection>

          <RecipeSection v-if="recipe.hops?.length" title="Хмель" icon="i-lucide-hop" :summary="num(hopGrams, 1, ' г')">
            <ul class="divide-y divide-default">
              <li v-for="(h, i) in recipe.hops" :key="i" class="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-3 py-2 sm:grid-cols-[1.25rem_minmax(0,1fr)_5rem_5rem]">
                <UIcon name="i-lucide-hop" class="size-4 text-success" />
                <div class="min-w-0">
                  <div class="truncate text-highlighted">{{ h.name || 'Хмель' }}</div>
                  <div class="text-xs text-muted">{{ whenLabel(HOP_USES, h.use ?? 'boil', h.minutes, h.day) }}</div>
                </div>
                <span class="num hidden text-right text-sm text-muted sm:block">{{ h.alpha != null ? `α ${num(h.alpha, 1)} %` : '' }}</span>
                <span class="num text-right text-highlighted">{{ num(h.amount, 1, ' г') }}</span>
              </li>
            </ul>
          </RecipeSection>

          <RecipeSection v-if="recipe.yeasts?.length" title="Дрожжи" icon="i-lucide-microscope">
            <ul class="divide-y divide-default">
              <li v-for="(y, i) in recipe.yeasts" :key="i" class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 py-2">
                <div class="min-w-0">
                  <div class="truncate text-highlighted">{{ y.name }}</div>
                  <div class="text-xs text-muted">
                    {{ YEAST_FORMS[y.form ?? 'dry'] }}<template v-if="y.attenuation != null"> · сбраживание {{ num(y.attenuation) }} %</template>
                  </div>
                </div>
                <span class="num text-right text-highlighted">{{ y.amount != null ? `${num(y.amount, 1)} ${unitLabel(y.unit)}` : '' }}</span>
              </li>
            </ul>
          </RecipeSection>

          <RecipeSection v-if="recipe.miscs?.length" title="Другое" icon="i-lucide-flask-conical">
            <ul class="divide-y divide-default">
              <li v-for="(m, i) in recipe.miscs" :key="i" class="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-3 py-2">
                <UIcon :name="additionKind(m).icon" class="size-4" :class="additionKind(m).tint" />
                <div class="min-w-0">
                  <div class="truncate text-highlighted">{{ additionName(m) }}</div>
                  <div class="text-xs text-muted">{{ whenLabel(MISC_USES, m.use ?? 'boil', m.minutes) }}</div>
                </div>
                <span class="num text-right text-highlighted">{{ additionAmount(m) ?? '' }}</span>
              </li>
            </ul>
          </RecipeSection>


          <RecipeSection title="Затирание и кипячение" icon="i-lucide-thermometer" :summary="programSummary(recipe)">
            <template v-if="steps.length">
              <RecipeProfile :steps="steps" :groups="groups" class="mb-4" />
              <ul class="divide-y divide-default">
                <li v-for="(s, i) in steps" :key="i" class="flex items-center gap-3 py-2">
                  <span
                    class="num grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold"
                    :class="s.boil ? 'bg-error/10 text-error' : 'bg-primary/10 text-primary'"
                  >
                    <UIcon v-if="s.boil" name="i-lucide-flame" class="size-3.5" />
                    <template v-else>{{ i + 1 }}</template>
                  </span>
                  <span class="min-w-0 flex-1 truncate text-highlighted">{{ s.name }}</span>
                  <span class="num text-sm text-muted">{{ s.boil ? 'кипение' : `${num(s.temp, 1)} °C` }} · {{ s.minutes }} мин · {{ s.watts }} W</span>
                </li>
              </ul>
              <div v-if="groups.length" class="mt-4 space-y-2 rounded-lg bg-elevated/50 p-4">
                <div class="text-xs font-medium uppercase tracking-wider text-dimmed">Закладки на кипячении</div>
                <div v-for="g in groups" :key="g.minutes" class="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-4">
                  <span class="num w-44 shrink-0 text-sm text-muted">{{ whenInBoil(g.minutes, recipe.boil?.minutes) }}</span>
                  <div class="flex flex-wrap gap-x-4 gap-y-1">
                    <span v-for="(item, k) in g.items" :key="k" class="inline-flex items-center gap-1.5 text-sm">
                      <UIcon :name="additionKind(item).icon" class="size-4" :class="additionKind(item).tint" />
                      <span class="text-highlighted">{{ additionName(item) }}</span>
                      <span v-if="additionAmount(item)" class="num text-muted">{{ additionAmount(item) }}</span>
                    </span>
                  </div>
                </div>
              </div>
            </template>
            <p v-else class="text-sm text-muted">Пауз и кипячения нет — добавьте их в редакторе, чтобы загрузить рецепт в пивоварню.</p>
          </RecipeSection>

          <RecipeSection v-if="recipe.fermentation?.length" title="Брожение" icon="i-lucide-thermometer-snowflake">
            <ul class="divide-y divide-default">
              <li v-for="(s, i) in recipe.fermentation" :key="i" class="flex items-center gap-3 py-2">
                <span class="min-w-0 flex-1 truncate text-highlighted">{{ s.name || `Этап ${i + 1}` }}</span>
                <span class="num text-sm text-muted">{{ num(s.temp, 1) }} °C · {{ num(s.days, 1) }} дн.</span>
              </li>
            </ul>
          </RecipeSection>
        </div>

        <aside class="space-y-4 xl:sticky xl:top-0 xl:self-start">
          <UCard :ui="{ body: 'p-5 sm:p-5' }">
            <div class="mb-4 text-xs font-medium uppercase tracking-wider text-dimmed">Стиль</div>
            <RecipeStyleRanges :bjcp="style" :custom="!!recipe.style && !recipe.style.code" :og="calc?.og" :fg="calc?.fg" :ibu="calc?.ibu" :ebc="calc?.ebc" />
          </UCard>

          <UCard :ui="{ body: 'p-5 sm:p-5' }">
            <div class="mb-3 text-xs font-medium uppercase tracking-wider text-dimmed">Партия</div>
            <dl class="space-y-1.5 text-sm">
              <div v-for="b in batch" :key="b.label" class="flex justify-between gap-3">
                <dt class="text-muted">{{ b.label }}</dt>
                <dd class="num text-right" :class="b.value === '—' ? 'text-dimmed' : 'text-highlighted'">{{ b.value }}</dd>
              </div>
            </dl>
          </UCard>

          <UCard :ui="{ body: 'p-5 sm:p-5' }">
            <div class="mb-3 text-xs font-medium uppercase tracking-wider text-dimmed">Варки</div>
            <ul v-if="brews.length" class="space-y-2">
              <li v-for="b in brews" :key="b.id" class="flex items-center gap-3 text-sm">
                <span class="num min-w-0 flex-1 text-highlighted">{{ new Date(b.startedAt * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }) }}</span>
                <span v-if="b.energyWh" class="num text-muted">{{ fmtEnergy(b.energyWh) }}</span>
                <UBadge :color="BREW_STATUS[b.status].color" variant="subtle" size="sm" :label="BREW_STATUS[b.status].label" />
              </li>
            </ul>
            <p v-else class="text-sm text-muted">Ещё не варили.</p>
          </UCard>
        </aside>
      </div>
    </template>
  </UDashboardPanel>
</template>
