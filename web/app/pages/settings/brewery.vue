<script setup lang="ts">
// Оборудование пивовара; у подключённой к сайту пивоварни — ещё связь и калибровка. Управление ею — на странице партии.
const { list } = useEquipment()
const paired = computed(() => list.value.some(e => e.connected))
</script>

<template>
  <div class="space-y-6">
    <!-- якорь: на него ссылается редактор рецепта (испарение) -->
    <SettingsEquipmentCard id="equipment" />
    <template v-if="paired">
      <SettingsConnectionCard />
      <SettingsCalibrationCard />
    </template>
  </div>
</template>
