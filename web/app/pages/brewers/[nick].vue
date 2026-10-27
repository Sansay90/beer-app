<script setup lang="ts">
// Страница пивовара: аватар, ник, с какого времени на сайте и его опубликованные рецепты (свои — все).
// Рендерится на сервере — для поисковиков и превью ссылок. Почты здесь нет: её сервис никому не отдаёт.
const route = useRoute()
const { $api } = useNuxtApp()
const auth = useAuthStore()
const brewery = useBreweryStore()

const nick = computed(() => String(route.params.nick))
const { data: brewer, error } = await useAsyncData(
  () => `brewer:${nick.value.toLowerCase()}`,
  () => $api('/api/brewers/{nick}', { path: { nick: nick.value } }),
)
if (error.value) {
  throw createError({ status: isOffline(error.value) ? 503 : errorStatus(error.value) ?? 500, message: errorText(error.value), fatal: true })
}

const { data: recipes, status } = useApi('/api/recipes', {
  query: { author: nick },
  key: () => `brewer-recipes:${nick.value.toLowerCase()}`,
  watch: [() => auth.user?.id],
  default: () => [],
})
const loaded = computed(() => status.value === 'success')
const isMe = computed(() => !!auth.user && auth.user.id === brewer.value?.id)

const since = computed(() => brewer.value
  ? new Date(brewer.value.joinedAt * 1000).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
  : '')
const count = computed(() => {
  const n = brewer.value?.recipes ?? 0
  return n ? `${n} ${plural(n, 'рецепт', 'рецепта', 'рецептов')}` : 'пока без опубликованных рецептов'
})

useSeoMeta({
  title: () => `Пивовар ${brewer.value?.name ?? nick.value}`,
  description: () => `Рецепты домашнего пива пивовара ${brewer.value?.name ?? nick.value}.`,
})
</script>

<template>
  <UDashboardPanel id="brewer">
    <template #header>
      <UDashboardNavbar :title="brewer?.name ?? nick">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template v-if="isMe" #right>
          <UButton label="Изменить профиль" icon="i-lucide-pencil" color="neutral" variant="outline" to="/settings" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="brewer" class="mx-auto w-full max-w-7xl space-y-8">
        <div class="flex items-center gap-5">
          <UserAvatar :user="brewer" class="size-24" />
          <div class="min-w-0">
            <h1 class="truncate text-4xl font-semibold text-highlighted">{{ brewer.name }}</h1>
            <p class="mt-1 text-base text-muted">На сайте с {{ since }}, {{ count }}</p>
          </div>
        </div>

        <div v-if="recipes.length" class="grid auto-rows-fr gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <RecipeCard v-for="r in recipes" :key="r.id" :recipe="r" :in-device="r.id === brewery.snapshot?.deviceRecipe?.id" />
        </div>
        <UEmpty
          v-else-if="loaded"
          icon="i-lucide-book-open"
          :title="isMe ? 'У вас пока нет рецептов' : 'Опубликованных рецептов пока нет'"
          variant="naked"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
