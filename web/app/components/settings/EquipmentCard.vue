<script setup lang="ts">
import type { Equipment } from '~/types'

const { $api } = useNuxtApp()
const { data: equipment, error } = useEquipment()
const { exec, pending } = useCommand()
useErrorToast(error)

const FIELDS: { key: keyof Equipment; label: string; unit: string; step: number; description: string }[] = [
  { key: 'efficiency', label: 'Эффективность', unit: '%', step: 1, description: 'Для новых рецептов.' },
  { key: 'evaporation', label: 'Испарение', unit: 'л/ч', step: 0.1, description: 'За час кипячения без крышки.' },
]

// форма — копия сохранённого профиля, пока человек её не трогал
const form = ref<Equipment | null>(null)
const changed = computed(() => !!form.value && JSON.stringify(form.value) !== JSON.stringify(equipment.value))

function reset() {
  form.value = equipment.value ? { ...equipment.value } : null
}
watch(equipment, reset, { immediate: true })

async function save() {
  const saved = form.value && await exec(() => $api('/api/equipment', { method: 'PUT', body: form.value! }), 'Профиль оборудования сохранён')
  if (saved) equipment.value = saved          // общий по ключу: новые цифры видят и рецепты
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="font-semibold text-highlighted">Оборудование</div>
      <div class="text-sm text-muted">Эффективность подставляется в новые рецепты, по испарению считается промывочная вода. Не знаете своих цифр — оставьте средние и поправьте после пары варок.</div>
    </template>
    <div v-if="form" class="grid gap-x-6 gap-y-5 sm:grid-cols-2">
      <UFormField v-for="f in FIELDS" :key="f.key" :label="f.label" :hint="f.unit" :description="f.description">
        <UInputNumber
          v-model="form[f.key]"
          :min="0"
          :step="f.step"
          :step-snapping="false"
          :format-options="{ maximumFractionDigits: 2 }"
          placeholder="—"
          class="w-full"
        />
      </UFormField>
    </div>
    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton color="neutral" variant="ghost" label="Сбросить" :disabled="!changed" @click="reset" />
        <UButton icon="i-lucide-save" label="Сохранить" :loading="pending" :disabled="!changed" @click="save" />
      </div>
    </template>
  </UCard>
</template>
