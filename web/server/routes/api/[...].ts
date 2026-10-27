// /api — сервис (runtimeConfig.apiServer, NUXT_API_SERVER). Сюда ходят браузер в dev, запросы $api при рендере
// на сервере (с cookie посетителя) и локальный Docker; в проде nginx отдаёт /api сервису сам, мимо Nuxt.
// Ответ — потоком (SSE /api/stream), Set-Cookie входа проходит как есть; адрес посетителя и схема — в X-Forwarded-*,
// как у nginx (deploy/nginx.conf). Origin браузера сервис проверяет сам: свой сайт — APP_URL, без него — этот ПК.
export default defineEventHandler(async (event) => {
  const { apiServer } = useRuntimeConfig(event)
  // посетитель ушёл (закрыл вкладку с потоком SSE) — запрос к сервису тоже прерывается
  const gone = new AbortController()
  event.node.res.once('close', () => gone.abort())
  try {
    return await proxyRequest(event, apiServer.replace(/\/$/, '') + event.path, {
      headers: {
        'x-forwarded-for': [getRequestHeader(event, 'x-forwarded-for'), getRequestIP(event)].filter(Boolean).join(', '),
        'x-forwarded-proto': getRequestProtocol(event),
      },
      fetchOptions: { signal: gone.signal },
    })
  } catch (e) {
    if (!gone.signal.aborted) throw e
  }
})
