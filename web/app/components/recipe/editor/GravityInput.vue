<script setup lang="ts">
// Плотность в единицах пивовара (°P или SG), хранится в SG — как все плотности.
const value = defineModel<number | null | undefined>({ required: true })
defineProps<{ placeholder?: string; label?: string }>()
const prefs = usePreferencesStore()

const plato = computed(() => prefs.gravityUnit === 'plato')
const shown = computed(() => (value.value == null ? null : gravityIn(value.value, prefs.gravityUnit)))
function set(v: number | null | undefined) {
  value.value = v == null ? null : plato.value ? Math.round(sgFromPlato(v) * 10000) / 10000 : v
}
const format = computed(() => (plato.value
  ? { minimumFractionDigits: 1, maximumFractionDigits: 1 }
  : { minimumFractionDigits: 3, maximumFractionDigits: 3 }))
</script>

<template>
  <UInputNumber
    :model-value="shown"
    :min="plato ? -5 : 0.98"
    :max="plato ? 40 : 1.2"
    :step="plato ? 0.1 : 0.001"
    :step-snapping="false"
    :format-options="format"
    :placeholder="placeholder ?? (plato ? '°P' : 'SG')"
    :aria-label="label ?? 'Плотность'"
    size="sm"
    @update:model-value="set"
  />
</template>
