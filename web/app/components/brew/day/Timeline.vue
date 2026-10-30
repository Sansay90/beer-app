<script setup lang="ts">
// Таймлайн партии одной линией: шаги варочного дня из рецепта партии — сделано, сейчас, дальше; у каждого время
// по факту, что приготовить, закладки на кипячении, замеры шага чипами (есть значение — показываем, нет — записать);
// после задачи дрожжей — брожение по плану: этапы с датами (следующий — «Начать сейчас»), сухое охмеление в свой день
// («Заложил»), розлив («Разлито»); вылитая партия — «Вылито» с причиной (после розлива — и он; вылили в варочный
// день — брожения нет, только «Вылито»). Замеры брожения — в карточке «Брожение» (они по дням, а не по этапам).
// Пока варочный день идёт, у брожения дат нет.
import type { BrewDetail } from '~/types'
import type { BrewDayView, StepState } from '~/utils/brewday'
import type { EntryKind } from '~/utils/brewlog'

const props = defineProps<{ brew: BrewDetail; view: BrewDayView; now: number }>()
const emit = defineEmits<{ measure: [kind: EntryKind]; stage: [index: number]; entry: [kind: 'dry_hop' | 'package', text?: string] }>()
const prefs = usePreferencesStore()

// брожение — от задачи дрожжей (её нет — от дня варки); варочный день ещё идёт — всё впереди, без дат
const brewing = computed(() => props.view.active)
const start = computed(() => props.brew.fermentStart ?? props.brew.startedAt)
const reason = computed(() => props.brew.entries.find(e => e.kind === 'dumped')?.text ?? null)
const ferment = computed(() => fermentPlan(props.brew.plan, start.value, brewing.value ? start.value - 1 : props.now,
  props.brew.packagedAt, props.brew.entries, props.brew.dumpedAt))
// вылили в варочный день, без дрожжей, — брожения не было
const fermented = computed(() => (ferment.value.stages.length > 0 || ferment.value.dryHops.length > 0)
  && !(props.brew.phase === 'dumped' && props.brew.fermentStart == null))
// розлив — «сейчас», когда план пройден (у последнего этапа по плотности — когда его условие наступило и перешли)
const ended = computed(() => !brewing.value && ferment.value.stages.length > 0 && ferment.value.finished)
const dryLabel = (items: string[]) => items.join(', ')
// заложенное: запись «сухое охмеление» несёт состав закладки («Заложил» пишет его); старые записи без состава —
// по порядку оставшимся
const hoppedAt = computed(() => {
  const left = props.brew.entries.filter(e => e.kind === 'dry_hop').sort((a, b) => a.at - b.at)
  const done = ferment.value.dryHops.map((d) => {
    const k = left.findIndex(e => e.text === dryLabel(d.items))
    return k < 0 ? null : left.splice(k, 1)[0]!.at
  })
  return done.map(at => at ?? left.shift()?.at ?? null)
})
// этапы и сухое охмеление — по порядку во времени: охмеление на 3-й день стоит между этапами, а не после всех
const rows = computed(() => [
  ...ferment.value.stages.map((st, i) => ({ kind: 'stage' as const, i, at: st.from, state: st.state, st })),
  ...ferment.value.dryHops.map((d, i) => ({
    kind: 'dry' as const, i, at: d.at ?? ferment.value.end, d,
    state: (hoppedAt.value[i] != null ? 'done' : d.state) as StepState, doneAt: hoppedAt.value[i] ?? null,
  })),
].sort((a, b) => a.at - b.at || (a.kind === 'stage' ? -1 : 1)))
const measures = computed(() => lastMeasures(props.brew.entries))

