import { describe, expect, it } from 'vitest'
import { proxyHeaders } from '../../server/utils/forwarded'

describe('заголовки запроса к сервису через прокси /api', () => {
  const incoming = {
    'cookie': 'brewapp_session=abc',
    'content-type': 'application/json',
    'x-forwarded-for': '6.6.6.6',
    'x-forwarded-proto': 'https',
    'x-real-ip': '6.6.6.6',
    'forwarded': 'for=6.6.6.6',
  }

  it('без своего прокси — подставные X-Forwarded-* долой, адрес и схема — самого соединения', () => {
    expect(proxyHeaders(incoming, { trust: false, ip: '192.168.1.5', secure: false })).toEqual({
      'cookie': 'brewapp_session=abc',
      'content-type': 'application/json',
      'x-forwarded-for': '192.168.1.5',
      'x-forwarded-proto': 'http',
    })
  })

  it('адреса нет (запрос рендера на сервере) — X-Forwarded-For не отправляется, даже пустым', () => {
    const h = proxyHeaders(incoming, { trust: false, secure: false })
    expect(h['x-forwarded-for']).toBeUndefined()
    expect(h['x-real-ip']).toBeUndefined()
    expect(h['x-forwarded-proto']).toBe('http')
  })

  it('за своим прокси — его цепочка адресов дополняется, схема — от него', () => {
    const h = proxyHeaders({ ...incoming, 'x-forwarded-for': '203.0.113.7', 'x-forwarded-proto': 'https, http' },
      { trust: true, ip: '172.18.0.3', secure: false })
    expect(h['x-forwarded-for']).toBe('203.0.113.7, 172.18.0.3')
    expect(h['x-forwarded-proto']).toBe('https')
    expect(proxyHeaders({}, { trust: true, ip: '172.18.0.3', secure: true })['x-forwarded-proto']).toBe('https')
  })
})
