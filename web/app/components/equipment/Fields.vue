<script setup lang="ts">
// Параметры оборудования по каталогу вида: числа — с единицей и пределами, выбор — списком, «да/нет» — переключателем.
// Подсказки — под полями: разной длины, над полями они сдвигали поля по высоте.
import type { EquipmentKindInfo } from '~/types'
import type { EquipmentValue, EquipmentValues } from '~/utils/equipment'

defineProps<{ kind: EquipmentKindInfo }>()
const values = defineModel<EquipmentValues>({ required: true })
const set = (key: string, v: EquipmentValue | undefined) => { values.value = { ...values.value, [key]: v ?? null } }
</script>

<template>
  <div v-if="kind.fields.length" class="grid gap-4 sm:grid-cols-2">
    <template v-for="f in kind.fields" :key="f.key">
      <UFormField v-if="f.type === 'number'" :label="f.label" :hint="f.unit || undefined" :help="f.help ?? undefined">
        <UInputNumber
          :model-value="(values[f.key] as number | null)"
          :min="f.min ?? undefined"
          :max="f.max ?? undefined"
          :step="f.step ?? 1"
          :step-snapping="false"
          :format-options="{ maximumFractionDigits: f.digits ?? 0 }"
          placeholder="—"
          size="lg"
          class="w-full"
          @update:model-value="v => set(f.key, v)"
        />
      </UFormField>
      <UFormField v-else-if="f.type === 'select'" :label="f.label" :help="f.help ?? undefined">
        <USelect
          :model-value="(values[f.key] as string | null) ?? undefined"
          :items="f.options ?? []"
          placeholder="Не указано"
          size="lg"
          class="w-full"
          @update:model-value="v => set(f.key, v as string)"
        />
      </UFormField>
      <UFormField v-else :help="f.help ?? undefined" class="self-end">
        <USwitch :model-value="!!values[f.key]" :label="f.label" size="lg" @update:model-value="v => set(f.key, v)" />
      </UFormField>
    </template>
  </div>
</template>
