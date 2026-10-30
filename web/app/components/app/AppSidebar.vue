<script setup lang="ts">
const brewery = useBreweryStore()
const auth = useAuthStore()
const { enabled: soundOn, toggle: toggleSound } = useSound()

// на узком экране меню — выдвижная панель: выбранный пункт её закрывает. Своей смены маршрута у панели
// (autoClose) мало: закрытый раздел вместо страницы показывает витрину, и маршрут Nuxt тогда не меняется
const open = ref(false)
const close = () => { open.value = false }

const colorMode = useColorMode()

// разделы видны всем — гостя закрытый раздел зовёт зарегистрироваться (AuthGate); пользователи — администратору.
// У вошедшего «Рецепты» раскрыты: все, свои и избранные (?scope=…) — новые подразделы (подборки) встают сюда же
const route = useRoute()
const recipes = computed(() => {
  if (!auth.user) return { label: 'Рецепты', icon: 'i-lucide-book-open', to: '/recipes', onSelect: close }
  const scope = route.path === '/recipes' ? route.query.scope ?? 'all' : null
  const sub = (label: string, value: string) => ({
    label,
    to: value === 'all' ? '/recipes' : `/recipes?scope=${value}`,
    active: scope === value,
    onSelect: close,
  })
  return {
    label: 'Рецепты',
    icon: 'i-lucide-book-open',
    defaultOpen: true,
    active: route.path.startsWith('/recipes'),
    children: [sub('Все рецепты', 'all'), sub('Мои рецепты', 'mine'), sub('Избранное', 'favorites')],
  }
})
// метка у «Варки» — только когда пивоварня варит: состояние самой пивоварни — у оборудования и на странице партии
const status = computed(() => (auth.user && brewery.phase.running
  ? { label: 'идёт варка', color: 'primary' as const }
  : undefined))
// «Варка» ведёт прямо на идущую партию: через главную вышел бы лишний круг с перерисовкой страницы
const { brew: current, refresh: refreshCurrent } = useCurrentBrew()
const changed = useBrewChanged()
if (import.meta.client) watch([() => route.path, changed], () => { if (auth.user) refreshCurrent() })
// уведомления — вошедшему, с числом непрочитанных: при входе, переходах, возвращении на вкладку и раз в минуту
const notices = useNotifications()
const visibility = useDocumentVisibility()
if (import.meta.client) watch([() => auth.user?.id, () => route.path, visibility], () => notices.refresh(), { immediate: true })
useIntervalFn(() => { if (visibility.value === 'visible') notices.refresh() }, 60_000)
const unread = computed(() => notices.unread.value
  && { label: notices.unread.value > 99 ? '99+' : String(notices.unread.value), color: 'primary' as const, variant: 'solid' as const })

const nav = computed(() => [
  // страница партии — это и есть «Варка»; «Мои варки» — только список
  { label: 'Варка', icon: 'i-lucide-flame', to: current.value ? `/brews/${current.value.id}` : '/', active: route.path === '/' || /^\/brews\/[^/]+$/.test(route.path), badge: status.value && { ...status.value, variant: 'subtle' as const }, onSelect: close },
  // журнал варок — и с пивоварни, и без неё
  ...(auth.user ? [{ label: 'Мои варки', icon: 'i-lucide-notebook-pen', to: '/brews', active: route.path === '/brews', onSelect: close }] : []),
  // на чём варит пивовар: рецепт партии считается под него, подключённая пивоварня — связь и калибровка
  ...(auth.user ? [{ label: 'Оборудование', icon: 'i-lucide-cooking-pot', to: '/equipment', active: route.path.startsWith('/equipment'), onSelect: close }] : []),
  recipes.value,
  ...(auth.user ? [{ label: 'Уведомления', icon: 'i-lucide-bell', to: '/notifications', badge: unread.value || undefined, onSelect: close }] : []),
  ...(auth.isAdmin ? [{ label: 'Пользователи', icon: 'i-lucide-users', to: '/admin/users', onSelect: close }] : []),
])
const drawer = useAuthDrawer()

function login() {
  close()
  drawer.show('login')
}

