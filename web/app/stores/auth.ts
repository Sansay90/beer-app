import type { Me } from '~/types'

/** Кто вошёл. Сама сессия — httpOnly-cookie сервиса, здесь только профиль. */
export const useAuthStore = defineStore('auth', () => {
  const { $api } = useNuxtApp()
  const user = ref<Me | null>(null)
  const checked = ref(false)          // сервис уже спрашивали
  const unreachable = ref(false)      // сервис не ответил
  // права решает сервис (service/app/access.py), здесь — только что показывать
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function refresh() {
    try {
      const { data, response } = await $api.GET('/api/auth/me')
      user.value = response.ok ? data ?? null : null
      unreachable.value = false
    } catch {
      user.value = null
      unreachable.value = true
    }
    checked.value = true
    return user.value
  }

  async function login(email: string, password: string) {
    user.value = unwrap(await $api.POST('/api/auth/login', { body: { email, password } }))
  }

  async function register(email: string, password: string) {
    user.value = unwrap(await $api.POST('/api/auth/register', { body: { email, password } }))
  }

  async function forgot(email: string) {
    unwrap(await $api.POST('/api/auth/forgot', { body: { email } }))
  }

  async function reset(token: string, password: string) {
    user.value = unwrap(await $api.POST('/api/auth/reset', { body: { token, password } }))
  }

  async function verify(token: string) {
    const me = unwrap(await $api.POST('/api/auth/verify', { body: { token } }))
    if (user.value?.id === me.id) user.value = me
    return me
  }

  async function resendVerify() {
    unwrap(await $api.POST('/api/auth/verify/resend'))
  }

  async function logout() {
    // уведомления этого браузера были для этого пользователя
    const push = usePush()
    if (push.state.value === 'on') await push.disable().catch(() => {})
    await $api.POST('/api/auth/logout').catch(() => {})
    // данные прежнего пользователя в сторах и открытый поток событий сбрасывает полная перезагрузка
    window.location.assign(`${useRuntimeConfig().app.baseURL}recipes`)
  }

  /** Сервис ответил 401: сессия истекла или её закрыли (новый пароль на другом устройстве). */
  function expired() {
    user.value = null
  }

  return { user, checked, unreachable, isAdmin, refresh, login, register, forgot, reset, verify, resendVerify, logout, expired }
})
