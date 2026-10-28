// Сервис-воркер brewapp: Web Push — подсказки, закладки, конец программы, комментарии и ответы приходят, даже когда
// вкладка закрыта. Адрес сервиса — параметр регистрации (/sw.js?api=…): кнопки в уведомлении шлют команды прямо ему,
// с cookie входа. url уведомления — куда вести по нажатию (комментарий на странице рецепта).
const API = new URL(self.location.href).searchParams.get('api') || self.location.origin
const ICON = new URL('icon-192.png', self.registration.scope).href

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()))

self.addEventListener('push', (event) => {
  let note = null
  try {
    note = event.data?.json()
  } catch {
    // не JSON — показывать нечего
  }
  if (!note?.title) return
  event.waitUntil(self.registration.showNotification(note.title, {
    body: note.body,
    tag: note.tag,
    icon: ICON,
    // новое уведомление с той же меткой заменяет прежнее — и всё равно всплывает и звучит заново
    renotify: !!note.tag,
    // подсказки и закладки висят, пока не нажмут
    requireInteraction: !!note.urgent,
    actions: note.action ? [{ action: 'act', title: note.action.title }] : [],
    data: { path: note.action?.path ?? null, url: note.url ?? null },
  }))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const path = event.notification.data?.path
  event.waitUntil((async () => {
    if (event.action === 'act' && path) {
      const done = await fetch(API + path, { method: 'POST', credentials: 'include' }).then(r => r.ok, () => false)
      if (done) return
    }
    // не вышло или нажали на само уведомление — открыть приложение, а у уведомления с адресом — сразу там
    const url = event.notification.data?.url ? new URL(event.notification.data.url, self.registration.scope).href : null
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    const open = windows.find(w => w.url.startsWith(self.registration.scope))
    if (!open) return self.clients.openWindow(url ?? self.registration.scope)
    if (!url) return open.focus()
    // перейти можно только во вкладке под управлением воркера — иначе новая вкладка
    const moved = await open.navigate(url).catch(() => null)
    return moved ? moved.focus() : self.clients.openWindow(url)
  })())
})
