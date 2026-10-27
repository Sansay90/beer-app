export type AuthMode = 'login' | 'register' | 'forgot'

/** Панель входа — одна на приложение (components/auth/Drawer.vue). next — куда перейти после входа; без него человек
 *  остаётся на месте, а закрытый раздел под окном сам откроется. */
export const useAuthDrawer = createSharedComposable(() => {
  const open = ref(false)
  const mode = ref<AuthMode>('login')
  const next = ref<string | null>(null)

  function show(m: AuthMode = 'login', to?: string) {
    mode.value = m
    next.value = to ?? null
    open.value = true
  }

  return { open, mode, next, show }
})
