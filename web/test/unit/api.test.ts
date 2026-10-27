import { describe, expect, it } from 'vitest'
import { errorStatus, errorText, isOffline } from '~/utils/api'

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
    // ошибка useAsyncData не от запроса: NuxtError с причиной — не ответ сервиса
    const bug = Object.assign(new Error('x is undefined', { cause: new TypeError('x is undefined') }), { statusCode: 500 })
    expect(errorText(bug)).toBe('x is undefined')
    expect(errorStatus(bug)).toBeUndefined()
  })

  // ошибка, случившаяся при рендере на сервере: NuxtError приходит без cause — только код и тело ответа
  // (Nuxt восстанавливает её из данных страницы: cause — сам разобранный объект, не Error)
  const fromServer = (status: number, data?: unknown) => {
    const fields = { message: `[GET] "/api/recipes": ${status}`, status, statusCode: status, data }
    return Object.assign(new Error(fields.message, { cause: fields }), fields)
  }

  it('с отрисованной на сервере страницей — detail и код из самой NuxtError', () => {
    expect(errorText(fromServer(404, { detail: 'рецепт не найден' }))).toBe('рецепт не найден')
    expect(errorStatus(fromServer(404, { detail: 'рецепт не найден' }))).toBe(404)
    expect(errorText(fromServer(500))).toBe('Сервис ответил ошибкой 500')
    expect(isOffline(fromServer(404, { detail: 'рецепт не найден' }))).toBe(false)
  })

  it('шлюз без ответа сервиса (502–504 без detail) — нет связи; 503 от самого сервиса — его текст', () => {
    expect(isOffline(fromServer(502, { statusCode: 502, statusMessage: 'Bad Gateway' }))).toBe(true)
    expect(isOffline(fetchError(504, '<html>'))).toBe(true)
    const busy = fetchError(503, { detail: 'пивоварня не в сети' })
    expect(isOffline(busy)).toBe(false)
    expect(errorText(busy)).toBe('пивоварня не в сети')
  })
})
