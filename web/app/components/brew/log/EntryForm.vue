<script setup lang="ts">
// Запись в журнал варки: что (по группам, в порядке варки), значение замера — в единицах пивовара, когда было,
// комментарий (у заметки — сам текст). entry — правка: вид записи не меняется. preset — вид, выбранный со шага
// варочного дня (каждый выбор — новый объект, даже того же вида).
import type { BrewEntry } from '~/types'
import type { EntryKind } from '~/utils/brewlog'

const props = defineProps<{ brewId: string; entry?: BrewEntry; preset?: { kind: EntryKind } | null }>()
const emit = defineEmits<{ saved: [entry: BrewEntry]; cancel: [] }>()
const { $api } = useNuxtApp()
const prefs = usePreferencesStore()
const { exec, pending } = useCommand()

const kind = ref<EntryKind>(props.entry?.kind ?? 'og')
const value = ref<number | null>(props.entry?.value != null ? fromStored(props.entry.kind, props.entry.value, prefs.gravityUnit) : null)
const when = ref(localInput(props.entry?.at ?? Date.now() / 1000, true))
const text = ref(props.entry?.text ?? '')

const items = entryKindItems()
const input = computed(() => entryInput(kind.value, prefs.gravityUnit))
const ready = computed(() => (input.value ? value.value != null : kind.value !== 'note' || !!text.value.trim()))
watch(kind, () => { value.value = null })
watch(() => props.preset, (p) => { if (p && !props.entry) kind.value = p.kind })

async function save() {
  const body = {
    value: input.value && value.value != null ? toStored(kind.value, value.value, prefs.gravityUnit) : null,
    text: text.value.trim() || null,
    at: new Date(when.value).getTime() / 1000,
  }
  const saved = await exec(() => (props.entry
    ? $api('/api/brews/{bid}/entries/{eid}', { method: 'PATCH', path: { bid: props.brewId, eid: props.entry.id }, body })
    : $api('/api/brews/{bid}/entries', { method: 'POST', path: { bid: props.brewId }, body: { kind: kind.value, ...body } })))
  if (!saved) return
  emit('saved', saved)
  if (!props.entry) {                                     // новая запись — поля готовы к следующей
    value.value = null
    text.value = ''
    when.value = localInput(Date.now() / 1000, true)
  }
}
</script>

<template>
  <form class="space-y-3" @submit.prevent="save">
    <div class="flex flex-wrap items-end gap-3">
      <UFormField label="Что записать" class="min-w-56 flex-1">
        <USelect v-model="kind" :items="items" :disabled="!!entry" size="lg" class="w-full" />
      </UFormField>
      <UFormField v-if="input" :label="input.suffix === 'л' ? 'Литров' : 'Значение'">
        <div class="flex items-center gap-2">
          <UInputNumber
            v-model="value"
            :min="input.min"
            :max="input.max"
            :step="input.step"
            :step-snapping="false"
            :format-options="{ maximumFractionDigits: input.digits }"
            :increment="false"
            :decrement="false"
            placeholder="—"
            size="lg"
            class="w-28"
          />
          <span class="text-base text-muted">{{ input.suffix }}</span>
        </div>
      </UFormField>
      <UFormField label="Когда">
        <UInput v-model="when" type="datetime-local" size="lg" />
      </UFormField>
    </div>
    <UTextarea
      v-model="text"
      autoresize
      :rows="1"
      :maxrows="8"
      size="lg"
      :placeholder="kind === 'note' ? 'Что заметили' : 'Комментарий — необязательно'"
      class="w-full"
    />
    <div class="flex gap-2">
      <UButton type="submit" :label="entry ? 'Сохранить' : 'Записать'" :icon="entry ? 'i-lucide-check' : 'i-lucide-plus'" size="lg" :loading="pending" :disabled="!ready" />
      <UButton v-if="entry" label="Отмена" color="neutral" variant="ghost" size="lg" @click="emit('cancel')" />
    </div>
  </form>
</template>
