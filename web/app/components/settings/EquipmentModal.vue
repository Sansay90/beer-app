<script setup lang="ts">
// Добавить или изменить оборудование. Новое — сначала тип: без подключения (кастрюля, котёл, любая система)
// или Easy Brew Connect; затем название, объём партии, эффективность, испарение и объём котла (по нему «Сварить»
// предупреждает, что варка не влезает). Тип у сохранённого не меняется.
import type { Equipment, EquipmentKind } from '~/types'

const props = defineProps<{ item?: Equipment | null }>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ saved: [item: Equipment] }>()
const { $api } = useNuxtApp()
const { exec, pending } = useCommand()

const KINDS: { value: EquipmentKind; icon: string; title: string; text: string; name: string }[] = [
  { value: 'manual', icon: 'i-lucide-cooking-pot', title: 'Без подключения', text: 'Кастрюля на плите, котёл, любая система. Цифры — для расчёта рецептов и журнала варок.', name: 'Кастрюля' },
  { value: 'easybrew', icon: 'i-lucide-plug', title: 'Easy Brew Connect', text: 'Пивоварня, которой можно управлять с сайта: программа, закладки, график варки.', name: 'Easy Brew' },
]

const kind = ref<EquipmentKind | null>(null)
const blank = () => ({ name: '', volume: null as number | null, efficiency: DEFAULT_EFFICIENCY, evaporation: 3, kettle: null as number | null })
const form = reactive(blank())

watch(open, (on) => {
  if (!on) return
  const it = props.item
  kind.value = it?.kind ?? null
  Object.assign(form, it
    ? { name: it.name, volume: it.volume ?? null, efficiency: it.efficiency, evaporation: it.evaporation, kettle: it.kettle ?? null }
    : blank())
})

function choose(k: EquipmentKind) {
  kind.value = k
  form.name ||= KINDS.find(x => x.value === k)!.name
}

async function save() {
  const body = { name: form.name.trim(), volume: form.volume, efficiency: form.efficiency, evaporation: form.evaporation, kettle: form.kettle }
  const saved = await exec(() => (props.item
    ? $api('/api/equipment/{eid}', { method: 'PUT', path: { eid: props.item.id }, body })
    : $api('/api/equipment', { method: 'POST', body: { ...body, kind: kind.value! } })), props.item ? 'Оборудование сохранено' : 'Оборудование добавлено')
  if (!saved) return
  emit('saved', saved)
  open.value = false
}
</script>

<template>
  <UModal v-model:open="open" :title="item ? 'Оборудование' : 'Добавить оборудование'" :description="kind ? KINDS.find(k => k.value === kind)!.title : 'На чём вы варите?'">
    <template #body>
      <div v-if="!kind" class="grid gap-3">
        <button
          v-for="k in KINDS"
          :key="k.value"
          type="button"
          class="flex items-start gap-4 rounded-xl p-4 text-left ring ring-default transition hover:bg-elevated/60 hover:ring-accented focus-visible:outline-2 focus-visible:outline-primary"
          @click="choose(k.value)"
        >
          <span class="grid size-11 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary">
            <UIcon :name="k.icon" class="size-6" />
          </span>
          <span>
            <span class="block text-base font-semibold text-highlighted">{{ k.title }}</span>
            <span class="mt-0.5 block text-sm text-muted">{{ k.text }}</span>
          </span>
        </button>
      </div>
      <form v-else id="equipment-form" class="space-y-4" @submit.prevent="save">
        <UFormField label="Название">
          <UInput v-model="form.name" size="lg" maxlength="60" class="w-full" />
        </UFormField>
        <!-- подсказки — под полями: разной длины, над полями они сдвигали поля по высоте -->
        <div class="grid gap-4 sm:grid-cols-2">
          <UFormField label="Объём партии" hint="л" help="После кипячения">
            <UInputNumber v-model="form.volume" :min="0.5" :max="2000" :step="1" :step-snapping="false" :format-options="{ maximumFractionDigits: 1 }" placeholder="—" size="lg" class="w-full" />
          </UFormField>
          <UFormField label="Эффективность" hint="%" help="Для новых рецептов">
            <UInputNumber v-model="form.efficiency" :min="1" :max="100" :step="1" :step-snapping="false" size="lg" class="w-full" />
          </UFormField>
          <UFormField label="Испарение" hint="л/ч" help="За час, без крышки">
            <UInputNumber v-model="form.evaporation" :min="0" :max="20" :step="0.1" :step-snapping="false" :format-options="{ maximumFractionDigits: 1 }" size="lg" class="w-full" />
          </UFormField>
          <UFormField label="Объём котла" hint="л" help="До краёв — проверить, влезет ли варка">
            <UInputNumber v-model="form.kettle" :min="1" :max="5000" :step="1" :step-snapping="false" :format-options="{ maximumFractionDigits: 1 }" placeholder="—" size="lg" class="w-full" />
          </UFormField>
        </div>
        <p class="text-sm text-muted">Не знаете своих цифр — оставьте средние и поправьте после пары варок.</p>
      </form>
    </template>
    <template #footer>
      <div class="flex w-full justify-between gap-2">
        <UButton v-if="kind && !item" label="Назад" icon="i-lucide-arrow-left" color="neutral" variant="ghost" size="lg" @click="kind = null" />
        <span v-else />
        <div class="flex gap-2">
          <UButton label="Отмена" color="neutral" variant="ghost" size="lg" @click="open = false" />
          <UButton v-if="kind" type="submit" form="equipment-form" :label="item ? 'Сохранить' : 'Добавить'" icon="i-lucide-check" size="lg" :loading="pending" :disabled="!form.name.trim()" />
        </div>
      </div>
    </template>
  </UModal>
</template>
