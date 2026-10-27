<script setup lang="ts">
const brewery = useBreweryStore()
const { exec } = useCommand()
const manualOpen = ref(false)

// ползунок двигается локально, команда уходит, когда его отпустили
const flow = ref(5)
watch(() => brewery.snapshot?.flow, (f) => { if (f != null) flow.value = f }, { immediate: true })

const rows = computed(() => [
  {
    key: 'power', icon: 'i-lucide-power', title: 'Питание', hint: 'Ожидание ↔ включена',
    value: !!brewery.snapshot?.power,
    set: (on: boolean) => exec(() => brewery.setPower(on), on ? 'Пивоварня включена' : 'Пивоварня выключена'),
  },
  {
    key: 'pump', icon: 'i-lucide-waves', title: 'Насос', hint: 'Рециркуляция',
    value: !!brewery.snapshot?.pump,
    set: (on: boolean) => exec(() => brewery.setPump(on)),
  },
])
</script>

<template>
  <UCard :ui="{ body: 'p-5 sm:p-6' }">
    <div class="text-xs font-medium uppercase tracking-wider text-dimmed">Управление</div>

    <div class="mt-2 divide-y divide-default">
      <div v-for="r in rows" :key="r.key" class="flex items-center justify-between gap-4 py-4">
        <div class="flex items-center gap-3">
          <UIcon :name="r.icon" class="size-5 text-muted" />
          <div>
            <div class="font-medium text-highlighted">{{ r.title }}</div>
            <div class="text-xs text-muted">{{ r.hint }}</div>
          </div>
        </div>
        <USwitch :model-value="r.value" :disabled="!brewery.online" size="lg" @update:model-value="r.set" />
      </div>

      <div class="flex items-center gap-3 py-4">
        <span class="w-12 text-xs text-muted">Поток</span>
        <USlider
          v-model="flow"
          :min="0"
          :max="10"
          :step="1"
          :disabled="!brewery.online"
          class="flex-1"
          @change="exec(() => brewery.setFlow(flow))"
        />
        <span class="num w-6 text-right font-semibold text-highlighted">{{ flow }}</span>
      </div>

      <div class="pt-4">
        <UButton
          block
          color="neutral"
          variant="soft"
          icon="i-lucide-sliders-horizontal"
          label="Ручной режим"
          :disabled="!brewery.online"
          @click="manualOpen = true"
        />
      </div>
    </div>

    <BrewManualSlideover v-model:open="manualOpen" />
  </UCard>
</template>
