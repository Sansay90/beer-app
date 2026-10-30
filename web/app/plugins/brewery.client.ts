import type { BrewEvent, Snapshot } from '~/types'

/** Поток SSE сервиса: состояние и события пивоварни → стор пивоварни, «варка изменилась» → useBrewChanged,
 *  «новое уведомление» → счётчик непрочитанных. Открыт, пока пользователь вошёл; EventSource переподключается сам. */
export default defineNuxtPlugin({
  name: 'brewery-stream',
  dependsOn: ['api'],
  setup(nuxtApp) {
    const brewery = useBreweryStore()
    const auth = useAuthStore()
    const changed = useBrewChanged()
    const notices = useNotifications()
    let source: EventSource | null = null

    function open() {
      source = new EventSource(`${nuxtApp.$apiBase}/api/stream`, { withCredentials: true })
      source.addEventListener('open', () => {
        brewery.setConnected(true)
        brewery.resync()                     // догнать то, что пропустили, пока связи не было
      })
      source.addEventListener('error', () => brewery.setConnected(false))
      source.addEventListener('state', e => brewery.applySnapshot(JSON.parse((e as MessageEvent).data) as Snapshot))
      source.addEventListener('event', e => brewery.pushEvent(JSON.parse((e as MessageEvent).data) as BrewEvent))
      source.addEventListener('brew', (e) => {
        const { id } = JSON.parse((e as MessageEvent).data) as { id: string }
        changed.value = { id, seq: (changed.value?.seq ?? 0) + 1 }
      })
      source.addEventListener('notice', () => notices.refresh())
    }

    function close() {
      source?.close()
      source = null
      brewery.setConnected(false)
    }

    // поток — когда страница ожила: отрисованное на сервере сверяется с состоянием «ещё без связи»
    onNuxtReady(() => watch(() => auth.user?.id, (id) => {
      close()
      if (id) open()
    }, { immediate: true }))

    if (import.meta.hot) import.meta.hot.dispose(close)
  },
})
