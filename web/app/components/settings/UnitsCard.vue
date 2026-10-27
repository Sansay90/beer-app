<script setup lang="ts">
const prefs = usePreferencesStore()

const GRAVITY_UNITS = [
  { label: '°P — Плато', value: 'plato' },
  { label: 'SG — удельная плотность', value: 'sg' },
]
</script>

<template>
  <UCard>
    <template #header>
      <div class="font-semibold text-highlighted">Единицы</div>
      <div class="text-sm text-muted">Как показывать плотность в рецептах. Настраивается для каждого устройства отдельно.</div>
    </template>
    <UFormField label="Плотность">
      <URadioGroup v-model="prefs.gravityUnit" :items="GRAVITY_UNITS" orientation="horizontal" />
    </UFormField>
  </UCard>
</template>
