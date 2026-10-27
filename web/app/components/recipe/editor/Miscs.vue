<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type { KindOption, MiscRow } from '~/types/recipe'

const rows = defineModel<MiscRow[]>({ required: true })

const KINDS: KindOption<MiscRow['kind']>[] = MISC_KINDS.map(k => ({ value: k, ...ADDITION_KINDS[k] }))
const USES = options(MISC_USES)
const GRID = 'sm:grid sm:grid-cols-[2rem_minmax(0,1fr)_9.5rem_17rem_2rem]'

const addItems: DropdownMenuItem[] = KINDS.map(k => ({
  label: k.label, icon: k.icon, ui: { itemLeadingIcon: k.tint }, onSelect: () => rows.value.push(newMisc(k.value)),
}))
</script>

<template>
  <RecipeSection title="Другое" icon="i-lucide-flask-conical">
    <template #actions>
      <UDropdownMenu :items="addItems" :content="{ align: 'end' }">
        <UButton icon="i-lucide-plus" label="Добавить" trailing-icon="i-lucide-chevron-down" size="xs" color="neutral" variant="outline" />
      </UDropdownMenu>
    </template>

    <RecipeEditorEmpty v-if="!rows.length" text="Специи, осветлители, соли, добавки и оборудование вроде чиллера." />
    <div v-else class="space-y-2">
      <div class="hidden items-center gap-2 px-0.5 text-xs text-dimmed" :class="GRID">
        <span /><span>Название</span><span>Сколько</span><span>Когда</span><span />
      </div>
      <div v-for="(m, i) in rows" :key="i" class="flex flex-wrap items-center gap-2" :class="GRID">
        <RecipeEditorKindButton v-model="m.kind" :options="KINDS" />
        <!-- у оборудования количества нет — название занимает и его колонку -->
        <UInput v-model="m.name" :placeholder="ADDITION_KINDS[m.kind].placeholder" size="sm" class="min-w-40 flex-1" :class="{ 'sm:col-span-2': !ADDITION_KINDS[m.kind].measured }" />
        <UFieldGroup v-if="ADDITION_KINDS[m.kind].measured" size="sm" class="w-38 sm:w-auto">
          <UInputNumber v-model="m.amount" :min="0" :step="1" :step-snapping="false" :format-options="{ maximumFractionDigits: 2 }" :increment="false" :decrement="false" placeholder="—" class="min-w-0 flex-1" aria-label="Количество" />
          <USelect v-model="m.unit" :items="ADDITION_UNITS" class="w-16" aria-label="Единица" />
        </UFieldGroup>
        <RecipeEditorWhen v-model:use="m.use" v-model:minutes="m.minutes" :items="USES" class="w-68 sm:w-auto" />
        <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="sm" aria-label="Убрать" @click="rows.splice(i, 1)" />
      </div>
    </div>
  </RecipeSection>
</template>
