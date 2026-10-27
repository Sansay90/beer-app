// Web Push: подписка этого браузера на уведомления сервиса — подсказки, закладки, конец программы.
// Сервис-воркер — public/sw.js, регистрирует плагин push.client.ts.
export type PushState = 'unsupported' | 'denied' | 'off' | 'on'

/** base64url → байты: applicationServerKey для pushManager.subscribe. */
function keyBytes(base64url: string) {
  const b64 = base64url.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(base64url.length / 4) * 4, '=')
  return Uint8Array.from(atob(b64), c => c.charCodeAt(0))
}

function sameKey(sub: PushSubscription, key: Uint8Array) {
  const current = sub.options.applicationServerKey
  if (!current || current.byteLength !== key.length) return false
  const bytes = new Uint8Array(current)
  return key.every((b, i) => b === bytes[i])
}

export const usePush = createSharedComposable(() => {
  const { $api } = useNuxtApp()
  const supported = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
  const state = ref<PushState>(supported ? 'off' : 'unsupported')

  async function current() {
    const reg = await navigator.serviceWorker.ready
    return { reg, sub: await reg.pushManager.getSubscription() }
  }

  /** Подписать браузер и сообщить сервису; ключ сервера сменился — подписаться заново. */
  async function subscribe() {
    const { reg, sub } = await current()
    const key = keyBytes((await $api('/api/push/key')).publicKey)
    let s = sub
    if (s && !sameKey(s, key)) {
      await s.unsubscribe()
      s = null
    }
    s ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key })
    const { endpoint, keys } = s.toJSON()
    await $api('/api/push/subscriptions', {
      method: 'POST',
      body: { endpoint: endpoint!, keys: { p256dh: keys!.p256dh!, auth: keys!.auth! }, userAgent: navigator.userAgent },
    })
  }

  /** При запуске приложения: подписка уже есть — освежить её на сервисе. */
  async function sync() {
    if (!supported) return
    if (Notification.permission === 'denied') {
      state.value = 'denied'
      return
    }
    const { sub } = await current()
    if (!sub || Notification.permission !== 'granted') return
    await subscribe()
    state.value = 'on'
  }

  async function enable() {
    const permission = await Notification.requestPermission()
    if (permission !== 'granted') {
      state.value = permission === 'denied' ? 'denied' : 'off'
      return
    }
    await subscribe()
    state.value = 'on'
  }

  async function disable() {
    const { sub } = await current()
    if (sub) {
      await $api('/api/push/subscriptions', { method: 'DELETE', body: { endpoint: sub.endpoint } }).catch(() => {})
      await sub.unsubscribe()
    }
    state.value = 'off'
  }

  async function test() {
    return (await $api('/api/push/test', { method: 'POST' })).devices
  }

  /** Убрать системное уведомление, когда его подтвердили в приложении. */
  async function close(tag: string) {
    if (!supported) return
    const reg = await navigator.serviceWorker.getRegistration()
    for (const n of await reg?.getNotifications({ tag }) ?? []) n.close()
  }

  return { state, enable, disable, test, sync, close }
})
