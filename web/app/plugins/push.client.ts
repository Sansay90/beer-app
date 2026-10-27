/** Сервис-воркер для Web Push — на любой странице; уже выданная подписка освежается на посреднике. */
export default defineNuxtPlugin({
  name: 'push',
  dependsOn: ['api'],
  setup() {
    if (!('serviceWorker' in navigator)) return
    const { $bridgeUrl } = useNuxtApp()
    const base = useRuntimeConfig().app.baseURL
    const push = usePush()
    // адрес посредника — параметром: кнопки в уведомлении шлют команды прямо ему
    navigator.serviceWorker.register(`${base}sw.js?api=${encodeURIComponent($bridgeUrl)}`, { scope: base })
      .then(() => push.sync())
      .catch(e => console.warn('уведомления недоступны:', e))
  },
})
