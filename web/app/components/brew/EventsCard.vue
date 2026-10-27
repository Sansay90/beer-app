<script setup lang="ts">
import type { BrewEvent } from '~/types'

const brewery = useBreweryStore()

const LOOK: Record<BrewEvent['kind'], { icon: string; tone: string }> = {
  alert: { icon: 'i-lucide-hand', tone: 'text-warning' },
  alertCleared: { icon: 'i-lucide-circle-check', tone: 'text-success' },
  addition: { icon: 'i-lucide-bell-ring', tone: 'text-warning' },
  added: { icon: 'i-lucide-circle-check', tone: 'text-success' },
  step: { icon: 'i-lucide-arrow-right', tone: 'text-info' },
  end: { icon: 'i-lucide-flag', tone: 'text-success' },
  powerOff: { icon: 'i-lucide-power', tone: 'text-muted' },
  error: { icon: 'i-lucide-circle-alert', tone: 'text-error' },
  offline: { icon: 'i-lucide-wifi-off', tone: 'text-error' },
  online: { icon: 'i-lucide-wifi', tone: 'text-success' },
}
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-6' }">
    <div class="text-xs font-medium uppercase tracking-wider text-dimmed">События</div>

    <UEmpty
      v-if="!brewery.events.length"
      icon="i-lucide-history"
      title="Пока тихо"
      description="Здесь появятся шаги программы, подсказки и закладки хмеля."
      variant="naked"
      size="sm"
      class="py-4"
    />

    <ul v-else class="mt-3 max-h-80 space-y-1 overflow-auto pr-1">
      <li
        v-for="(e, i) in brewery.events.slice(0, 50)"
        :key="`${e.at}-${i}`"
        class="flex items-start gap-3 rounded-lg px-2 py-1.5 hover:bg-elevated/60"
      >
        <UIcon :name="LOOK[e.kind].icon" class="mt-0.5 size-4 shrink-0" :class="LOOK[e.kind].tone" />
        <span class="min-w-0 flex-1 text-sm" :class="e.kind === 'alert' || e.kind === 'addition' ? 'font-medium text-highlighted' : 'text-toned'">
          {{ e.text }}
        </span>
        <span class="num shrink-0 text-xs text-dimmed">{{ fmtClock(e.at) }}</span>
      </li>
    </ul>
  </UCard>
</template>
