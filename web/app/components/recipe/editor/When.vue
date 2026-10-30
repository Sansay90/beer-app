<script setup lang="ts" generic="U extends string">
// «Когда» в таблицах ингредиентов: способ закладки и, где нужно, время — в одной ячейке, без пустых колонок.
// Кипячение — за сколько минут до конца, вирпул — сколько стоит, сухое охмеление — при какой плотности брожения
// и примерно в какой день (без плотности — в этот день).
const use = defineModel<U>('use', { required: true })
const minutes = defineModel<number | null>('minutes', { default: null })
const day = defineModel<number | null>('day', { default: null })
const gravity = defineModel<number | null | undefined>('gravity', { default: null })
const props = defineProps<{ items: { label: string; value: U }[] }>()
// USelect не выводит тип значения из обобщённого U — работаем со строками
const options = computed(() => props.items as { label: string; value: string }[])

const MINUTES = { style: 'unit', unit: 'minute', unitDisplay: 'short' } as const
const DAYS = { style: 'unit', unit: 'day', unitDisplay: 'short' } as const

function setUse(v: string) {
  const value = v as U
  use.value = value
  if (value === 'boil' && minutes.value == null) minutes.value = 10
  if (value === 'whirlpool' && minutes.value == null) minutes.value = 20
  if (value === 'dry_hop' && day.value == null) day.value = 3
}
</script>

<template>
  <div class="flex min-w-0 gap-2">
    <USelect :model-value="use as string" :items="options" size="sm" class="min-w-0 flex-1" aria-label="Когда" @update:model-value="setUse" />
    <UInputNumber
      v-if="use === 'boil' || use === 'whirlpool'"
      v-model="minutes"
      :min="0"
      :step="1"
      :format-options="MINUTES"
      size="sm"
      class="w-30 shrink-0"
      :aria-label="use === 'boil' ? 'Минут до конца кипячения' : 'Сколько минут стоит'"
    />
    <template v-else-if="use === 'dry_hop'">
      <RecipeEditorGravityInput v-model="gravity" placeholder="при" label="При какой плотности" class="w-24 shrink-0" />
      <UInputNumber
        v-model="day"
        :min="0"
        :step="1"
        :format-options="DAYS"
        size="sm"
        class="w-24 shrink-0"
        :aria-label="gravity != null ? 'Примерно в какой день' : 'День брожения'"
      />
    </template>
  </div>
</template>
