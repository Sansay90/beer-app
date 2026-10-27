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
      user.value = await $api('/api/auth/me')
      unreachable.value = false
    } catch (e) {                     // 401 — гость
      user.value = null
      unreachable.value = isOffline(e)
    }
    checked.value = true
    return user.value
  }

  async function login(email: string, password: string) {
    user.value = await $api('/api/auth/login', { method: 'POST', body: { email, password } })
  }

  async function register(email: string, password: string) {
    user.value = await $api('/api/auth/register', { method: 'POST', body: { email, password } })
  }

  async function forgot(email: string) {
    await $api('/api/auth/forgot', { method: 'POST', body: { email } })
  }

  async function reset(token: string, password: string) {
    user.value = await $api('/api/auth/reset', { method: 'POST', body: { token, password } })
  }

  async function verify(token: string) {
    const me = await $api('/api/auth/verify', { method: 'POST', body: { token } })
    if (user.value?.id === me.id) user.value = me
    return me
  }

  async function resendVerify() {
    await $api('/api/auth/verify/resend', { method: 'POST' })
  }

  async function logout() {
    // уведомления этого браузера были для этого пользователя
    const push = usePush()
    if (push.state.value === 'on') await push.disable().catch(() => {})
    await $api('/api/auth/logout', { method: 'POST' }).catch(() => {})
    // данные прежнего пользователя в сторах и открытый поток событий сбрасывает полная перезагрузка
    window.location.assign(`${useRuntimeConfig().app.baseURL}recipes`)
  }

  /** Сервис ответил 401: сессия истекла или её закрыли (новый пароль на другом устройстве). */
  function expired() {
    user.value = null
  }

  return { user, checked, unreachable, isAdmin, refresh, login, register, forgot, reset, verify, resendVerify, logout, expired }
})
