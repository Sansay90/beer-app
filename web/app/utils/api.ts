// Ошибки запросов к сервису ($api, useApi, useAsyncData) — текстом для человека.
type FetchErrorLike = Error & { response?: Response; data?: unknown }

/** FetchError ofetch: сама ошибка $api или её причина в ошибке useFetch / useAsyncData (NuxtError). */
function fetchError(e: unknown): FetchErrorLike | null {
  for (let x = e; x instanceof Error; x = x.cause) {
    if (x.name === 'FetchError') return x as FetchErrorLike
  }
  return null
}

/** Сервис не ответил вовсе: нет сети или сервис недоступен. */
export function isOffline(e: unknown) {
  const f = fetchError(e)
  return !!f && !f.response
}

/** Текст ошибки: detail ответа FastAPI, код ответа сервиса или текст самой ошибки. */
export function errorText(e: unknown) {
  const f = fetchError(e)
  if (f?.response) return detailText(f.data) ?? `Сервис ответил ошибкой ${f.response.status}`
  return e instanceof Error ? e.message : String(e)
}

function detailText(data: unknown): string | undefined {
  const detail = (data as { detail?: unknown } | undefined)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(d => (d as { msg?: string }).msg).filter(Boolean).join('; ')
  return undefined
}
