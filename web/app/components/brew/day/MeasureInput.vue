<script setup lang="ts">
// Замер прямо на месте: подпись, поле в единицах пивовара. Записывается само, когда ввод закончен — через паузу,
// по Enter или когда ушли из поля: кнопок нет. Обычно есть запись этого вида — её значение в поле, новое пишется
// новой записью. fresh — замер по дням (брожение): поле пустое, прошлое значение подсказкой, после записи снова пустое.
import type { BrewEntry } from '~/types'
import type { EntryKind } from '~/utils/brewlog'

const props = defineProps<{ brewId: string; kind: EntryKind; last?: BrewEntry | null; fresh?: boolean }>()
const emit = defineEmits<{ saved: [entry: BrewEntry] }>()
const { $api } = useNuxtApp()
const prefs = usePreferencesStore()
const { exec, pending } = useCommand()

const input = computed(() => entryInput(props.kind, prefs.gravityUnit)!)
// прошлая запись — в единицах пивовара
const lastInput = computed(() => (props.last?.value != null ? fromStored(props.kind, props.last.value, prefs.gravityUnit) : null))
const value = ref<number | null>(props.fresh ? null : lastInput.value)
watch(lastInput, (v) => { value.value = props.fresh ? null : v })
const placeholder = computed(() => (props.fresh && lastInput.value != null ? fmtNumber(lastInput.value, input.value.digits) : '—'))
const saved = ref(false)                                 // записали в этот раз — зелёная галочка

// поле отдаёт значение по мере набора: «5,35» — это 5, 5,3, 5,35. Записываем один раз, когда ввод закончен
const DELAY_MS = 900
let timer: ReturnType<typeof setTimeout> | null = null
let lastSaved: number | null = null
async function save() {
  if (timer) clearTimeout(timer)
  timer = null
  const v = value.value
  if (v == null || v === lastSaved) return
  if (!props.fresh && lastInput.value != null && Math.abs(v - lastInput.value) < 1e-9) return
  const body = { kind: props.kind, value: toStored(props.kind, v, prefs.gravityUnit) }
  const entry = await exec(() => $api('/api/brews/{bid}/entries', { method: 'POST', path: { bid: props.brewId }, body }))
  if (!entry) return
  saved.value = true
  lastSaved = props.fresh ? null : v
  if (props.fresh) value.value = null
  emit('saved', entry)
}
watch(value, (v) => {
  if (timer) clearTimeout(timer)
  timer = v == null ? null : setTimeout(save, DELAY_MS)
})
onBeforeUnmount(() => { if (timer) clearTimeout(timer) })
</script>

<template>
  <label class="flex flex-col gap-1">
    <span class="text-sm text-muted">{{ ENTRY_KINDS[kind].short ?? ENTRY_KINDS[kind].label }}</span>
    <span class="flex items-center gap-1.5">
      <UInputNumber
        v-model="value"
        :min="input.min"
        :max="input.max"
        :step="input.step"
        :step-snapping="false"
        :format-options="{ maximumFractionDigits: input.digits }"
        :increment="false"
        :decrement="false"
        :placeholder="placeholder"
        size="lg"
        class="w-28"
        :ui="{ base: 'num' }"
        @keydown.enter.prevent="save"
        @blur="save"
      />
      <span class="w-6 text-base text-muted">{{ input.suffix }}</span>
      <span v-if="pending" class="flex items-center text-sm text-muted"><UIcon name="i-lucide-loader-circle" class="size-4 animate-spin" /></span>
      <UIcon v-else-if="saved" name="i-lucide-check" class="size-5 text-success" aria-label="Записано" />
      <UIcon v-else-if="lastInput != null && !fresh" name="i-lucide-check" class="size-5 text-muted" aria-label="Записано раньше" />
    </span>
  </label>
</template>
