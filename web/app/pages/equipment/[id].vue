<script setup lang="ts">
// Единица оборудования: что это, параметры вида и заметки — правятся здесь же; у варочной системы — основная она
// или нет (основная — в новые рецепты и расчёт воды); у Easy Brew — подключение и калибровка датчика, если сайт
// управляет именно этой пивоварней. Удалить — из меню (подключённую пивоварню — нельзя). Вида уже нет в каталоге —
// видно как «Другое», правка недоступна; список или каталог не загрузились — так и сказано, с «Повторить».
import type { EquipmentValues } from '~/utils/equipment'

definePageMeta({ auth: 'user', title: 'Оборудование' })

const route = useRoute()
const { $api } = useNuxtApp()
const confirm = useConfirm()
const { exec, pending } = useCommand()
const { list, status, error, refresh } = useEquipment()
const { kinds, kindOf, categoryLabel, status: kindsStatus, error: kindsError, refresh: refreshKinds } = useEquipmentKinds()
const item = computed(() => list.value.find(e => e.id === route.params.id) ?? null)
const kind = computed(() => (item.value ? kindOf(item.value.kind) : undefined))
const editable = computed(() => !!item.value && kinds.value.has(item.value.kind))
const loading = computed(() => (status.value === 'pending' && !list.value.length) || (kindsStatus.value === 'pending' && !kinds.value.size))
const failed = computed(() => !loading.value && (!!error.value || !!kindsError.value) && !(item.value && kind.value))
function retry() {
  refresh()
  refreshKinds()
}

// форма — копия того, с чего начали править (base). Список обновился (сделали основной, сохранили) — форма
// подтягивает новое, только если в ней ничего не меняли: несохранённые правки не теряются
type Form = { name: string; notes: string; values: EquipmentValues }
const form = ref<Form>({ name: '', notes: '', values: {} })
const base = ref<Form & { id: string } | null>(null)
const snapshot = (): Form & { id: string } => ({ id: item.value!.id, name: item.value!.name, notes: item.value!.notes ?? '',
  values: equipmentValues(item.value!, kind.value) })
const same = (a: Form, b: Form) => a.name.trim() === b.name.trim() && a.notes.trim() === b.notes.trim()
  && JSON.stringify(a.values) === JSON.stringify(b.values)
const dirty = computed(() => !!base.value && !same(form.value, base.value))
function reset() {
  if (!item.value || !kind.value) return
  base.value = snapshot()
  form.value = { name: base.value.name, notes: base.value.notes, values: { ...base.value.values } }
}
watch([item, kind], () => { if (!dirty.value || base.value?.id !== item.value?.id) reset() }, { immediate: true })

async function save() {
  const f = form.value
  const body = { name: f.name.trim(), notes: f.notes.trim() || null, ...equipmentBody(kind.value!, f.values) }
  if (!await exec(() => $api('/api/equipment/{eid}', { method: 'PUT', path: { eid: item.value!.id }, body }), 'Сохранено')) return
  await refresh()
  reset()
}
async function makeMain() {
  if (await exec(() => $api('/api/equipment/{eid}/main', { method: 'PUT', path: { eid: item.value!.id } }), `«${item.value!.name}» — основная`)) await refresh()
}
async function remove() {
  const e = item.value!
  if (!await confirm({ title: `Удалить «${e.name}»?`, description: 'Варки на нём останутся в журнале.', confirmLabel: 'Удалить', confirmIcon: 'i-lucide-trash-2', color: 'error' })) return
  if (await exec(() => $api('/api/equipment/{eid}', { method: 'DELETE', path: { eid: e.id } }), `«${e.name}» удалено`)) {
    await refresh()
    await navigateTo('/equipment')
  }
}
// подключена к сайту, но сайт управляет другой пивоварней — какой
const controlledName = computed(() => list.value.find(e => e.controlled)?.name ?? null)

const menu = computed(() => [[
  ...(item.value?.system && !item.value.main ? [{ label: 'Сделать основной', icon: 'i-lucide-star', onSelect: makeMain }] : []),
  { label: 'Удалить', icon: 'i-lucide-trash-2', color: 'error' as const, disabled: !!item.value?.connected, onSelect: remove },
]])
</script>