const ROW = 'relative grid grid-cols-[2.25rem_minmax(0,1fr)] gap-x-3 py-3'
const NOW = '-mx-3 rounded-lg bg-primary/10 px-3'
const NODE: Record<StepState, string> = {
  done: 'bg-success text-inverted ring-success',
  now: 'bg-primary text-inverted ring-primary ring-offset-4 ring-offset-default',
  next: 'bg-elevated text-muted ring-default',
}
const DUMPED = 'bg-error text-inverted ring-error'
const ICONS: Record<string, string> = { prepare: 'i-lucide-list-checks', heat: 'i-lucide-thermometer-sun', mash_in: 'i-lucide-wheat', rest: 'i-lucide-timer', sparge: 'i-lucide-droplets', boil: 'i-lucide-flame', chill: 'i-lucide-snowflake', pitch: 'i-lucide-microscope' }
const measureLabel = (m: EntryKind) => {
  const name = ENTRY_KINDS[m].short ?? ENTRY_KINDS[m].label
  const last = measures.value.get(m)
  return last ? `${name}: ${entryValue(m, last.value, prefs.gravityUnit)}` : name
}
</script>

<template>
  <ol class="relative">
    <li v-for="s in view.steps" :key="s.key" :class="[ROW, s.state === 'now' && NOW]">
      <span class="relative z-10 grid size-9 place-items-center rounded-full ring-2" :class="NODE[s.state]">
        <UIcon :name="s.state === 'done' ? 'i-lucide-check' : ICONS[s.kind] ?? 'i-lucide-circle'" class="size-4" />
      </span>
      <div class="min-w-0">
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <span class="text-lg font-semibold" :class="s.state === 'next' ? 'text-muted' : 'text-highlighted'">{{ s.name }}</span>
          <span v-if="stepLine(s)" class="num text-base text-muted">{{ stepLine(s) }}</span>
          <span v-if="s.at != null" class="num text-sm text-dimmed">{{ fmtTime(s.at) }}</span>
        </div>
        <ul v-if="s.details.length" class="mt-1 space-y-0.5 text-sm text-toned">
          <li v-for="d in s.details" :key="d">{{ d }}</li>
        </ul>
        <ol v-if="s.additions.length" class="mt-2 space-y-1">
          <li v-for="a in s.additions" :key="a.minutes" class="flex items-baseline gap-3 rounded-md bg-elevated/60 px-3 py-1.5 text-sm">
            <span class="num w-16 shrink-0 font-semibold text-highlighted">{{ additionWhen(a.minutes, s.minutes) }}</span>
            <span class="min-w-0 text-toned">{{ a.label }}</span>
          </li>
        </ol>
        <div v-if="s.measures.length" class="mt-2 flex flex-wrap gap-2">
          <UButton
            v-for="m in s.measures"
            :key="m"
            :icon="ENTRY_KINDS[m].icon"
            :label="measureLabel(m)"
            :color="measures.get(m) ? 'primary' : 'neutral'"
            :variant="measures.get(m) ? 'soft' : 'outline'"
            size="sm"
            @click="emit('measure', m)"
          />
        </div>
      </div>
    </li>
  </ol>

  <template v-if="fermented">
    <div class="mt-4 mb-1 flex items-center gap-3 text-xs font-medium tracking-wider text-dimmed uppercase">
      Брожение<template v-if="brewing">{{ SEP }}с задачи дрожжей</template><span class="h-px flex-1 bg-border" />
    </div>
    <ol class="relative">
      <li v-for="r in rows" :key="`${r.kind}${r.i}`" :class="[ROW, r.state === 'now' && NOW]">
        <span class="relative z-10 grid size-9 place-items-center rounded-full ring-2" :class="NODE[r.state]">
          <UIcon
            :name="r.state === 'done' ? 'i-lucide-check' : r.kind === 'dry' ? 'i-lucide-hop' : r.st.temp <= COLD ? 'i-lucide-snowflake' : 'i-lucide-flask-conical'"
            class="size-4"
          />
        </span>
        <div v-if="r.kind === 'stage'" class="min-w-0">
          <div class="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <span class="text-lg font-semibold" :class="r.state === 'next' ? 'text-muted' : 'text-highlighted'">{{ r.st.name }}</span>
            <span class="num text-base text-muted">{{ fmtNumber(r.st.temp, 1) }} °C{{ SEP }}{{ stageCondition({ until: r.st.until, gravity: r.st.target, days: r.st.days }, prefs.gravityUnit) }}</span>
            <span v-if="!brewing" class="num text-sm text-dimmed">{{ fmtDay(r.st.from) }} – {{ r.st.until !== 'days' && r.st.state !== 'done' ? '~' : '' }}{{ fmtDay(r.st.to) }}<template v-if="r.st.manual">{{ SEP }}начат по факту</template></span>
          </div>
          <!-- следующий этап можно начать раньше плана; первый начинается с задачи дрожжей -->
          <UButton
            v-if="r.i >= 1 && r.i === ferment.next && !brewing && !ferment.closed"
            :label="`Начать «${r.st.name}» сейчас`"
            icon="i-lucide-arrow-right"
            color="neutral"
            variant="outline"
            size="sm"
            class="mt-2"
            @click="emit('stage', r.i)"
          />
        </div>
        <div v-else class="min-w-0">
          <div class="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <span class="text-lg font-semibold" :class="r.state === 'next' ? 'text-muted' : 'text-highlighted'">Сухое охмеление</span>
            <span class="text-base text-muted">{{ r.d.items.join(', ') }}</span>
            <span class="num text-sm text-dimmed">
              {{ dryHopWhen(r.d, prefs.gravityUnit) }}<template v-if="r.doneAt != null">{{ SEP }}{{ fmtDay(r.doneAt) }}</template><template v-else-if="r.d.at != null && !r.d.estimated && !brewing">{{ SEP }}{{ fmtDay(r.d.at) }}</template>
            </span>
          </div>
          <UButton
            v-if="r.state !== 'done' && !brewing && !ferment.closed"
            label="Заложил"
            icon="i-lucide-check"
            :color="r.state === 'now' ? 'primary' : 'neutral'"
            :variant="r.state === 'now' ? 'solid' : 'outline'"
            size="sm"
            class="mt-2"
            @click="emit('entry', 'dry_hop', dryLabel(r.d.items))"
          />
        </div>
      </li>
      <li v-if="!brew.dumpedAt || brew.packagedAt" :class="ROW">
        <span class="relative z-10 grid size-9 place-items-center rounded-full ring-2" :class="NODE[brew.packagedAt ? 'done' : ended ? 'now' : 'next']">
          <UIcon :name="brew.packagedAt ? 'i-lucide-check' : 'i-lucide-beer'" class="size-4" />
        </span>
        <div class="flex min-w-0 flex-wrap items-center gap-3">
          <span class="text-lg font-semibold" :class="brew.packagedAt || ended ? 'text-highlighted' : 'text-muted'">Розлив</span>
          <span class="num text-sm text-dimmed">
            <template v-if="brew.packagedAt">{{ fmtDay(brew.packagedAt) }}</template><template v-else-if="!brewing && ferment.stages.length">{{ ferment.estimated ? '~' : '' }}{{ fmtDay(ferment.end) }}</template>
          </span>
          <UButton
            v-if="!brew.packagedAt && !brewing"
            label="Разлито"
            icon="i-lucide-beer"
            :color="ended ? 'primary' : 'neutral'"
            :variant="ended ? 'solid' : 'outline'"
            size="sm"
            @click="emit('entry', 'package')"
          />
        </div>
      </li>
    </ol>
  </template>
  <ol v-if="brew.dumpedAt" class="relative">
    <li :class="ROW">
      <span class="relative z-10 grid size-9 place-items-center rounded-full ring-2" :class="DUMPED">
        <UIcon name="i-lucide-circle-x" class="size-4" />
      </span>
      <div class="min-w-0">
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <span class="text-lg font-semibold text-highlighted">Вылито</span>
          <span class="num text-sm text-dimmed">{{ fmtDay(brew.dumpedAt) }}</span>
        </div>
        <p v-if="reason" class="mt-0.5 text-sm break-words whitespace-pre-line text-toned">{{ reason }}</p>
      </div>
    </li>
  </ol>
</template>
