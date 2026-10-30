<script setup lang="ts">
// Добавить оборудование: сначала вид — из каталога по группам (в окне «Сварить» — только варочные системы), затем
// название и параметры вида. Править добавленное — на его странице (pages/equipment/[id].vue).
import type { Equipment, EquipmentKindInfo } from '~/types'
import type { EquipmentValues } from '~/utils/equipment'

const props = defineProps<{ systemsOnly?: boolean }>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ saved: [item: Equipment] }>()
const { $api } = useNuxtApp()
const { exec, pending } = useCommand()
const { categories } = useEquipmentKinds()

const groups = computed(() => categories.value
  .map(c => ({ ...c, kinds: c.kinds.filter(k => !props.systemsOnly || k.system) }))
  .filter(c => c.kinds.length))
const kind = ref<EquipmentKindInfo | null>(null)
const name = ref('')
const values = ref<EquipmentValues>({})

watch(open, (on) => {
  if (!on) return
  kind.value = null
  name.value = ''
  values.value = {}
})

function choose(k: EquipmentKindInfo) {
  kind.value = k
  name.value = k.label
  values.value = equipmentDefaults(k)
}

async function save() {
  const k = kind.value!
  const body = { kind: k.id, name: name.value.trim(), ...equipmentBody(k, values.value) }
  const saved = await exec(() => $api('/api/equipment', { method: 'POST', body }), 'Оборудование добавлено')
  if (!saved) return
  emit('saved', saved)
  open.value = false
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Добавить оборудование"
    :description="kind ? kind.label : systemsOnly ? 'На чём вы варите?' : 'Что добавить?'"
    :ui="{ content: 'sm:max-w-2xl' }"
  >
    <template #body>
      <div v-if="!kind" class="space-y-6">
        <section v-for="g in groups" :key="g.id">
          <h3 class="mb-2 text-xs font-medium tracking-wider text-dimmed uppercase">{{ g.label }}</h3>
          <div class="grid gap-2 sm:grid-cols-2">
            <button
              v-for="k in g.kinds"
              :key="k.id"
              type="button"
              class="flex items-start gap-3 rounded-xl p-3 text-left ring ring-default transition hover:bg-elevated/60 hover:ring-accented focus-visible:outline-2 focus-visible:outline-primary"
              @click="choose(k)"
            >
              <span class="grid size-10 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary">
                <UIcon :name="equipmentIcon(k.id)" class="size-5" />
              </span>
              <span class="min-w-0">
                <span class="block text-base font-semibold text-highlighted">{{ k.label }}</span>
                <span class="mt-0.5 block text-sm text-muted">{{ k.hint }}</span>
              </span>
            </button>
          </div>
        </section>
      </div>
      <form v-else id="equipment-form" class="space-y-4" @submit.prevent="save">
        <UFormField label="Название">
          <UInput v-model="name" size="lg" maxlength="60" class="w-full" />
        </UFormField>
        <EquipmentFields v-model="values" :kind="kind" />
        <p v-if="kind.system" class="text-sm text-muted">Не знаете своих цифр — оставьте средние и поправьте после пары варок.</p>
      </form>
    </template>
    <template #footer>
      <div class="flex w-full justify-between gap-2">
        <UButton v-if="kind" label="Назад" icon="i-lucide-arrow-left" color="neutral" variant="ghost" size="lg" @click="kind = null" />
        <span v-else />
        <div class="flex gap-2">
          <UButton label="Отмена" color="neutral" variant="ghost" size="lg" @click="open = false" />
          <UButton v-if="kind" type="submit" form="equipment-form" label="Добавить" icon="i-lucide-check" size="lg" :loading="pending" :disabled="!name.trim()" />
        </div>
      </div>
    </template>
  </UModal>
</template>