<template>
  <UDashboardPanel id="equipment-item">
    <template #header>
      <UDashboardNavbar :title="item?.name ?? 'Оборудование'">
        <template #leading>
          <UButton icon="i-lucide-arrow-left" color="neutral" variant="ghost" to="/equipment" aria-label="Всё оборудование" />
        </template>
        <template #right>
          <UDropdownMenu v-if="item" :items="menu">
            <UButton icon="i-lucide-ellipsis-vertical" color="neutral" variant="ghost" aria-label="Ещё" />
          </UDropdownMenu>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="item && kind" class="mx-auto w-full max-w-3xl space-y-6">
        <UCard :ui="{ body: 'p-5 sm:p-6' }">
          <div class="flex items-start gap-4">
            <span class="grid size-14 shrink-0 place-items-center rounded-xl" :class="item.main ? 'bg-primary/15 text-primary' : 'bg-elevated text-muted'">
              <UIcon :name="equipmentIcon(item.kind)" class="size-8" />
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <h1 class="text-2xl font-semibold text-highlighted">{{ item.name }}</h1>
                <UBadge v-if="item.main" label="основная" color="primary" variant="subtle" />
                <UBadge v-if="item.kind === 'easybrew'" :label="item.connected ? 'подключена' : 'не подключена'" :color="item.connected ? 'success' : 'neutral'" variant="subtle" />
              </div>
              <div class="mt-1 text-base text-muted">{{ kind.label }} · {{ categoryLabel.get(item.category) }}</div>
              <div class="mt-0.5 text-sm text-dimmed">{{ kind.hint }}</div>
            </div>
          </div>
          <div v-if="item.system" class="mt-5 flex flex-wrap items-center gap-3 rounded-lg bg-elevated/60 px-4 py-3">
            <UIcon :name="item.main ? 'i-lucide-star' : 'i-lucide-star-off'" class="size-5" :class="item.main ? 'text-primary' : 'text-dimmed'" />
            <span class="min-w-0 flex-1 text-base text-toned">
              {{ item.main ? 'Основная: её цифры — в новых рецептах и расчёте воды' : 'Варить на ней можно, в новые рецепты идут цифры основной' }}
            </span>
            <UButton v-if="!item.main" label="Сделать основной" icon="i-lucide-star" color="neutral" variant="outline" :loading="pending" @click="makeMain" />
          </div>
        </UCard>

        <UCard :ui="{ body: 'p-5 sm:p-6' }">
          <template #header>
            <h2 class="text-xl font-semibold text-highlighted">Параметры</h2>
          </template>
          <form id="equipment-item-form" class="space-y-4" @submit.prevent="save">
            <UFormField label="Название">
              <UInput v-model="form.name" size="lg" maxlength="60" class="w-full" :disabled="!editable" />
            </UFormField>
            <EquipmentFields v-model="form.values" :kind="kind" />
            <UFormField label="Заметки" help="Модель, где куплено, особенности">
              <UTextarea v-model="form.notes" :rows="2" autoresize maxlength="2000" size="lg" class="w-full" :disabled="!editable" />
            </UFormField>
          </form>
          <UAlert v-if="!editable" icon="i-lucide-info" color="neutral" variant="subtle" class="mt-4" title="Этого вида больше нет в каталоге — править пока нельзя" />
          <template v-if="dirty && editable" #footer>
            <div class="flex justify-end gap-2">
              <UButton label="Отменить" color="neutral" variant="ghost" size="lg" @click="reset" />
              <UButton type="submit" form="equipment-item-form" label="Сохранить" icon="i-lucide-check" size="lg" :loading="pending" :disabled="!form.name.trim()" />
            </div>
          </template>
        </UCard>

        <template v-if="item.kind === 'easybrew'">
          <template v-if="item.controlled">
            <EquipmentConnectionCard />
            <EquipmentCalibrationCard />
          </template>
          <UCard v-else-if="item.connected" :ui="{ body: 'p-5 sm:p-6' }">
            <div class="flex items-start gap-3">
              <UIcon name="i-lucide-plug" class="mt-0.5 size-5 shrink-0 text-muted" />
              <p class="text-base text-toned">
                Подключена к сайту, но управление с сайта сейчас у {{ controlledName ? `«${controlledName}»` : 'другой пивоварни' }}:
                подключение и калибровка — на её странице.
              </p>
            </div>
          </UCard>
          <UCard v-else :ui="{ body: 'p-5 sm:p-6' }">
            <div class="flex items-start gap-3">
              <UIcon name="i-lucide-plug" class="mt-0.5 size-5 shrink-0 text-muted" />
              <p class="text-base text-toned">
                Чтобы управлять пивоварней с сайта, рядом с ней должна работать программа-агент. Подключение в пару
                шагов прямо отсюда скоро появится — пока его настраивает администратор сервиса.
              </p>
            </div>
          </UCard>
        </template>
      </div>
      <UEmpty
        v-else-if="failed"
        icon="i-lucide-cloud-off"
        title="Не удалось загрузить оборудование"
        :actions="[{ label: 'Повторить', icon: 'i-lucide-rotate-cw', onClick: retry }]"
        variant="naked"
      />
      <UEmpty
        v-else-if="!loading && !item"
        icon="i-lucide-search-x"
        title="Оборудование не найдено"
        description="Его удалили или это чужое оборудование."
        :actions="[{ label: 'Всё оборудование', to: '/equipment', icon: 'i-lucide-arrow-left' }]"
        variant="naked"
      />
      <div v-else class="mx-auto w-full max-w-3xl space-y-6">
        <USkeleton class="h-36 w-full" />
        <USkeleton class="h-64 w-full" />
      </div>
    </template>
  </UDashboardPanel>
</template>
