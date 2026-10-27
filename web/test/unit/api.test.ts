import { describe, expect, it } from 'vitest'
import { errorText, isOffline } from '~/utils/api'

/** Как FetchError ofetch: ответ сервиса (или его нет) и разобранное тело. */
function fetchError(status?: number, data?: unknown) {
  return Object.assign(new Error('[GET] "/api/x"'), {
    name: 'FetchError',
    response: status ? new Response(null, { status }) : undefined,
    data,
  })
}

describe('ошибки запросов к сервису', () => {
  it('текст — из detail FastAPI', () => {
    expect(errorText(fetchError(404, { detail: 'рецепт не найден' }))).toBe('рецепт не найден')
    expect(errorText(fetchError(422, { detail: [{ msg: 'слишком коротко' }, { msg: 'не почта' }] }))).toBe('слишком коротко; не почта')
  })

  it('без detail — код ответа', () => {
    expect(errorText(fetchError(502, '<html>'))).toBe('Сервис ответил ошибкой 502')
  })

  it('ошибка useFetch / useAsyncData — FetchError в причине', () => {
    const nuxtError = new Error('Not Found', { cause: fetchError(404, { detail: 'рецепт не найден' }) })
    expect(errorText(nuxtError)).toBe('рецепт не найден')
    expect(isOffline(nuxtError)).toBe(false)
  })

  it('сервис не ответил вовсе', () => {
    expect(isOffline(fetchError())).toBe(true)
    expect(isOffline(new Error('', { cause: fetchError() }))).toBe(true)
    expect(isOffline(fetchError(500))).toBe(false)
  })

  it('не запрос — текст самой ошибки', () => {
    expect(errorText(new Error('«a.heic» не открылось'))).toBe('«a.heic» не открылось')
    expect(isOffline(new TypeError('x is undefined'))).toBe(false)
    expect(errorText('строка')).toBe('строка')
  })
})
