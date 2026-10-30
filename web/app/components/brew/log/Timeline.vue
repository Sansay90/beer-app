<script setup lang="ts">
// Лента варки по дням, новые сверху: записи пивовара (замеры, вехи, заметки — правятся и удаляются) и события
// пивоварни (шаги, подсказки, закладки — как записала пивоварня, мельче и бледнее). Сначала — последние RECENT,
// остальное — по кнопке «Все записи».
import type { BrewEntry, BrewEvent } from '~/types'

const props = defineProps<{ brewId: string; entries: BrewEntry[]; events: BrewEvent[] }>()
const RECENT = 12
const expanded = ref(false)
const emit = defineEmits<{ changed: [] }>()
const { $api } = useNuxtApp()
const prefs = usePreferencesStore()
const confirm = useConfirm()
const { exec } = useCommand()

type Row = { at: number; key: string } & ({ entry: BrewEntry } | { event: BrewEvent })
const days = computed(() => {
  const rows: Row[] = [
    ...props.entries.map(e => ({ at: e.at, key: e.id, entry: e })),
    ...props.events.map((e, i) => ({ at: e.at, key: `ev-${i}`, event: e })),
  ].sort((a, b) => b.at - a.at)
  const groups = new Map<string, Row[]>()
  for (const r of expanded.value ? rows : rows.slice(0, RECENT)) {
    const day = new Date(r.at * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', weekday: 'short' })
    groups.set(day, [...groups.get(day) ?? [], r])
  }
  return [...groups]
})
const total = computed(() => props.entries.length + props.events.length)

const editing = ref<string | null>(null)

async function remove(e: BrewEntry) {
  if (!await confirm({ title: 'Удалить запись?', description: ENTRY_KINDS[e.kind].label, confirmLabel: 'Удалить', confirmIcon: 'i-lucide-trash-2', color: 'error' })) return
  if (await exec(() => $api('/api/brews/{bid}/entries/{eid}', { method: 'DELETE', path: { bid: props.brewId, eid: e.id } }))) emit('changed')
}

function saved() {
  editing.value = null
  emit('changed')
}
</script>

<template>
  <div v-if="days.length" class="space-y-4">
    <section v-for="[day, rows] in days" :key="day">
      <h3 class="mb-1 text-sm font-medium tracking-wide text-dimmed uppercase">{{ day }}</h3>
      <ul class="space-y-0.5">
        <li v-for="r in rows" :key="r.key">
          <BrewLogEntryForm
            v-if="'entry' in r && editing === r.entry.id"
            :brew-id="brewId"
            :entry="r.entry"
            class="rounded-lg bg-elevated/50 p-3"
            @saved="saved"
            @cancel="editing = null"
          />
          <!-- заголовок строкой: значок, время, что и сколько, кнопки; заметка — под ним на всю ширину -->
          <div v-else-if="'entry' in r" class="group rounded-lg px-2 py-1 hover:bg-elevated/50">
            <div class="flex items-center gap-2">
              <UIcon :name="ENTRY_KINDS[r.entry.kind].icon" class="size-5 shrink-0 text-primary" />
              <span class="num w-12 shrink-0 text-base leading-none text-muted">{{ fmtTime(r.at) }}</span>
              <div class="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-2 leading-tight">
                <span class="text-base text-toned">{{ ENTRY_KINDS[r.entry.kind].short ?? ENTRY_KINDS[r.entry.kind].label }}</span>
                <span v-if="r.entry.value != null" class="num text-lg font-semibold text-highlighted">
                  {{ entryValue(r.entry.kind, r.entry.value, prefs.gravityUnit) }}
                </span>
              </div>
              <div class="flex shrink-0 gap-0.5 opacity-0 transition group-hover:opacity-100 focus-within:opacity-100">
                <!-- переход к этапу или шагу — только удалить: какой, решают кнопки таймлайна и «Сейчас» -->
                <UButton v-if="!ENTRY_KINDS[r.entry.kind].transition" icon="i-lucide-pencil" color="neutral" variant="ghost" size="sm" aria-label="Изменить" @click="editing = r.entry.id" />
                <UButton icon="i-lucide-trash-2" color="neutral" variant="ghost" size="sm" aria-label="Удалить" @click="remove(r.entry)" />
              </div>
            </div>
            <p v-if="r.entry.text" class="mt-0.5 ps-6 text-sm break-words whitespace-pre-line text-muted">{{ r.entry.text }}</p>
          </div>
          <div v-else class="flex items-center gap-2 px-2 py-0.5 text-sm text-muted">
            <UIcon :name="EVENT_LOOK[r.event.kind].icon" class="size-4 shrink-0" :class="EVENT_LOOK[r.event.kind].tone" />
            <span class="num w-12 shrink-0">{{ fmtTime(r.at) }}</span>
            <span class="min-w-0 flex-1">{{ r.event.text }}</span>
          </div>
        </li>
      </ul>
    </section>
    <UButton
      v-if="total > RECENT"
      :label="expanded ? 'Свернуть' : `Все записи (${total})`"
      :icon="expanded ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
      color="neutral"
      variant="ghost"
      size="sm"
      @click="expanded = !expanded"
    />
  </div>
  <p v-else class="text-base text-muted">Записей пока нет: добавьте первый замер или заметку.</p>
</template>
