<script setup lang="ts">
// Настройки: аккаунт и пивоварня — на сервисе, уведомления, единицы и звук — для этого устройства.
// Разделы — components/settings/.
definePageMeta({ auth: 'user', teaser: 'settings', title: 'Настройки' })
</script>

<template>
  <UDashboardPanel id="settings">
    <template #header>
      <UDashboardNavbar title="Настройки">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="mx-auto w-full max-w-3xl space-y-6">
        <SettingsAccountCard />
        <SettingsConnectionCard />
        <SettingsCalibrationCard />
        <!-- якорь: на него ссылается редактор рецепта (испарение) -->
        <SettingsEquipmentCard id="equipment" />
        <SettingsNotificationsCard />
        <SettingsUnitsCard />
        <SettingsSoundCard />
      </div>
    </template>
  </UDashboardPanel>
</template>
