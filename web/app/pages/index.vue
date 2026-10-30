<script setup lang="ts">
// «Варка»: идёт партия (варочный день — на пивоварне или без неё) — сразу на её страницу. Иначе — «Сварить»:
// рецепт → партия, и варка живёт там. Состояние и управление пивоварней без партии — у оборудования (настройки).
definePageMeta({ auth: 'user', teaser: 'brew', title: 'Варка' })

const creating = ref(false)
const { list: equipment } = useEquipment()
const paired = computed(() => equipment.value.some(e => e.connected))

const { brew: running, status } = useCurrentBrew()
watch(running, (b) => { if (b) navigateTo(`/brews/${b.id}`, { replace: true }) }, { immediate: true })
</script>

<template>
  <UDashboardPanel id="brew">
    <template #header>
      <UDashboardNavbar title="Варка">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton label="Сварить" icon="i-lucide-flame" @click="creating = true" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <USkeleton v-if="running || status === 'pending'" class="mx-auto h-64 w-full max-w-3xl" />
      <div v-else class="mx-auto w-full max-w-3xl">
        <UCard :ui="{ body: 'p-6 sm:p-8' }">
          <div class="flex items-start gap-4">
            <span class="grid size-12 shrink-0 place-items-center rounded-xl bg-primary/15 text-primary">
              <UIcon name="i-lucide-flame" class="size-7" />
            </span>
            <div>
              <h2 class="text-2xl font-semibold text-highlighted">Сейчас ничего не варится</h2>
              <p class="mt-1 text-base text-muted">
                Выберите рецепт и нажмите «Сварить»: партия получит рецепт под ваше оборудование, а варочный день —
                шаги, замеры, потом брожение и напоминания — будет на её странице.
              </p>
            </div>
          </div>
          <div class="mt-6 flex flex-wrap gap-3">
            <UButton label="Сварить" icon="i-lucide-flame" size="lg" @click="creating = true" />
            <UButton label="Рецепты" icon="i-lucide-book-open" size="lg" color="neutral" variant="outline" to="/recipes" />
            <UButton label="Мои варки" icon="i-lucide-notebook-pen" size="lg" color="neutral" variant="outline" to="/brews" />
            <UButton label="Оборудование" icon="i-lucide-cooking-pot" size="lg" color="neutral" variant="ghost" to="/settings/brewery" />
          </div>
          <p v-if="!paired" class="mt-6 text-sm text-muted">
            Есть Easy Brew Connect? С подключённой пивоварней у партии будут температура вживую, шаги программы
            и напоминания о закладках хмеля.
          </p>
        </UCard>
      </div>
      <BrewStartModal v-model:open="creating" />
    </template>
  </UDashboardPanel>
</template>
