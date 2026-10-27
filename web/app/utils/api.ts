// Ошибки запросов к сервису ($api, useApi, useAsyncData) — текстом для человека.
type Reply = { response?: Response; data?: unknown; status?: number; statusCode?: number }

/** Шлюз не достучался до сервиса: 502–504 без ответа FastAPI (detail) — от Nuxt или nginx, не от сервиса. */
const GATEWAY = new Set([502, 503, 504])

/** Что ответил сервис: код и тело. Ошибка $api — FetchError ofetch (нет response — запрос не дошёл); ошибка
 *  useFetch / useAsyncData — NuxtError с FetchError в cause; а пришедшая с отрисованной на сервере страницей —
 *  NuxtError без FetchError в cause, только с кодом (status) и телом (data). */
function replyOf(e: unknown): { status?: number; data?: unknown; failed: boolean } {
  for (let x = e; x instanceof Error; x = x.cause) {
    if (x.name === 'FetchError') {
      const f = x as Error & Reply
      return { status: f.response?.status, data: f.data, failed: !f.response }
    }
  }
  // NuxtError с сервера: cause у неё — не Error (сам разобранный объект ошибки); причина-Error — сбой не запроса,
  // его текст — сам message
  const n = e instanceof Error && !(e.cause instanceof Error) ? e as Error & Reply : undefined
  return { status: n?.status ?? n?.statusCode, data: n?.data, failed: false }
}

/** Сервис не ответил: нет сети, сервис недоступен. */
export function isOffline(e: unknown) {
  const { status, data, failed } = replyOf(e)
  return failed || (status != null && GATEWAY.has(status) && detailText(data) === undefined)
}

/** Текст ошибки: detail ответа FastAPI, код ответа сервиса или текст самой ошибки. */
export function errorText(e: unknown) {
  const { status, data } = replyOf(e)
  if (status != null) return detailText(data) ?? `Сервис ответил ошибкой ${status}`
  return e instanceof Error ? e.message : String(e)
}

/** Код ответа сервиса, если ошибка — от него: 404 — нет такого, 5xx — сбой. */
export function errorStatus(e: unknown) {
  return replyOf(e).status
}

function detailText(data: unknown): string | undefined {
  const detail = (data as { detail?: unknown } | undefined)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(d => (d as { msg?: string }).msg).filter(Boolean).join('; ')
  return undefined
}
