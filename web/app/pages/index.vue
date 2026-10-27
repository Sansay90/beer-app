<script setup lang="ts">
definePageMeta({ auth: 'user', teaser: 'brew', title: 'Варка' })

const brewery = useBreweryStore()
</script>

<template>
  <UDashboardPanel id="brew">
    <template #header>
      <UDashboardNavbar title="Варка">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UBadge
            v-if="brewery.snapshot?.deviceRecipe?.name"
            color="neutral"
            variant="subtle"
            icon="i-lucide-book-open"
            :label="brewery.snapshot.deviceRecipe.name"
            class="hidden sm:inline-flex"
          />
          <UBadge :color="brewery.status.tone" variant="soft" :label="brewery.status.label" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <!-- shrink-0: тело панели — флекс-колонка с прокруткой, а overflow-hidden у плашки иначе разрешает её сплющить -->
      <UAlert
        v-if="!brewery.connected"
        class="shrink-0"
        color="error"
        variant="subtle"
        icon="i-lucide-server"
        title="Нет связи с сервисом"
        description="Переподключаемся сами. Если не выходит долго — обновите страницу."
      />

      <!-- на широком экране — две независимые колонки, на узком — одна, по важности -->
      <div class="flex flex-col gap-4 sm:gap-6 xl:grid xl:grid-cols-12 xl:items-start">
        <div class="contents xl:col-span-8 xl:flex xl:flex-col xl:gap-6">
          <BrewNowCard class="order-1 xl:order-none" />
          <BrewProgramCard class="order-4 xl:order-none" />
          <BrewTempChart class="order-6 xl:order-none" />
        </div>
        <div class="contents xl:col-span-4 xl:flex xl:flex-col xl:gap-6">
          <BrewNextCard class="order-2 xl:order-none" />
          <BrewAdditionsCard class="order-3 xl:order-none" />
          <BrewControlsCard class="order-5 xl:order-none" />
          <BrewEventsCard class="order-7 xl:order-none" />
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
