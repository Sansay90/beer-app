<script setup lang="ts">
const recipes = useRecipesStore()
const brewery = useBreweryStore()
const auth = useAuthStore()
const { exec } = useCommand()

// опубликованные рецепты всех и свои; «Мои» — только свои, в том числе неопубликованные
const scope = ref<'all' | 'mine'>('all')
const SCOPES = [{ label: 'Все', value: 'all' }, { label: 'Мои', value: 'mine' }]

const query = ref('')
const styleCode = ref<string>('all')
const sort = ref<'recent' | 'name' | 'brews'>('recent')

onMounted(() => exec(recipes.fetchList))

const styleItems = computed(() => {
  const seen = new Map<string, string>()
  for (const r of recipes.list) {
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
  const list = recipes.list.filter((r) => {
    if (scope.value === 'mine' && !r.mine) return false
    const key = r.style ? r.style.code ?? 'custom' : null
    if (styleCode.value !== 'all' && key !== styleCode.value) return false
    return !q || r.name.toLowerCase().includes(q) || r.style?.name.toLowerCase().includes(q) || r.style?.code?.toLowerCase() === q
  })
  if (sort.value === 'name') return [...list].sort((a, b) => a.name.localeCompare(b.name, 'ru'))
  if (sort.value === 'brews') return [...list].sort((a, b) => b.brews - a.brews || (b.lastBrewedAt ?? 0) - (a.lastBrewedAt ?? 0))
  return list                              // сервис отдаёт недавно изменённые первыми
})
</script>

<template>
  <UDashboardPanel id="recipes">
    <template #header>
      <UDashboardNavbar title="Рецепты">
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
        v-if="recipes.loaded && !recipes.list.length && !auth.user"
        icon="i-lucide-book-open"
        title="Опубликованных рецептов пока нет"
        description="Здесь появятся рецепты, которыми поделились пивовары."
        :actions="[{ label: 'Добавить свой рецепт', icon: 'i-lucide-plus', to: '/recipes/new' }]"
        variant="naked"
        class="m-auto"
      />
      <UEmpty
        v-else-if="recipes.loaded && !recipes.list.length"
        icon="i-lucide-book-open"
        title="Рецептов пока нет"
        description="Засыпь, хмель, дрожжи и программа для пивоварни — всё в одном рецепте."
        :actions="[{ label: 'Новый рецепт', icon: 'i-lucide-plus', to: '/recipes/new' }]"
        variant="naked"
        class="m-auto"
      />

      <div v-else class="mx-auto w-full max-w-7xl space-y-5">
        <div class="flex flex-wrap items-center gap-2">
          <UTabs v-if="auth.user" v-model="scope" :items="SCOPES" :content="false" size="sm" class="w-auto" />
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
          v-else-if="recipes.loaded && scope === 'mine' && !recipes.list.some(r => r.mine)"
          icon="i-lucide-notebook-pen"
          title="Своих рецептов пока нет"
          description="Новый рецепт виден только вам, пока вы его не опубликуете."
          :actions="[{ label: 'Новый рецепт', icon: 'i-lucide-plus', to: '/recipes/new' }]"
          variant="naked"
        />
        <UEmpty v-else-if="recipes.loaded" icon="i-lucide-search-x" title="Ничего не нашлось" description="Измените запрос или фильтр по стилю." variant="naked" />
      </div>
    </template>
  </UDashboardPanel>
</template>
