// /api — сервис (runtimeConfig.apiServer, NUXT_API_SERVER). Сюда ходят браузер в dev, запросы $api при рендере
// на сервере (с cookie посетителя) и локальный Docker; в проде nginx отдаёт /api сервису сам, мимо Nuxt.
// Ответ — потоком (SSE /api/stream), Set-Cookie входа проходит как есть. Origin браузера сервис проверяет сам:
// свой сайт — APP_URL, без него — этот ПК. Адрес посетителя и схема — X-Forwarded-* (server/utils/forwarded.ts).
const PAYLOAD_METHODS = new Set(['PATCH', 'POST', 'PUT', 'DELETE'])

export default defineEventHandler(async (event) => {
  const { apiServer, trustProxy } = useRuntimeConfig(event)
  const headers = proxyHeaders(getProxyRequestHeaders(event), {
    trust: !!trustProxy,
    ip: getRequestIP(event),
    secure: getRequestProtocol(event, { xForwardedProto: false }) === 'https',
  })

  // посетитель ушёл (закрыл вкладку с потоком SSE) — запрос к сервису тоже прерывается
  const gone = new AbortController()
  event.node.res.once('close', () => gone.abort())
  try {
    return await sendProxy(event, apiServer.replace(/\/$/, '') + event.path, {
      fetchOptions: {
        method: event.method,
        body: PAYLOAD_METHODS.has(event.method) ? await readRawBody(event, false) : undefined,
        headers,
        signal: gone.signal,
      },
    })
  } catch (e) {
    if (!gone.signal.aborted) throw e
  }
})
