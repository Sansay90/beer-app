<script setup lang="ts">
// Партия — одна страница варки для кастрюли и пивоварни: «Сейчас» (текущий шаг, таймер; на подключённой пивоварне —
// её живое состояние), таймлайн варочного дня из рецепта партии с замерами на своих шагах, итог против плана,
// брожение по плану, журнал, температура с пивоварни, рецепт партии. Изменилась на сервисе (пивоварня сменила
// шаг, закончила программу) — страница освежается сама. День и оборудование задаются один раз, в «Сварить»: рецепт
// партии посчитан под них. Удалить — любую, кроме идущей на пивоварне.
import type { EntryKind } from '~/utils/brewlog'

definePageMeta({ auth: 'user', title: 'Варка' })

const route = useRoute()
const id = computed(() => String(route.params.id))
const { $api } = useNuxtApp()
const confirm = useConfirm()
const { exec } = useCommand()
const prefs = usePreferencesStore()
const { data: brew, status, error, refresh } = useApi('/api/brews/{bid}', { path: { bid: id }, key: () => `brew:${id.value}` })
const missing = computed(() => errorStatus(error.value) === 404)
const showError = useErrorToast()
watch(error, e => e && !missing.value && showError(e))                  // не найдена — об этом говорит страница

const { data: readings, refresh: refreshReadings } = useApi('/api/brews/{bid}/readings', {
  path: { bid: id }, key: () => `readings:${id.value}`, default: () => [],
})
const changed = useBrewChanged()
watch(changed, (c) => {
  if (c?.id !== id.value) return
  refresh()
  refreshReadings()
})
// варочный день закончился здесь (дрожжи, «закончить») — «Варка» в меню больше не ведёт сюда
const { refresh: refreshCurrent } = useCurrentBrew()
watch(() => brew.value?.phase, (p, was) => { if (was && p !== was) refreshCurrent() })

