<script setup lang="ts">
const { enabled, toggle, play } = useSound()
</script>

<template>
  <UCard>
    <template #header>
      <div class="font-semibold text-highlighted">Звук</div>
      <div class="text-sm text-muted">Подсказки, закладки и конец программы. Настраивается для каждого устройства отдельно.</div>
    </template>
    <div class="flex flex-wrap items-center justify-between gap-4">
      <USwitch :model-value="enabled" label="Звуковые оповещения" @update:model-value="toggle" />
      <div class="flex flex-wrap gap-2">
        <UButton color="neutral" variant="outline" icon="i-lucide-bell-ring" label="Подсказка" :disabled="!enabled" @click="play('alert')" />
        <UButton color="neutral" variant="outline" icon="i-lucide-bell-ring" label="Закладка" :disabled="!enabled" @click="play('addition')" />
        <UButton color="neutral" variant="outline" icon="i-lucide-flag" label="Конец" :disabled="!enabled" @click="play('end')" />
      </div>
    </div>
  </UCard>
</template>
