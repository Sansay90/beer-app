<script setup lang="ts">
// Стиль рецепта: BJCP 2021 (поиск по коду и названию) или авторский — без рамок стиля, с необязательным названием.
import type { SelectMenuItem } from '@nuxt/ui'
import type { StyleRef } from '~/types'

const model = defineModel<StyleRef | null>({ required: true })

const custom = ref(!!model.value && !model.value.code)
watch(model, (s) => { if (s) custom.value = !s.code })

const groups = computed<SelectMenuItem[][]>(() => {
  const byCategory = new Map<string, SelectMenuItem[]>()
  for (const s of STYLES) {
    const list = byCategory.get(s.category) ?? []
    list.push({ label: `${s.code}${SEP}${s.name}`, value: s.code })
    byCategory.set(s.category, list)
  }
  return [...byCategory].map(([category, items]) => [{ type: 'label' as const, label: category }, ...items])
})

const code = computed({
  get: () => model.value?.code ?? undefined,
  set: (value?: string) => { model.value = value ? { code: value, name: styleByCode(value)!.name } : null },
})

const customName = computed({
  get: () => (model.value && !model.value.code ? model.value.name : ''),
  set: (name: string) => { model.value = { code: null, name } },
})

function setCustom(on: boolean) {
  if (on === custom.value) return
  custom.value = on
  model.value = on ? { code: null, name: '' } : null
}
</script>

<template>
  <div class="flex gap-2">
    <UFieldGroup>
      <UButton label="BJCP" color="neutral" :variant="custom ? 'outline' : 'subtle'" @click="setCustom(false)" />
      <UButton label="Авторский" color="neutral" :variant="custom ? 'subtle' : 'outline'" @click="setCustom(true)" />
    </UFieldGroup>
    <UInput v-if="custom" v-model="customName" placeholder="Название стиля — необязательно" class="min-w-0 flex-1" />
    <USelectMenu
      v-else
      v-model="code"
      :items="groups"
      value-key="value"
      :search-input="{ placeholder: 'Код или название: 5B, Kölsch…' }"
      clear
      placeholder="Выберите стиль"
      icon="i-lucide-tag"
      :ui="{ content: 'min-w-80' }"
      class="min-w-0 flex-1"
    />
  </div>
</template>
