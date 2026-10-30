<script setup lang="ts">
// Настройки по группам — вкладками со своими адресами: профиль и аккаунт; пивоварня (подключение, калибровка,
// оборудование); уведомления, единицы и звук — для этого устройства. Группы — pages/settings/, разделы — components/settings/.
definePageMeta({ auth: 'user', teaser: 'settings', title: 'Настройки' })

const TABS = [
  { label: 'Профиль', icon: 'i-lucide-user', to: '/settings', exact: true },
  { label: 'Оборудование', icon: 'i-lucide-cooking-pot', to: '/settings/brewery' },
  { label: 'Уведомления и вид', icon: 'i-lucide-bell', to: '/settings/notifications' },
]
</script>

<template>
  <UDashboardPanel id="settings">
    <template #header>
      <UDashboardNavbar title="Настройки">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <UNavigationMenu :items="TABS" highlight class="-mx-1 flex-1" :ui="{ link: 'text-base gap-2', linkLeadingIcon: 'size-5' }" />
      </UDashboardToolbar>
    </template>

    <template #body>
      <div class="mx-auto w-full max-w-3xl space-y-6">
        <NuxtPage />
      </div>
    </template>
  </UDashboardPanel>
</template>
