<script setup lang="ts">
// Модалка подтверждения для useConfirm(): закрывается с true/false.
withDefaults(defineProps<{
  title: string
  description?: string
  items?: { icon: string; text: string; tone?: string }[]
  confirmLabel?: string
  confirmIcon?: string
  color?: 'primary' | 'warning' | 'error'
}>(), { confirmLabel: 'Подтвердить', color: 'primary', items: () => [] })

const emit = defineEmits<{ close: [boolean] }>()
</script>

<template>
  <UModal :title="title" :description="description" :close="{ onClick: () => emit('close', false) }">
    <template v-if="items.length" #body>
      <ul class="space-y-2 text-sm">
        <li v-for="(it, i) in items" :key="i" class="flex gap-2">
          <UIcon :name="it.icon" class="size-5 shrink-0" :class="it.tone ?? 'text-muted'" />
          <span class="text-toned">{{ it.text }}</span>
        </li>
      </ul>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton color="neutral" variant="outline" label="Отмена" @click="emit('close', false)" />
        <UButton :color="color" :icon="confirmIcon" :label="confirmLabel" @click="emit('close', true)" />
      </div>
    </template>
  </UModal>
</template>
