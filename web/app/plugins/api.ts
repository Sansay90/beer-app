import createClient from 'openapi-fetch'
import type { paths } from '~/types/bridge'

/** Типизированный клиент сервиса: пути, тела запросов и ответы — из OpenAPI-схемы.
 *  Вход — httpOnly-cookie сервиса: запросы идут с ним. Истёкшая сессия (401) — пользователь вышел, и закрытые
 *  разделы сами покажут приглашение войти (layouts/default.vue). */
export default defineNuxtPlugin({
  name: 'api',
  setup() {
    const configured = String(useRuntimeConfig().public.bridge || '').replace(/\/$/, '')
    // пусто — тот же хост, что отдал страницу. В dev сервис живёт отдельно на :8000 — на том же имени хоста,
    // иначе браузер не приложит cookie (localhost и 127.0.0.1 для него разные сайты)
    const bridgeUrl = configured
      || (import.meta.dev ? `${window.location.protocol}//${window.location.hostname}:8000` : window.location.origin)

    const api = createClient<paths>({ baseUrl: bridgeUrl, credentials: 'include' })
    api.use({
      onResponse({ request, response }) {
        if (response.status !== 401 || new URL(request.url).pathname.startsWith('/api/auth/')) return
        useAuthStore().expired()
      },
    })

    return {
      provide: { api, bridgeUrl },
    }
  },
})