const THEMES = [
  { value: 'system', label: 'как в системе', icon: 'i-lucide-monitor' },
  { value: 'light', label: 'светлая', icon: 'i-lucide-sun' },
  { value: 'dark', label: 'тёмная', icon: 'i-lucide-moon' },
]
const theme = computed(() => THEMES.find(t => t.value === colorMode.preference) ?? THEMES[0]!)
const themeChoices = computed(() => THEMES.map(t => ({
  label: t.label[0]!.toUpperCase() + t.label.slice(1),
  icon: t.icon,
  type: 'checkbox' as const,
  checked: colorMode.preference === t.value,
  onUpdateChecked: () => { colorMode.preference = t.value },
})))
const themeItems = computed(() => [[{ type: 'label' as const, label: 'Тема' }, ...themeChoices.value]])

// всё личное и редкое — в меню аккаунта, внизу панели одна строка: кто вы → страница и настройки → звук и тема → выход
const userItems = computed(() => [
  [{ type: 'label' as const, label: auth.user?.name ?? auth.user?.email }],
  [
    ...(auth.user?.name ? [{ label: 'Моя страница', icon: 'i-lucide-user', to: brewerPath(auth.user.name), onSelect: close }] : []),
    { label: 'Настройки', icon: 'i-lucide-settings', to: '/settings', onSelect: close },
  ],
  [
    {
      label: soundOn.value ? 'Звук включён' : 'Звук выключен',
      icon: soundOn.value ? 'i-lucide-bell-ring' : 'i-lucide-bell-off',
      type: 'checkbox' as const,
      checked: soundOn.value,
      onUpdateChecked: () => toggleSound(),
      onSelect: (e: Event) => e.preventDefault(),          // меню не закрывается — видно, что переключилось
    },
    { label: `Тема: ${theme.value.label}`, icon: theme.value.icon, children: [themeChoices.value] },
  ],
  [{ label: 'Выйти', icon: 'i-lucide-log-out', onSelect: () => auth.logout() }],
])
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
      <UNavigationMenu
        :items="nav"
        :collapsed="collapsed"
        orientation="vertical"
        tooltip
        :ui="{ link: 'gap-2.5 py-2 text-base', linkLeadingIcon: 'size-5.5', childLink: 'py-1.5 text-[0.9375rem]' }"
      />
    </template>

    <template #footer="{ collapsed }">
      <UDropdownMenu v-if="auth.user" :items="userItems" :content="{ side: collapsed ? 'right' : 'top', align: 'start' }" :ui="{ content: 'min-w-60' }">
        <UButton
          :label="collapsed ? undefined : auth.user.name ?? auth.user.email"
          :trailing-icon="collapsed ? undefined : 'i-lucide-chevrons-up-down'"
          color="neutral"
          variant="ghost"
          :block="!collapsed"
          size="lg"
          class="text-base"
          :square="collapsed"
          :class="collapsed ? 'mx-auto' : 'justify-start'"
          :ui="{ label: 'truncate', trailingIcon: 'ms-auto text-dimmed' }"
          aria-label="Аккаунт"
        >
          <template #leading>
            <UserAvatar :user="auth.user" class="size-7" />
          </template>
        </UButton>
      </UDropdownMenu>
      <div v-else class="flex w-full items-center gap-1" :class="collapsed && 'flex-col'">
        <UButton
          icon="i-lucide-log-in"
          :label="collapsed ? undefined : 'Войти'"
          color="primary"
          variant="soft"
          :block="!collapsed"
          size="lg"
          class="flex-1 text-base"
          :square="collapsed"
          :class="collapsed ? 'mx-auto' : 'justify-start'"
          aria-label="Войти"
          @click="login"
        />
        <UDropdownMenu :items="themeItems" :content="{ side: collapsed ? 'right' : 'top', align: 'end' }">
          <UButton :icon="theme.icon" color="neutral" variant="ghost" size="lg" square :aria-label="`Тема: ${theme.label}`" />
        </UDropdownMenu>
      </div>
    </template>
  </UDashboardSidebar>
</template>
