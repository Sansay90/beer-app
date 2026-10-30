<script setup lang="ts">
// Мои варки — журнал пивовара: все варки по всем рецептам, новые первыми, с тем, где партия сейчас
// (варка идёт, брожение — какой день, разлито); с пивоварни — сами, остальные — «Сварить».
import type { BrewSummary } from '~/types'

definePageMeta({ auth: 'user', title: 'Мои варки' })

const prefs = usePreferencesStore()
const now = useNow({ interval: 60_000 })
const stage = (b: BrewSummary) => batchStatus(b, now.value.getTime() / 1000)
const { data: brews, status, error } = useApi('/api/brews', { key: 'my-brews', default: () => [] })
useErrorToast(error)
const creating = ref(false)

const date = (t: number) => new Date(t * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
</script>

<template>
  <UDashboardPanel id="brews">
    <template #header>
      <UDashboardNavbar title="Мои варки">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton label="Сварить" icon="i-lucide-flame" @click="creating = true" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="mx-auto w-full max-w-4xl">
        <UCard v-if="brews.length" :ui="{ body: 'p-0 sm:p-0' }">
          <ul class="divide-y divide-default">
            <li v-for="b in brews" :key="b.id">
              <NuxtLink :to="`/brews/${b.id}`" class="flex items-center gap-4 px-4 py-4 transition hover:bg-elevated/60 sm:px-6">
                <UIcon :name="b.manual ? 'i-lucide-notebook-pen' : 'i-lucide-flame'" class="size-6 shrink-0 text-muted" />
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-baseline gap-x-2">
                    <span class="truncate text-base font-semibold text-highlighted">{{ b.name }}</span>
                    <UBadge v-if="stage(b)" :label="stage(b)!.label" :color="stage(b)!.color" variant="subtle" size="sm" />
                  </div>
                  <div class="num text-sm text-muted">
                    {{ date(b.startedAt) }} · {{ equipmentLabel(b) }}<template v-if="b.entries"> · {{ b.entries }} {{ plural(b.entries, 'запись', 'записи', 'записей') }}</template>
                  </div>
                  <div v-if="brewFacts(b, prefs.gravityUnit)" class="num mt-0.5 text-sm text-toned sm:hidden">{{ brewFacts(b, prefs.gravityUnit) }}</div>
                </div>
                <span v-if="brewFacts(b, prefs.gravityUnit)" class="num hidden shrink-0 text-base text-toned sm:block">{{ brewFacts(b, prefs.gravityUnit) }}</span>
                <UIcon name="i-lucide-chevron-right" class="size-5 shrink-0 text-dimmed" />
              </NuxtLink>
            </li>
          </ul>
        </UCard>
        <UEmpty
          v-else-if="status === 'success'"
          icon="i-lucide-notebook-pen"
          title="Варок пока нет"
          description="Найдите рецепт в каталоге или запишите свой и нажмите «Сварить»: партия получит рецепт под ваше оборудование, а здесь — журнал, замеры и брожение. Варки на подключённой пивоварне появляются сами."
          :actions="[{ label: 'Сварить', icon: 'i-lucide-flame', onClick: () => { creating = true } }, { label: 'К рецептам', icon: 'i-lucide-book-open', color: 'neutral', variant: 'outline', to: '/recipes' }]"
          variant="naked"
        />
      </div>
      <BrewStartModal v-model:open="creating" />
    </template>
  </UDashboardPanel>
</template>
