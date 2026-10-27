<script setup lang="ts">
// Пароль с кнопкой «показать»: на телефоне опечатку иначе не заметить.
defineProps<{ autocomplete: 'current-password' | 'new-password' }>()
const value = defineModel<string>({ required: true })
const shown = ref(false)
</script>

<template>
  <UInput
    v-model="value"
    :type="shown ? 'text' : 'password'"
    :autocomplete="autocomplete"
    size="lg"
    class="w-full"
    :ui="{ trailing: 'pe-1' }"
  >
    <template #trailing>
      <UButton
        color="neutral"
        variant="link"
        size="sm"
        :icon="shown ? 'i-lucide-eye-off' : 'i-lucide-eye'"
        :aria-label="shown ? 'Скрыть пароль' : 'Показать пароль'"
        :aria-pressed="shown"
        @click="shown = !shown"
      />
    </template>
  </UInput>
</template>
