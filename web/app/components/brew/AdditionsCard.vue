<script setup lang="ts">
const brewery = useBreweryStore()
const { exec, pending } = useCommand()
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-6' }">
    <div class="text-xs font-medium uppercase tracking-wider text-dimmed">Закладки</div>

    <UEmpty
      v-if="!brewery.additions.length"
      icon="i-lucide-list-plus"
      title="Закладок нет"
      description="В рецепте пивоварни нет закладок на кипячении."
      variant="naked"
      size="sm"
      class="py-4"
    />

    <ul v-else class="mt-4 space-y-2">
      <li
        v-for="a in brewery.additions"
        :key="a.minutes"
        class="flex items-center gap-4 rounded-xl px-3 py-2.5 transition"
        :class="{
          'bg-warning/15 ring-2 ring-warning': a.phase === 'due',
          'bg-primary/10 ring-1 ring-primary/40': a.phase === 'next',
          'bg-elevated/60': a.phase === 'later',
          'opacity-50': a.phase === 'done',
        }"
      >
        <div v-if="a.minutes" class="num w-14 shrink-0 text-2xl font-semibold text-highlighted">
          {{ a.minutes }}<span class="ml-0.5 text-xs font-medium text-muted">мин</span>
        </div>
        <div v-else class="w-14 shrink-0 text-sm font-semibold leading-tight text-highlighted">в конце</div>
        <ul v-if="a.items.length" class="min-w-0 flex-1 space-y-0.5">
          <li v-for="(item, k) in a.items" :key="k" class="flex min-w-0 items-center gap-2">
            <UIcon :name="additionKind(item).icon" class="size-4 shrink-0" :class="additionKind(item).tint" />
            <span class="truncate font-medium text-highlighted">{{ additionName(item) }}</span>
            <span v-if="additionAmount(item)" class="num shrink-0 text-sm text-muted">{{ additionAmount(item) }}</span>
            <span v-if="additionNote(item)" class="num shrink-0 text-xs text-muted">· {{ additionNote(item) }}</span>
          </li>
        </ul>
        <div v-else class="min-w-0 flex-1">
          <div class="font-medium text-highlighted">Закладка</div>
          <div class="text-xs text-muted">рецепт не из приложения — что класть, неизвестно</div>
        </div>
        <div class="shrink-0 text-right">
          <UButton v-if="a.phase === 'due'" color="warning" icon="i-lucide-check" label="Заложил" :loading="pending" @click="exec(() => brewery.ackAddition(a.minutes))" />
          <UIcon v-else-if="a.phase === 'done'" name="i-lucide-circle-check" class="size-5 text-success" />
          <span v-else-if="a.until != null" class="num font-semibold" :class="a.phase === 'next' ? 'text-primary' : 'text-muted'">
            {{ fmtDuration(a.until) }}
          </span>
        </div>
      </li>
    </ul>
  </UCard>
</template>
