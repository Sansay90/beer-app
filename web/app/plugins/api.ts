import createClient from 'openapi-fetch'
import type { paths } from '~/types/bridge'

/** Типизированный клиент посредника: пути, тела запросов и ответы — из OpenAPI-схемы. */
export default defineNuxtPlugin({
  name: 'api',
  setup() {
    const configured = String(useRuntimeConfig().public.bridge || '').replace(/\/$/, '')
    // пусто — тот же хост, что отдал страницу; в dev посредник живёт отдельно на :8000
    const bridgeUrl = configured || (import.meta.dev ? 'http://127.0.0.1:8000' : window.location.origin)

    return {
      provide: {
        api: createClient<paths>({ baseUrl: bridgeUrl }),
        bridgeUrl,
      },
    }
  },
})
