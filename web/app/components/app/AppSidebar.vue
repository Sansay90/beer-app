<script setup lang="ts">
const brewery = useBreweryStore()
const auth = useAuthStore()
const { enabled: soundOn, toggle: toggleSound } = useSound()

// на узком экране меню — выдвижная панель: выбранный пункт её закрывает. Своей смены маршрута у панели
// (autoClose) мало: закрытый раздел вместо страницы показывает витрину, и маршрут Nuxt тогда не меняется
const open = ref(false)
const close = () => { open.value = false }

const userItems = computed(() => [
  [{ type: 'label' as const, label: auth.user?.email }],
  [
    { label: 'Настройки', icon: 'i-lucide-settings', to: '/settings', onSelect: close },
    { label: 'Выйти', icon: 'i-lucide-log-out', onSelect: () => auth.logout() },
  ],
])
const colorMode = useColorMode()

// разделы видны всем — гостя закрытый раздел зовёт зарегистрироваться (AuthGate); пользователи — администратору.
// У вошедшего «Рецепты» раскрыты: все и свои (?scope=mine) — новые подразделы (избранное, подборки) встают сюда же
const route = useRoute()
const recipes = computed(() => {
  if (!auth.user) return { label: 'Рецепты', icon: 'i-lucide-book-open', to: '/recipes', onSelect: close }
  const mine = route.path === '/recipes' && route.query.scope === 'mine'
  return {
    label: 'Рецепты',
    icon: 'i-lucide-book-open',
    defaultOpen: true,
    active: route.path.startsWith('/recipes'),
    children: [
      { label: 'Все рецепты', to: '/recipes', active: route.path === '/recipes' && !mine, onSelect: close },
      { label: 'Мои рецепты', to: '/recipes?scope=mine', active: mine, onSelect: close },
    ],
  }
})
const nav = computed(() => [
  { label: 'Варка', icon: 'i-lucide-flame', to: '/', onSelect: close },
  recipes.value,
  { label: 'Настройки', icon: 'i-lucide-settings', to: '/settings', onSelect: close },
  ...(auth.isAdmin ? [{ label: 'Пользователи', icon: 'i-lucide-users', to: '/admin/users', onSelect: close }] : []),
])
const drawer = useAuthDrawer()

function login() {
  close()
  drawer.show('login')
}

const link = computed(() => {
  if (!brewery.connected) return { label: 'Нет связи с сервисом', tone: 'text-error', icon: 'i-lucide-server' }
  if (!brewery.online) return { label: 'Пивоварня не в сети', tone: 'text-warning', icon: 'i-lucide-wifi-off' }
  return { label: 'Пивоварня на связи', tone: 'text-success', icon: 'i-lucide-wifi' }
})

const THEMES = [
  { value: 'system', label: 'как в системе', icon: 'i-lucide-monitor' },
  { value: 'light', label: 'светлая', icon: 'i-lucide-sun' },
  { value: 'dark', label: 'тёмная', icon: 'i-lucide-moon' },
]
const theme = computed(() => THEMES.find(t => t.value === colorMode.preference) ?? THEMES[0]!)
const themeItems = computed(() => [[
  { type: 'label' as const, label: 'Тема' },
  ...THEMES.map(t => ({
    label: t.label[0]!.toUpperCase() + t.label.slice(1),
    icon: t.icon,
    type: 'checkbox' as const,
    checked: colorMode.preference === t.value,
    onUpdateChecked: () => { colorMode.preference = t.value },
  })),
]])
</script>

<template>
  <UDashboardSidebar
    id="main"
    v-model:open="open"
    collapsible
    resizable
    :min-size="13"
    :default-size="15"
    :max-size="20"
    class="bg-elevated/25"
    :ui="{ footer: 'lg:border-t lg:border-default' }"
  >
    <template #header="{ collapsed }">
      <div class="flex items-center gap-2.5" :class="collapsed ? 'mx-auto' : 'px-1'">
        <div class="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary">
          <UIcon name="i-lucide-beer" class="size-5" />
        </div>
        <span v-if="!collapsed" class="font-semibold text-highlighted">Пивоварня</span>
      </div>
    </template>

    <template #default="{ collapsed }">
      <UNavigationMenu :items="nav" :collapsed="collapsed" orientation="vertical" tooltip />
    </template>

    <template #footer="{ collapsed }">
      <div class="flex w-full flex-col gap-1">
        <UDropdownMenu v-if="auth.user" :items="userItems" :content="{ side: collapsed ? 'right' : 'top', align: 'start' }">
          <UButton
            icon="i-lucide-circle-user"
            :label="collapsed ? undefined : auth.user.email"
            color="neutral"
            variant="ghost"
            :block="!collapsed"
            :square="collapsed"
            :class="collapsed ? 'mx-auto' : 'justify-start'"
            :ui="{ label: 'truncate' }"
            aria-label="Аккаунт"
          />
        </UDropdownMenu>
        <UButton
          v-else
          icon="i-lucide-log-in"
          :label="collapsed ? undefined : 'Войти'"
          color="primary"
          variant="soft"
          :block="!collapsed"
          :square="collapsed"
          :class="collapsed ? 'mx-auto' : 'justify-start'"
          aria-label="Войти"
          @click="login"
        />
        <UTooltip v-if="auth.user" :text="link.label" :disabled="!collapsed">
          <div class="flex items-center gap-2 px-2.5 py-1.5 text-sm" :class="collapsed && 'justify-center'">
            <UIcon :name="link.icon" class="size-5 shrink-0" :class="link.tone" />
            <span v-if="!collapsed" class="truncate text-muted">{{ link.label }}</span>
          </div>
        </UTooltip>
        <UTooltip :text="soundOn ? 'Звук включён' : 'Звук выключен'" :disabled="!collapsed">
          <UButton
            :icon="soundOn ? 'i-lucide-bell-ring' : 'i-lucide-bell-off'"
            :label="collapsed ? undefined : soundOn ? 'Звук включён' : 'Звук выключен'"
            :color="soundOn ? 'primary' : 'neutral'"
            variant="ghost"
            :block="!collapsed"
            :square="collapsed"
            :class="collapsed ? 'mx-auto' : 'justify-start'"
            @click="toggleSound"
          />
        </UTooltip>
        <UDropdownMenu :items="themeItems" :content="{ side: collapsed ? 'right' : 'top', align: 'start' }">
          <UButton
            :icon="theme.icon"
            :label="collapsed ? undefined : `Тема: ${theme.label}`"
            color="neutral"
            variant="ghost"
            :block="!collapsed"
            :square="collapsed"
            :class="collapsed ? 'mx-auto' : 'justify-start'"
            :aria-label="`Тема: ${theme.label}`"
          />
        </UDropdownMenu>
      </div>
    </template>
  </UDashboardSidebar>
</template>
