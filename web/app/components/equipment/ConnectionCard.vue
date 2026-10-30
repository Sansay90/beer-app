<script setup lang="ts">
const brewery = useBreweryStore()

const device = computed(() => brewery.snapshot?.settings)
const connection = computed(() => [
  {
    label: 'Сервис',
    badge: brewery.connected
      ? { color: 'success' as const, icon: 'i-lucide-server', label: 'на связи' }
      : { color: 'error' as const, icon: 'i-lucide-circle-x', label: 'нет связи' },
  },
  {
    label: 'Пивоварня',
    badge: brewery.online
      ? { color: 'success' as const, icon: 'i-lucide-wifi', label: 'в сети' }
      : { color: 'warning' as const, icon: 'i-lucide-wifi-off', label: 'не в сети' },
  },
])
</script>

<template>
  <UCard>
    <template #header>
      <div class="font-semibold text-highlighted">Подключение</div>
    </template>
    <dl class="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-[12rem_1fr]">
      <template v-for="c in connection" :key="c.label">
        <dt class="text-sm text-muted">{{ c.label }}</dt>
        <dd><UBadge variant="subtle" v-bind="c.badge" /></dd>
      </template>
      <dt class="text-sm text-muted">Модель</dt>
      <dd class="text-sm">
        <span class="font-medium text-highlighted">{{ device?.model ? `B${device.model}` : '—' }}</span>
        <span class="text-muted"> · заводская настройка, только просмотр</span>
      </dd>
      <dt class="text-sm text-muted">Потолок мощности</dt>
      <dd class="num text-sm font-medium text-highlighted">{{ fmtWatts(device?.maxWatts) }}</dd>
    </dl>
  </UCard>
</template>
