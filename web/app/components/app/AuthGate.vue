<script setup lang="ts">
// Закрытый раздел: меню показывает все разделы, а здесь вместо страницы — чем раздел хорош и как в него попасть.
// teaser — какой раздел показываем (meta.teaser страницы).
type Teaser = 'brew' | 'recipe' | 'settings'

const props = defineProps<{ title?: string; admin?: boolean; teaser?: Teaser }>()
const auth = useAuthStore()
const drawer = useAuthDrawer()

const TEASERS: Record<Teaser, { icon: string; title: string; points: { icon: string; text: string }[] }> = {
  brew: {
    icon: 'i-lucide-flame',
    title: 'Варка с телефона',
    points: [
      { icon: 'i-lucide-thermometer', text: 'Температура и шаги затирания вживую, с графиком' },
      { icon: 'i-lucide-bell-ring', text: 'Напоминания о закладках хмеля — даже когда вкладка закрыта' },
      { icon: 'i-lucide-history', text: 'Каждая варка сохраняется: температура, события, электричество' },
    ],
  },
  recipe: {
    icon: 'i-lucide-notebook-pen',
    title: 'Свои рецепты',
    points: [
      { icon: 'i-lucide-calculator', text: 'Плотность, горечь, цвет и крепость считаются по ингредиентам' },
      { icon: 'i-lucide-droplets', text: 'Вода: соли, ионный профиль, объёмы затора и промывки' },
      { icon: 'i-lucide-globe', text: 'Рецепт виден только вам, пока вы его не опубликуете' },
    ],
  },
  settings: {
    icon: 'i-lucide-sliders-horizontal',
    title: 'Расчёты под вашу систему',
    points: [
      { icon: 'i-lucide-gauge', text: 'Эффективность и испарение вашего оборудования — в каждом рецепте' },
      { icon: 'i-lucide-bell', text: 'Уведомления о варке на телефон и компьютер' },
      { icon: 'i-lucide-plug', text: 'Пивоварня Easy Brew Connect — на связи из любого места' },
    ],
  },
}
const pitch = computed(() => (props.teaser ? TEASERS[props.teaser] : null))
</script>

<template>
  <UDashboardPanel id="auth-gate">
    <template #header>
      <UDashboardNavbar :title="title">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <UEmpty
        v-if="admin"
        icon="i-lucide-shield"
        title="Раздел для администраторов"
        :description="auth.user ? 'Попросите администратора выдать вам права, если они нужны.' : 'Войдите под учётной записью администратора.'"
        :actions="auth.user ? [] : [{ label: 'Войти', icon: 'i-lucide-log-in', onClick: () => drawer.show('login') }]"
        variant="naked"
        class="m-auto"
      />

      <div v-else class="m-auto w-full max-w-md py-6">
        <div class="grid size-12 place-items-center rounded-xl bg-primary/15 text-primary">
          <UIcon :name="pitch?.icon ?? 'i-lucide-lock-keyhole'" class="size-6" />
        </div>
        <h2 class="mt-6 text-2xl font-semibold text-balance text-highlighted">{{ pitch?.title ?? 'Раздел доступен после входа' }}</h2>
        <p class="mt-2 text-muted">Доступно после регистрации — бесплатно, нужна только почта.</p>

        <ul v-if="pitch" class="mt-6 space-y-3">
          <li v-for="p in pitch.points" :key="p.text" class="flex gap-3">
            <UIcon :name="p.icon" class="mt-0.5 size-5 shrink-0 text-primary" />
            <span class="text-default">{{ p.text }}</span>
          </li>
        </ul>

        <div class="mt-8 flex flex-wrap items-center gap-x-4 gap-y-3">
          <UButton label="Зарегистрироваться" size="lg" @click="drawer.show('register')" />
          <UButton label="У меня есть аккаунт" color="neutral" variant="link" size="lg" class="px-0" @click="drawer.show('login')" />
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
