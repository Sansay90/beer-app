import type { BrewEvent, Snapshot } from '~/types'

/** Поток SSE сервиса → стор пивоварни: открыт, пока пользователь вошёл. EventSource переподключается сам. */
export default defineNuxtPlugin({
  name: 'brewery-stream',
  dependsOn: ['api'],
  setup(nuxtApp) {
    const brewery = useBreweryStore()
    const auth = useAuthStore()
    let source: EventSource | null = null

    function open() {
      source = new EventSource(`${nuxtApp.$bridgeUrl}/api/stream`, { withCredentials: true })
      source.addEventListener('open', () => {
        brewery.setConnected(true)
        brewery.resync()                     // догнать то, что пропустили, пока связи не было
      })
      source.addEventListener('error', () => brewery.setConnected(false))
      source.addEventListener('state', e => brewery.applySnapshot(JSON.parse((e as MessageEvent).data) as Snapshot))
      source.addEventListener('event', e => brewery.pushEvent(JSON.parse((e as MessageEvent).data) as BrewEvent))
    }

    function close() {
      source?.close()
      source = null
      brewery.setConnected(false)
    }

    watch(() => auth.user?.id, (id) => {
      close()
      if (id) open()
    }, { immediate: true })

    if (import.meta.hot) import.meta.hot.dispose(close)
  },
})
