/** Ошибка сервиса с текстом для человека (поле detail ответа FastAPI). */
export class ApiError extends Error {}

interface FetchResult<T> {
  data?: T
  error?: unknown
  response: Response
}

/** Результат openapi-fetch → данные или ApiError с понятным текстом. */
export function unwrap<T>(result: FetchResult<T>): T {
  if (result.error !== undefined || !result.response.ok) {
    throw new ApiError(errorDetail(result.error) ?? `Сервис ответил ошибкой ${result.response.status}`)
  }
  return result.data as T
}

function errorDetail(error: unknown): string | undefined {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(d => (d as { msg?: string }).msg).filter(Boolean).join('; ')
  return undefined
}
