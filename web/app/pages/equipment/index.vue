<script setup lang="ts">
// Оборудование — всё, на чём и чем варит пивовар, по группам каталога: варка, помол, охлаждение, брожение,
// измерения, дрожжи, розлив. У каждой единицы своя страница: параметры, заметки, у подключённой пивоварни — связь
// и калибровка. В группе основная варочная система — первой. Каталог не загрузился или вида в нём нет — оборудование
// всё равно видно: в группе «Другое» (без каталога — одним списком).
import type { Equipment } from '~/types'

definePageMeta({ auth: 'user', title: 'Оборудование' })

const { list, status, error, refresh } = useEquipment()
const { categories, kindOf, status: kindsStatus, error: kindsError } = useEquipmentKinds()
useErrorToast(error)
useErrorToast(kindsError)
const adding = ref(false)

const groups = computed(() => {
  const known = new Set(categories.value.map(c => c.id))
  const out = categories.value
    .map(c => ({ id: c.id, label: c.label, items: list.value.filter(e => e.category === c.id && c.id !== 'other') }))
  const rest = list.value.filter(e => e.category === 'other' || !known.has(e.category))
  out.push({ id: 'rest', label: categories.value.length ? 'Другое' : 'Оборудование', items: rest })
  return out.filter(g => g.items.length)
})
// пока нет списка или каталога — скелетон: без каталога не по чему группировать
const loading = computed(() => (status.value === 'pending' && !list.value.length)
  || (kindsStatus.value === 'pending' && !categories.value.length))
// вид — если название его не повторяет («pH-метр» — не «pH-метр · pH-метр»), и кратко параметры
const line = (e: Equipment) => {
  const k = kindOf(e.kind)
  return [k?.label !== e.name && k?.label, equipmentFacts(e, k)].filter(Boolean).join(SEP)
}
</script>

<template>
  <UDashboardPanel id="equipment">
    <template #header>
      <UDashboardNavbar title="Оборудование">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton label="Добавить" icon="i-lucide-plus" @click="adding = true" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="mx-auto w-full max-w-3xl space-y-6">
        <USkeleton v-if="loading" class="h-48 w-full" />
        <section v-for="g in loading ? [] : groups" :key="g.id">
          <h2 class="mb-2 px-1 text-xs font-medium tracking-wider text-dimmed uppercase">{{ g.label }}</h2>
          <UCard :ui="{ body: 'p-0 sm:p-0' }">
            <ul class="divide-y divide-default">
              <li v-for="e in g.items" :key="e.id">
                <NuxtLink :to="`/equipment/${e.id}`" class="flex items-center gap-4 px-4 py-4 transition hover:bg-elevated/50 sm:px-6">
                  <span class="grid size-11 shrink-0 place-items-center rounded-lg" :class="e.main ? 'bg-primary/15 text-primary' : 'bg-elevated text-muted'">
                    <UIcon :name="equipmentIcon(e.kind)" class="size-6" />
                  </span>
                  <span class="min-w-0 flex-1">
                    <span class="flex flex-wrap items-center gap-2">
                      <span class="text-base font-semibold text-highlighted">{{ e.name }}</span>
                      <UBadge v-if="e.main" label="основная" color="primary" variant="subtle" size="sm" />
                      <UBadge v-if="e.kind === 'easybrew'" :label="e.connected ? 'подключена' : 'не подключена'" :color="e.connected ? 'success' : 'neutral'" variant="subtle" size="sm" />
                    </span>
                    <span class="num mt-0.5 block truncate text-sm text-muted">{{ line(e) }}</span>
                  </span>
                  <UIcon name="i-lucide-chevron-right" class="size-5 shrink-0 text-dimmed" />
                </NuxtLink>
              </li>
            </ul>
          </UCard>
        </section>

        <UEmpty
          v-if="status === 'error' && !list.length"
          icon="i-lucide-cloud-off"
          title="Не удалось загрузить оборудование"
          :actions="[{ label: 'Повторить', icon: 'i-lucide-rotate-cw', onClick: () => refresh() }]"
          variant="naked"
        />
        <UCard v-if="!loading && status === 'success' && !list.length" :ui="{ body: 'p-6 sm:p-8' }">
          <div class="flex items-start gap-4">
            <span class="grid size-12 shrink-0 place-items-center rounded-xl bg-primary/15 text-primary">
              <UIcon name="i-lucide-cooking-pot" class="size-7" />
            </span>
            <div>
              <h2 class="text-xl font-semibold text-highlighted">Оборудования пока нет</h2>
              <p class="mt-1 text-base text-muted">
                Начните с того, на чём варите, — кастрюли, котла или пивоварни: рецепты возьмут её объём и эффективность.
                Ферментеры, кеги, приборы и остальное — тоже сюда.
              </p>
            </div>
          </div>
          <UButton label="Добавить оборудование" icon="i-lucide-plus" size="lg" class="mt-6" @click="adding = true" />
        </UCard>
      </div>
      <EquipmentModal v-model:open="adding" @saved="refresh()" />
    </template>
  </UDashboardPanel>
</template>
