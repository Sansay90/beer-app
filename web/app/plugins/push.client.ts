/** Сервис-воркер для Web Push — на любой странице; после входа выданная подписка освежается на сервисе. */
export default defineNuxtPlugin({
  name: 'push',
  dependsOn: ['api'],
  setup() {
    if (!('serviceWorker' in navigator)) return
    const { $apiBase } = useNuxtApp()
    const base = useRuntimeConfig().app.baseURL
    const auth = useAuthStore()
    const push = usePush()
    // адрес сервиса — параметром: кнопки в уведомлении шлют команды прямо ему
    navigator.serviceWorker.register(`${base}sw.js?api=${encodeURIComponent($apiBase)}`, { scope: base })
      .then(() => watch(() => auth.user?.id, id => id && push.sync(), { immediate: true }))
      .catch(e => console.warn('уведомления недоступны:', e))
  },
})
