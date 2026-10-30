<script setup lang="ts">
// Оборудование пивовара: основное — первым (его объём и эффективность — в новые рецепты, испарение — в расчёт
// воды), у каждого — вид и цифры; добавить, изменить, сделать основным, удалить. Пивоварню, подключённую к сайту,
// не удалить; Easy Brew, ещё не подключённая, — с объяснением, как подключить.
import type { Equipment } from '~/types'

const { $api } = useNuxtApp()
const { list, error, refresh } = useEquipment()
const confirm = useConfirm()
const { exec } = useCommand()
useErrorToast(error)

const editing = ref<Equipment | null>(null)
const modal = ref(false)
function add() {
  editing.value = null
  modal.value = true
}
function edit(e: Equipment) {
  editing.value = e
  modal.value = true
}

const num = (v: number) => fmtNumber(v, 1)
const facts = (e: Equipment) => [e.volume != null && `${num(e.volume)} л`, `${num(e.efficiency)} %`, `${num(e.evaporation)} л/ч`,
  e.kettle != null && `котёл ${num(e.kettle)} л`].filter(Boolean).join(' · ')
const kindLabel = (e: Equipment) => (e.kind === 'manual' ? 'без подключения' : e.connected ? 'Easy Brew · подключена' : 'Easy Brew · не подключена')

async function makeMain(e: Equipment) {
  if (await exec(() => $api('/api/equipment/{eid}/main', { method: 'PUT', path: { eid: e.id } }), `«${e.name}» — основное`)) await refresh()
}

async function remove(e: Equipment) {
  if (!await confirm({ title: `Удалить «${e.name}»?`, description: 'Варки на нём останутся в журнале.', confirmLabel: 'Удалить', confirmIcon: 'i-lucide-trash-2', color: 'error' })) return
  if (await exec(() => $api('/api/equipment/{eid}', { method: 'DELETE', path: { eid: e.id } }))) await refresh()
}

const menu = (e: Equipment) => [[
  { label: 'Изменить', icon: 'i-lucide-pencil', onSelect: () => edit(e) },
  ...(e.main ? [] : [{ label: 'Сделать основным', icon: 'i-lucide-star', onSelect: () => makeMain(e) }]),
  ...(e.connected ? [] : [{ label: 'Удалить', icon: 'i-lucide-trash-2', color: 'error' as const, onSelect: () => remove(e) }]),
]]
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div class="font-semibold text-highlighted">Оборудование</div>
          <div class="text-sm text-muted">На чём вы варите. Основное подставляется в новые рецепты, по испарению считается промывочная вода.</div>
        </div>
        <UButton label="Добавить" icon="i-lucide-plus" @click="add" />
      </div>
    </template>

    <ul v-if="list.length" class="-my-2 divide-y divide-default">
      <li v-for="e in list" :key="e.id" class="flex items-start gap-4 py-4">
        <span class="grid size-11 shrink-0 place-items-center rounded-lg" :class="e.main ? 'bg-primary/15 text-primary' : 'bg-elevated text-muted'">
          <UIcon :name="e.kind === 'manual' ? 'i-lucide-cooking-pot' : 'i-lucide-plug'" class="size-6" />
        </span>
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-base font-semibold text-highlighted">{{ e.name }}</span>
            <UBadge v-if="e.main" label="основное" color="primary" variant="subtle" size="sm" />
          </div>
          <div class="num mt-0.5 text-sm text-muted">{{ kindLabel(e) }} · {{ facts(e) }}</div>
          <p v-if="e.kind === 'easybrew' && !e.connected" class="mt-1.5 text-sm text-toned">
            Чтобы управлять пивоварней с сайта, рядом с ней должна работать программа-агент. Подключение в пару шагов прямо отсюда скоро появится — пока его настраивает администратор сервиса.
          </p>
        </div>
        <UDropdownMenu :items="menu(e)">
          <UButton icon="i-lucide-ellipsis-vertical" color="neutral" variant="ghost" :aria-label="`Действия: ${e.name}`" />
        </UDropdownMenu>
      </li>
    </ul>
    <div v-else class="flex flex-col items-start gap-3">
      <p class="text-base text-muted">Оборудования пока нет. Добавьте, на чём варите, — кастрюлю, котёл или пивоварню: рецепты возьмут ваш объём и эффективность.</p>
      <UButton label="Добавить оборудование" icon="i-lucide-plus" variant="soft" @click="add" />
    </div>

    <SettingsEquipmentModal v-model:open="modal" :item="editing" @saved="refresh()" />
  </UCard>
</template>
