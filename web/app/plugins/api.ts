import type { paths } from '#open-fetch-schemas/api'

/** Клиент сервиса $api (nuxt-open-fetch поверх $fetch): пути, параметры, тела и ответы — из OpenAPI-схемы;
 *  useApi — тот же клиент в useFetch. Сервис — /api того же сайта или runtimeConfig.public.apiBase.
 *  Вход — httpOnly-cookie сервиса: запросы идут с ним. Истёкшая сессия (401) — пользователь вышел, и закрытые
 *  разделы сами покажут приглашение войти (layouts/default.vue). */
export default defineNuxtPlugin({
  name: 'api',
  setup(nuxtApp) {
    const apiBase = useRuntimeConfig().public.apiBase.replace(/\/$/, '')
    const api = createOpenFetch<paths>({
      baseURL: apiBase || undefined,
      credentials: 'include',
      onResponseError({ request, response }) {
        const path = new URL(typeof request === 'string' ? request : request.url, 'http://local').pathname
        if (response.status === 401 && !path.startsWith('/api/auth/')) nuxtApp.runWithContext(() => useAuthStore().expired())
      },
    }, useRequestFetch())                // на сервере (SSR) — запрос с cookie пришедшего запроса

    return {
      provide: { api, apiBase },
    }
  },
})
