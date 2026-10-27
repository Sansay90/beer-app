<script setup lang="ts">
// Варки по рецепту, новые первыми — только свои: показывается автору рецепта.
const props = defineProps<{ recipeId: string }>()

const rid = toRef(() => props.recipeId)
const { data: brews, error } = useApi('/api/brews', { query: { recipe: rid }, key: () => `brews:${rid.value}`, default: () => [] })
useErrorToast(error)

const STATUS = {
  finished: { label: 'завершена', color: 'success' as const },
  stopped: { label: 'прервана', color: 'warning' as const },
  running: { label: 'идёт', color: 'info' as const },
}
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-5' }">
    <div class="mb-3 text-xs font-medium uppercase tracking-wider text-dimmed">Варки</div>
    <ul v-if="brews.length" class="space-y-2">
      <li v-for="b in brews" :key="b.id" class="flex items-center gap-3 text-sm">
        <!-- дата — в часовом поясе посетителя: NuxtTime поправляет её до оживления страницы, без расхождения с сервером -->
        <NuxtTime :datetime="b.startedAt * 1000" locale="ru-RU" day="numeric" month="long" year="numeric" class="num min-w-0 flex-1 text-highlighted" />
        <span v-if="b.energyWh" class="num text-muted">{{ fmtEnergy(b.energyWh) }}</span>
        <UBadge :color="STATUS[b.status].color" variant="subtle" size="sm" :label="STATUS[b.status].label" />
      </li>
    </ul>
    <p v-else class="text-sm text-muted">Ещё не варили.</p>
  </UCard>
</template>
