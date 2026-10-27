<script setup lang="ts" generic="K extends string">
// Тип строки — иконкой; по нажатию — меню с выбором.
import type { DropdownMenuItem } from '@nuxt/ui'
import type { KindOption } from '~/types/recipe'

const props = defineProps<{ options: KindOption<K>[] }>()
const model = defineModel<K>({ required: true })

const current = computed(() => props.options.find(o => o.value === model.value) ?? props.options[0]!)
const items = computed<DropdownMenuItem[]>(() => props.options.map(o => ({
  label: o.label,
  icon: o.icon,
  type: 'checkbox' as const,
  checked: o.value === model.value,
  ui: { itemLeadingIcon: o.tint },
  onUpdateChecked: () => { model.value = o.value },
})))
</script>

<template>
  <UDropdownMenu :items="items">
    <UButton
      :icon="current.icon"
      color="neutral"
      variant="ghost"
      size="sm"
      :ui="{ leadingIcon: current.tint }"
      :aria-label="`Тип: ${current.label}`"
    />
  </UDropdownMenu>
</template>
