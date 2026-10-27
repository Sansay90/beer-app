<script setup lang="ts">
const push = usePush()
const { exec, pending } = useCommand()

function toggle(on: boolean) {
  exec(() => (on ? push.enable() : push.disable()))
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="font-semibold text-highlighted">Уведомления</div>
      <div class="text-sm text-muted">Подсказки, закладки и конец программы — даже когда приложение закрыто. Настраивается для каждого устройства отдельно.</div>
    </template>
    <div class="flex flex-wrap items-center justify-between gap-4">
      <USwitch
        :model-value="push.state.value === 'on'"
        :disabled="push.state.value === 'unsupported' || push.state.value === 'denied'"
        :loading="pending"
        label="Системные уведомления"
        @update:model-value="toggle"
      />
      <UButton
        color="neutral"
        variant="outline"
        icon="i-lucide-send"
        label="Проверить"
        :disabled="push.state.value !== 'on'"
        @click="exec(push.test, 'Уведомление отправлено')"
      />
    </div>
    <p v-if="push.state.value === 'denied'" class="mt-3 text-sm text-warning">
      Уведомления для этого сайта запрещены — разрешите их в настройках браузера.
    </p>
    <p v-else-if="push.state.value === 'unsupported'" class="mt-3 text-sm text-muted">
      Этот браузер не поддерживает уведомления.
    </p>
  </UCard>
</template>
