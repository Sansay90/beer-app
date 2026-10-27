<script setup lang="ts">
import type { ButtonProps } from '@nuxt/ui'
import type { NextActionId, Tone } from '~/utils/brew'

const brewery = useBreweryStore()
const { exec, pending } = useCommand()
const confirm = useConfirm()

const a = computed(() => brewery.next)

const toneBox: Record<Tone, string> = {
  primary: 'bg-primary/10 text-primary',
  success: 'bg-success/10 text-success',
  warning: 'bg-warning/15 text-warning',
  error: 'bg-error/10 text-error',
  info: 'bg-info/10 text-info',
  neutral: 'bg-elevated text-muted',
}

async function startRecipe() {
  const ok = await confirm({
    title: 'Запустить рецепт?',
    description: brewery.snapshot?.deviceRecipe?.name ? `«${brewery.snapshot.deviceRecipe.name}» — нагрев начнётся сразу.` : 'Нагрев начнётся сразу.',
    items: [
      { icon: 'i-lucide-droplets', text: 'в баке достаточно воды', tone: 'text-info' },
      { icon: 'i-lucide-waves', text: 'клапаны выставлены для рециркуляции', tone: 'text-info' },
      { icon: 'i-lucide-wheat', text: 'солод под рукой', tone: 'text-warning' },
    ],
    confirmLabel: 'Запустить',
    confirmIcon: 'i-lucide-play',
  })
  if (ok) exec(brewery.startRecipe, 'Рецепт запущен')
}

/** Как выглядит и что делает каждое действие, которое может предложить «Дальше». */
const ACTIONS: Record<NextActionId, ButtonProps & { onClick?: () => void; tooltip?: string }> = {
  startRecipe: { label: 'Запустить рецепт', icon: 'i-lucide-play', size: 'xl', onClick: startRecipe },
  resume: { label: 'Продолжить', icon: 'i-lucide-play', size: 'xl', onClick: () => exec(brewery.start) },
  chooseRecipe: { label: 'Выбрать рецепт', icon: 'i-lucide-book-open', size: 'lg', to: '/recipes' },
  pause: { label: 'Пауза', icon: 'i-lucide-pause', color: 'neutral', variant: 'outline', onClick: () => exec(brewery.pause) },
  ackAddition: {
    label: 'Заложил',
    icon: 'i-lucide-check',
    color: 'warning',
    size: 'xl',
    onClick: () => { if (a.value.addition != null) exec(() => brewery.ackAddition(a.value.addition!)) },
  },
  confirmAlert: {
    label: 'Подтвердить',
    icon: 'i-lucide-check',
    color: 'warning',
    size: 'xl',
    onClick: () => exec(brewery.confirmAlert, 'Подтверждено'),
  },
}

const buttons = computed(() => a.value.actions.map(id => ({ id, ...ACTIONS[id] })))
</script>

<template>
  <UCard
    class="h-full"
    :class="a.attention ? 'ring-2 ring-warning' : ''"
    :ui="{ body: 'p-5 sm:p-6 flex h-full flex-col' }"
  >
    <div class="text-xs font-medium uppercase tracking-wider text-dimmed">Дальше</div>

    <div class="mt-4 flex items-start gap-4">
      <div class="grid size-14 shrink-0 place-items-center rounded-2xl" :class="toneBox[a.tone]">
        <UIcon :name="a.icon" class="size-7" :class="{ 'soft-pulse': a.attention, 'animate-spin': a.kind === 'wait' }" />
      </div>
      <div class="min-w-0">
        <div class="text-xl font-semibold leading-snug text-highlighted">{{ a.title }}</div>
        <div v-if="a.description" class="mt-1 text-sm text-muted">{{ a.description }}</div>
      </div>
    </div>

    <div v-if="a.countdown != null" class="num mt-6 text-5xl font-semibold tracking-tight text-highlighted">
      {{ fmtDuration(a.countdown) }}
    </div>

    <div v-if="buttons.length" class="mt-auto flex flex-wrap items-center gap-2 pt-6">
      <template v-for="{ id, tooltip, ...b } in buttons" :key="id">
        <UTooltip :text="tooltip" :disabled="!tooltip">
          <UButton v-bind="b" :loading="pending && !!b.onClick" :disabled="!brewery.online && id !== 'chooseRecipe'" />
        </UTooltip>
      </template>
    </div>
  </UCard>
</template>
