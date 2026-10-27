// Заголовки запроса к сервису через прокси /api: адрес посетителя и схема — в X-Forwarded-*, по ним лимиты по адресу
// и cookie Secure. Пришедшим X-Forwarded-* верим только за своим прокси (trust — runtimeConfig.trustProxy,
// NUXT_TRUST_PROXY=1): без него их пишет сам посетитель, и подставной адрес обходит лимиты.

/** Заголовки «откуда запрос»: без доверия к прокси пришедшие не пересылаются. */
const FORWARDED = new Set(['forwarded', 'x-forwarded-for', 'x-forwarded-proto', 'x-forwarded-host', 'x-real-ip'])

export interface Connection {
  trust: boolean               // перед Nuxt свой прокси
  ip?: string                  // адрес соединения с Nuxt; нет — запрос рендера на сервере
  secure: boolean              // соединение с Nuxt — по TLS
}

/** Пришедшие заголовки (подставные X-Forwarded-* — долой) и свои X-Forwarded-For / X-Forwarded-Proto. */
export function proxyHeaders(incoming: Record<string, string | undefined>, c: Connection): Record<string, string> {
  const headers: Record<string, string> = {}
  for (const [name, value] of Object.entries(incoming)) {
    if (value !== undefined && (c.trust || !FORWARDED.has(name))) headers[name] = value
  }
  const ip = [c.trust ? incoming['x-forwarded-for'] : undefined, c.ip].filter(Boolean).join(', ')
  if (ip) headers['x-forwarded-for'] = ip
  headers['x-forwarded-proto'] = (c.trust && incoming['x-forwarded-proto']?.split(',')[0]?.trim()) || (c.secure ? 'https' : 'http')
  return headers
}
