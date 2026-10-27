<script setup lang="ts">
import type { ManualMode } from '~/types'

const open = defineModel<boolean>('open', { default: false })

const brewery = useBreweryStore()
const { exec, pending } = useCommand()

const form = reactive<ManualMode>({ setpoint: 65, minutes: 60, watts: 2500 })
const boilTemp = computed(() => brewery.limits?.boilTemp ?? 100.1)
const watts = computed(() => wattOptions(brewery.limits))
const presets = computed(() => [52, 63, 66, 72, 78].map(t => ({ label: `${t}°`, value: t }))
  .concat({ label: 'Кипение', value: boilTemp.value }))

// при открытии — текущие значения пивоварни
watch(open, (isOpen) => {
  const s = brewery.snapshot
  if (!isOpen || !s) return
  if (s.setpoint != null) form.setpoint = s.setpoint
  if (s.manualMinutes) form.minutes = s.manualMinutes
  if (s.manualWatts) form.watts = s.manualWatts
})

async function apply(andStart: boolean) {
  const applied = await exec(async () => {
    await brewery.setManual({ ...form })
    if (andStart) await brewery.start()
    return true
  }, andStart ? 'Нагрев запущен' : 'Ручной режим задан')
  if (applied) open.value = false
}
</script>

<template>
  <USlideover v-model:open="open" title="Ручной режим" description="Нагрев до уставки и выдержка заданное время.">
    <template #body>
      <div class="space-y-6">
        <UFormField label="Температура" hint="°C">
          <UInputNumber
            v-model="form.setpoint"
            :min="brewery.limits?.minTemp ?? 20"
            :max="boilTemp"
            :step="0.5"
            :step-snapping="false"
            :format-options="{ minimumFractionDigits: 1, maximumFractionDigits: 1 }"
            size="xl"
            class="w-full"
          />
          <div class="mt-2 flex flex-wrap gap-1.5">
            <UButton
              v-for="p in presets"
              :key="p.label"
              size="xs"
              :color="form.setpoint === p.value ? 'primary' : 'neutral'"
              :variant="form.setpoint === p.value ? 'soft' : 'outline'"
              :label="p.label"
              @click="form.setpoint = p.value"
            />
          </div>
          <p class="mt-2 text-xs text-muted">{{ boilTemp }} °C — режим кипячения. Таймер пойдёт, когда вода дойдёт до уставки.</p>
        </UFormField>

        <UFormField label="Время выдержки" hint="минут">
          <UInputNumber v-model="form.minutes" :min="1" :step="1" size="xl" class="w-full" />
        </UFormField>

        <UFormField label="Мощность">
          <USelect v-model="form.watts" :items="watts" size="xl" class="w-full" />
        </UFormField>

        <UAlert
          color="warning"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          title="Нагрев только с водой"
          description="Запуск без воды повредит ТЭНы."
        />
      </div>
    </template>

    <template #footer>
      <div class="flex w-full flex-wrap justify-end gap-2">
        <UButton color="neutral" variant="outline" label="Только задать" :loading="pending" @click="apply(false)" />
        <UButton icon="i-lucide-play" label="Задать и запустить" :loading="pending" @click="apply(true)" />
      </div>
    </template>
  </USlideover>
</template>
