// Сервис-воркер brewapp: Web Push — подсказки, закладки и конец программы приходят, даже когда вкладка закрыта.
// Адрес сервиса — параметр регистрации (/sw.js?api=…): кнопки в уведомлении шлют команды прямо ему, с cookie входа.
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
    data: { path: note.action?.path ?? null },
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
    // не вышло или нажали на само уведомление — открыть приложение
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    const open = windows.find(w => w.url.startsWith(self.registration.scope))
    if (open) return open.focus()
    return self.clients.openWindow(self.registration.scope)
  })())
})
