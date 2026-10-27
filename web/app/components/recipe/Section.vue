<script setup lang="ts">
// Раздел рецепта (просмотр и редактор): заголовок с иконкой, итог справа, кнопки добавления.
defineProps<{ title: string; icon: string; summary?: string }>()
</script>

<template>
  <UCard :ui="{ header: 'px-5 py-3.5 sm:px-5', body: 'p-5 sm:p-5' }">
    <template #header>
      <div class="flex min-h-8 items-center gap-3">
        <UIcon :name="icon" class="size-5 shrink-0 text-muted" />
        <div class="min-w-0 flex-1 font-semibold text-highlighted">{{ title }}</div>
        <span v-if="summary" class="num hidden text-sm text-muted sm:inline">{{ summary }}</span>
        <slot name="actions" />
      </div>
    </template>
    <slot />
  </UCard>
</template>
