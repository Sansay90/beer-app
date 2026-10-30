<script setup lang="ts">
// Системные уведомления — на этом устройстве (подписка браузера); о комментариях и брожении — на всех устройствах
// пользователя.
const { $api } = useNuxtApp()
const push = usePush()
const { exec, pending } = useCommand()
const saving = useCommand()
const { data: settings } = useApi('/api/notifications/settings', { key: 'notice-settings' })

function toggle(on: boolean) {
  exec(() => (on ? push.enable() : push.disable()))
}

async function save(body: { pushComments?: boolean; pushBrews?: boolean }) {
  const saved = await saving.exec(() => $api('/api/notifications/settings', { method: 'PUT', body }))
  if (saved) settings.value = saved
}
const setComments = (on: boolean) => save({ pushComments: on })
const setBrews = (on: boolean) => save({ pushBrews: on })
</script>

<template>
  <UCard>
    <template #header>
      <div class="font-semibold text-highlighted">Уведомления</div>
      <div class="text-sm text-muted">Подсказки, закладки, конец программы, комментарии, ответы и брожение — даже когда приложение закрыто. Включаются для каждого устройства отдельно.</div>
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
    <USwitch
      class="mt-5"
      :model-value="settings?.pushComments ?? true"
      :disabled="!settings"
      :loading="saving.pending.value"
      label="Комментарии и ответы"
      description="Комментарии к вашим рецептам и ответы вам — на все ваши устройства. На сайте они всегда есть в разделе «Уведомления»."
      @update:model-value="setComments"
    />
    <USwitch
      class="mt-4"
      :model-value="settings?.pushBrews ?? true"
      :disabled="!settings"
      :loading="saving.pending.value"
      label="Напоминания о брожении"
      description="Следующий этап, сухое охмеление и конец брожения по плану рецепта — в нужный день, на все ваши устройства."
      @update:model-value="setBrews"
    />
    <p v-if="push.state.value === 'denied'" class="mt-3 text-sm text-warning">
      Уведомления для этого сайта запрещены — разрешите их в настройках браузера.
    </p>
    <p v-else-if="push.state.value === 'unsupported'" class="mt-3 text-sm text-muted">
      Этот браузер не поддерживает уведомления.
    </p>
  </UCard>
</template>