const { list: equipment } = useEquipment()
const brewery = useBreweryStore()
// минуты хватает всему, кроме таймера шага — его секунды считает «Сейчас»
const now = useNow({ interval: 60_000 })
const t = computed(() => now.value.getTime() / 1000)
const stage = computed(() => brew.value && batchStatus(brew.value, t.value))
const date = computed(() => brew.value
  && new Date(brew.value.startedAt * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', weekday: 'long' }))
const eq = computed(() => equipment.value.find(e => e.id === brew.value?.equipment?.id))
const connected = computed(() => !!eq.value?.connected)
const view = computed(() => brew.value && brewDay(brew.value, brewery.snapshot, brewery.phase))

// цифры партии — из рецепта партии
const snapshot = computed(() => brew.value?.snapshot ?? null)
const figures = computed(() => {
  const s = snapshot.value
  if (!s) return []
  const tg = s.targets
  return [
    s.batch?.volume != null && { label: 'партия', value: fmtNumber(s.batch.volume, 1, ' л') },
    tg?.og != null && { label: 'OG по плану', value: fmtGravity(tg.og, prefs.gravityUnit) },
    tg?.ibu != null && { label: 'горечь', value: `${Math.round(tg.ibu)} IBU` },
    tg?.abv != null && { label: 'крепость', value: fmtAbv(tg.abv) },
  ].filter(Boolean) as { label: string; value: string }[]
})

// этап брожения, сухое охмеление, розлив — записи в журнал прямо с таймлайна
async function advanceStage(index: number) {
  if (await exec(() => $api('/api/brews/{bid}/entries', { method: 'POST', path: { bid: id.value }, body: { kind: 'stage', value: index } }))) await refresh()
}
async function entry(kind: 'dry_hop' | 'package', text?: string) {
  // розлив без конечной плотности — крепость не посчитать; спросить
  if (kind === 'package' && brew.value && !lastMeasures(brew.value.entries).get('fg') && !await confirm({
    title: 'Конечная плотность не записана',
    description: 'Без FG не посчитать крепость. Запишите её в «Брожении» или разливайте без записи.',
    confirmLabel: 'Разлито без записи',
    confirmIcon: 'i-lucide-beer',
  })) return
  // у сухого охмеления — состав закладки: по нему таймлайн отмечает именно её
  if (await exec(() => $api('/api/brews/{bid}/entries', { method: 'POST', path: { bid: id.value }, body: { kind, text } }))) await refresh()
}

// замер со шага — форма журнала с нужным видом
const preset = ref<{ kind: EntryKind } | null>(null)
function measure(kind: EntryKind) {
  preset.value = { kind }
  nextTick(() => document.getElementById('journal')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

// рецепт партии: сколько и чего — под объём и эффективность на момент варки; вода — по испарению оборудования
const recipeOpen = ref(false)
const batchLabel = computed(() => {
  const s = snapshot.value
  if (!s) return ''
  const kg = totalKg(s.fermentables ?? [])
  const g = hopGrams(s)
  return [batchLine(s), kg > 0 && `засыпь ${fmtNumber(kg, 2, ' кг')}`, g > 0 && `хмель ${fmtNumber(g, 0, ' г')}`].filter(Boolean).join(' · ')
})
const volumes = computed(() => (snapshot.value ? waterVolumes(snapshot.value, snapshot.value.batch?.evaporation ?? eq.value?.evaporation) : null))

async function finish() {
  const ok = await confirm({
    title: 'Закончить варочный день?',
    description: 'Партия перейдёт к брожению. Запись «задача дрожжей» заканчивает его сама.',
    confirmLabel: 'Закончить',
    confirmIcon: 'i-lucide-check',
  })
  if (ok && await exec(() => $api('/api/brews/{bid}/finish', { method: 'POST', path: { bid: id.value } }))) await refresh()
}

async function remove() {
  if (!await confirm({
    title: 'Удалить варку?',
    description: 'Вместе с журналом. Вернуть её будет нельзя.',
    confirmLabel: 'Удалить',
    confirmIcon: 'i-lucide-trash-2',
    color: 'error',
  })) return
  if (await exec(() => $api('/api/brews/{bid}', { method: 'DELETE', path: { bid: id.value } }))) await navigateTo('/brews')
}

const menu = computed(() => [[
  // пока идёт программа пивоварни, день ведёт она
  ...(brew.value?.phase === 'brewday' && (brew.value.manual || brew.value.status !== 'running') ? [{ label: 'Закончить варочный день', icon: 'i-lucide-check', onSelect: finish }] : []),
  { label: 'Удалить варку', icon: 'i-lucide-trash-2', color: 'error' as const, disabled: brew.value?.status === 'running' && !brew.value.manual, onSelect: remove },
]])
</script>

<template>
  <UDashboardPanel id="brew">
    <template #header>
      <UDashboardNavbar :title="brew?.name ?? 'Варка'">
        <template #leading>
          <UButton icon="i-lucide-arrow-left" color="neutral" variant="ghost" to="/brews" aria-label="Мои варки" />
        </template>
        <template #right>
          <UBadge v-if="connected" :color="brewery.status.tone" variant="soft" :label="brewery.status.label" class="hidden sm:inline-flex" />
          <UDropdownMenu v-if="brew" :items="menu">
            <UButton icon="i-lucide-ellipsis-vertical" color="neutral" variant="ghost" aria-label="Ещё" />
          </UDropdownMenu>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="brew && view" class="mx-auto w-full max-w-6xl space-y-4 sm:space-y-6">
        <UCard :ui="{ body: 'p-5 sm:p-6' }">
          <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:gap-6">
            <div class="min-w-0 sm:flex-1">
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                <NuxtLink v-if="brew.recipeId" :to="`/recipes/${brew.recipeId}`" class="text-2xl font-semibold text-highlighted hover:underline">{{ brew.name }}</NuxtLink>
                <span v-else class="text-2xl font-semibold text-highlighted">{{ brew.name }}</span>
                <UBadge
                  :label="equipmentLabel(brew)"
                  :icon="connected ? 'i-lucide-plug' : 'i-lucide-cooking-pot'"
                  color="neutral"
                  variant="subtle"
                />
                <UBadge v-if="stage" :label="stage.label" :color="stage.color" variant="subtle" />
              </div>
              <div class="mt-1 text-base text-muted first-letter:uppercase">{{ date }}</div>
            </div>
            <dl v-if="figures.length" class="flex flex-wrap gap-x-6 gap-y-2 sm:justify-end">
              <div v-for="f in figures" :key="f.label">
                <dd class="num text-2xl font-semibold text-highlighted">{{ f.value }}</dd>
                <dt class="text-xs text-muted">{{ f.label }}</dt>
              </div>
            </dl>
          </div>
          <BrewPlanFact :brew="brew" class="mt-5" />
        </UCard>

        <!-- рецепт партии — свёрнут: сколько чего взвесить, один раз -->
        <UCollapsible v-if="snapshot" v-model:open="recipeOpen">
          <UButton
            :label="`Рецепт партии · ${batchLabel}`"
            icon="i-lucide-scroll-text"
            :trailing-icon="recipeOpen ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
            color="neutral"
            variant="outline"
            size="lg"
            block
            :ui="{ base: 'justify-start', label: 'flex-1 text-left truncate' }"
          />
          <template #content>
            <div class="mt-4 space-y-4">
              <p class="text-sm text-muted">
                Под объём и эффективность оборудования на день варки; правки оригинала сюда не попадают.
                <NuxtLink v-if="brew.recipeId" :to="`/recipes/${brew.recipeId}`" class="text-primary hover:underline">Открыть оригинал</NuxtLink>
              </p>
              <RecipeWaterSummary v-if="snapshot.water && volumes && (snapshot.water.ratio || snapshot.water.additions?.length)" :water="snapshot.water" :volumes="volumes" />
              <RecipeViewFermentables v-if="snapshot.fermentables?.length" :items="snapshot.fermentables" />
              <RecipeViewHops v-if="snapshot.hops?.length" :items="snapshot.hops" />
              <RecipeViewYeasts v-if="snapshot.yeasts?.length" :items="snapshot.yeasts" />
              <RecipeViewMiscs v-if="snapshot.miscs?.length" :items="snapshot.miscs" />
              <RecipeViewProgram :recipe="snapshot" />
            </div>
          </template>
        </UCollapsible>

        <BrewDayNowCard v-if="view.active && view.steps.length" :brew="brew" :view="view" :connected="connected" @changed="refresh()" />

        <div class="grid gap-4 sm:gap-6 xl:grid-cols-[minmax(0,1fr)_24rem] xl:items-start">
          <div class="min-w-0 space-y-4 sm:space-y-6">
            <UCard v-if="view.steps.length" :ui="{ body: 'p-5 sm:p-6' }">
              <template #header>
                <div class="flex flex-wrap items-baseline justify-between gap-2">
                  <h2 class="text-xl font-semibold text-highlighted">Варка</h2>
                  <span class="num text-sm text-muted">{{ view.steps.length }} {{ plural(view.steps.length, 'шаг', 'шага', 'шагов') }}</span>
                </div>
              </template>
              <BrewDayTimeline :brew="brew" :view="view" :now="t" @measure="measure" @stage="advanceStage" @entry="entry" />
            </UCard>
            <!-- ход брожения и график — когда оно началось; до дрожжей всё есть в таймлайне -->
            <BrewFermentCard v-if="!view.active" :brew="brew" @changed="refresh()" @stage="advanceStage" />
            <BrewTempChart v-if="readings.length > 1" :points="readings" />
          </div>

          <div class="min-w-0 space-y-4 sm:space-y-6">
            <UCard id="journal" :ui="{ body: 'p-5 sm:p-5' }" class="scroll-mt-4">
              <template #header>
                <h2 class="text-xl font-semibold text-highlighted">Журнал</h2>
              </template>
              <BrewLogEntryForm :brew-id="id" :preset="preset" @saved="refresh()" />
              <USeparator class="my-5" />
              <BrewLogTimeline :brew-id="id" :entries="brew.entries" :events="brew.events" @changed="refresh()" />
            </UCard>

            <template v-if="connected">
              <BrewAdditionsCard v-if="view.byBrewery" />
              <BrewControlsCard />
            </template>
          </div>
        </div>
      </div>
      <UEmpty
        v-else-if="missing"
        icon="i-lucide-search-x"
        title="Варка не найдена"
        description="Её удалили или это чужая варка."
        :actions="[{ label: 'Мои варки', to: '/brews', icon: 'i-lucide-arrow-left' }]"
        variant="naked"
      />
      <div v-else-if="status === 'pending'" class="mx-auto w-full max-w-6xl space-y-6">
        <USkeleton class="h-48 w-full" />
        <USkeleton class="h-80 w-full" />
      </div>
    </template>
  </UDashboardPanel>
</template>
