<script setup lang="ts">
import type { SettingsUpdate } from '~/types'

const brewery = useBreweryStore()
const { exec, pending } = useCommand()

// форма калибровки: заполняется значениями пивоварни, пока человек её не трогал
const form = reactive<Required<SettingsUpdate>>({ calibration: 0, boilCompensation: 0 })
const device = computed(() => brewery.snapshot?.settings)
const changed = computed(() => !!device.value && (form.calibration !== device.value.calibration || form.boilCompensation !== device.value.boilCompensation))

function reset() {
  form.calibration = device.value?.calibration ?? 0
  form.boilCompensation = device.value?.boilCompensation ?? 0
}
watchOnce(() => device.value?.calibration != null, reset, { immediate: true })
</script>

<template>
  <UCard>
    <template #header>
      <div class="font-semibold text-highlighted">Калибровка датчика</div>
    </template>
    <div class="space-y-6">
      <UFormField
        label="Калибровка температуры"
        description="Поправка к показаниям датчика, −10…+10 °C. Подбирается по эталонному термометру."
        hint="°C"
      >
        <UInputNumber
          v-model="form.calibration"
          :min="-10"
          :max="10"
          :step="0.1"
          :step-snapping="false"
          :format-options="{ minimumFractionDigits: 1, maximumFractionDigits: 1 }"
          class="w-48"
        />
      </UFormField>
      <UFormField
        label="Компенсация температуры кипения"
        description="Действует выше 90 °C, 0…10 °C. Нужна, если по датчику вода кипит заметно ниже 100 °C и таймер кипячения не стартует."
        hint="°C"
      >
        <UInputNumber
          v-model="form.boilCompensation"
          :min="0"
          :max="10"
          :step="0.1"
          :step-snapping="false"
          :format-options="{ minimumFractionDigits: 1, maximumFractionDigits: 1 }"
          class="w-48"
        />
      </UFormField>
    </div>
    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton color="neutral" variant="ghost" label="Сбросить" :disabled="!changed" @click="reset" />
        <UButton
          icon="i-lucide-save"
          label="Записать в пивоварню"
          :loading="pending"
          :disabled="!changed || !brewery.online"
          @click="exec(() => brewery.saveSettings({ ...form }), 'Калибровка записана в пивоварню')"
        />
      </div>
    </template>
  </UCard>
</template>
