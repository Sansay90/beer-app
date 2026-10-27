<script setup lang="ts">
// Каталог: опубликованные рецепты и свои. Рендерится на сервере — для поисковиков и превью ссылок.
const brewery = useBreweryStore()
const auth = useAuthStore()

const DESCRIPTION = 'Рецепты домашнего пива от пивоваров: засыпь, хмель, дрожжи, вода и программа затирания. '
  + 'Плотность, горечь, цвет и крепость считаются по ингредиентам.'
useSeoMeta({ title: 'Рецепты пива', description: DESCRIPTION, ogTitle: 'Рецепты пива', ogDescription: DESCRIPTION, ogType: 'website' })

// опубликованные рецепты всех и свои; после входа и выхода список другой
const { data: list, status, error } = useApi('/api/recipes', { key: 'recipes', watch: [() => auth.user?.id], default: () => [] })
const loaded = computed(() => status.value === 'success')
useErrorToast(error)

// раздел — из адреса, его выбирают в меню: ?scope=mine — только свои (и неопубликованные), ?scope=favorites — избранные.
// Гостю — всегда все: своих и избранных у него нет
const route = useRoute()
const scope = computed<'all' | 'mine' | 'favorites'>(() => {
  const s = route.query.scope
  return auth.user && (s === 'mine' || s === 'favorites') ? s : 'all'
})
const title = computed(() => ({ all: 'Рецепты', mine: 'Мои рецепты', favorites: 'Избранное' })[scope.value])

const query = ref('')
const styleCode = ref<string>('all')
const sort = ref<'recent' | 'name' | 'brews'>('recent')

const styleItems = computed(() => {
  const seen = new Map<string, string>()
  for (const r of list.value) {
    if (r.style) seen.set(r.style.code ?? 'custom', r.style.code ? styleLabel(r.style) : 'Авторские')
  }
  return [{ label: 'Все стили', value: 'all' }, ...[...seen].sort((a, b) => a[1].localeCompare(b[1])).map(([value, label]) => ({ label, value }))]
})

const SORTS = [
  { label: 'Недавние', value: 'recent' },
  { label: 'По названию', value: 'name' },
  { label: 'Чаще варили', value: 'brews' },
]

const shown = computed(() => {
  const q = query.value.trim().toLowerCase()
  const found = list.value.filter((r) => {
    if (scope.value === 'mine' && !r.mine) return false
    if (scope.value === 'favorites' && !r.favorite) return false
    const key = r.style ? r.style.code ?? 'custom' : null
    if (styleCode.value !== 'all' && key !== styleCode.value) return false
    return !q || r.name.toLowerCase().includes(q) || r.style?.name.toLowerCase().includes(q) || r.style?.code?.toLowerCase() === q
  })
  if (sort.value === 'name') return [...found].sort((a, b) => a.name.localeCompare(b.name, 'ru'))
  if (sort.value === 'brews') return [...found].sort((a, b) => b.brews - a.brews || (b.lastBrewedAt ?? 0) - (a.lastBrewedAt ?? 0))
  return found                             // сервис отдаёт недавно изменённые первыми
})
</script>

<template>
  <UDashboardPanel id="recipes">
    <template #header>
      <UDashboardNavbar :title="title">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton v-if="auth.user" icon="i-lucide-plus" label="Новый рецепт" to="/recipes/new" />
          <UButton v-else icon="i-lucide-plus" label="Добавить свой рецепт" to="/recipes/new" variant="soft" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UEmpty
        v-if="loaded && !list.length && !auth.user"
        icon="i-lucide-book-open"
        title="Опубликованных рецептов пока нет"
        description="Здесь появятся рецепты, которыми поделились пивовары."
        :actions="[{ label: 'Добавить свой рецепт', icon: 'i-lucide-plus', to: '/recipes/new' }]"
        variant="naked"
        class="m-auto"
      />
      <UEmpty
        v-else-if="loaded && !list.length"
        icon="i-lucide-book-open"
        title="Рецептов пока нет"
        description="Засыпь, хмель, дрожжи и программа для пивоварни — всё в одном рецепте."
        :actions="[{ label: 'Новый рецепт', icon: 'i-lucide-plus', to: '/recipes/new' }]"
        variant="naked"
        class="m-auto"
      />

      <div v-else class="mx-auto w-full max-w-7xl space-y-5">
        <div class="flex flex-wrap items-center gap-2">
          <UInput v-model="query" icon="i-lucide-search" placeholder="Название или стиль" class="min-w-56 flex-1 sm:max-w-80" />
          <USelect v-model="styleCode" :items="styleItems" class="min-w-44" />
          <span class="flex-1" />
          <USelect v-model="sort" :items="SORTS" icon="i-lucide-arrow-up-down" variant="ghost" class="min-w-40" />
        </div>

        <div v-if="shown.length" class="grid auto-rows-fr gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <RecipeCard
            v-for="r in shown"
            :key="r.id"
            :recipe="r"
            :in-device="r.id === brewery.snapshot?.deviceRecipe?.id"
          />
        </div>
        <UEmpty
          v-else-if="loaded && scope === 'mine' && !list.some(r => r.mine)"
          icon="i-lucide-notebook-pen"
          title="Своих рецептов пока нет"
          description="Новый рецепт виден только вам, пока вы его не опубликуете."
          :actions="[{ label: 'Новый рецепт', icon: 'i-lucide-plus', to: '/recipes/new' }]"
          variant="naked"
        />
        <UEmpty
          v-else-if="loaded && scope === 'favorites' && !list.some(r => r.favorite)"
          icon="i-lucide-bookmark"
          title="В избранном пока пусто"
          description="Отмечайте рецепты закладкой — они появятся здесь."
          :actions="[{ label: 'Все рецепты', icon: 'i-lucide-book-open', to: '/recipes' }]"
          variant="naked"
        />
        <UEmpty v-else-if="loaded" icon="i-lucide-search-x" title="Ничего не нашлось" description="Измените запрос или фильтр по стилю." variant="naked" />
      </div>
    </template>
  </UDashboardPanel>
</template>
