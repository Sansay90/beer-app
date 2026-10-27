import type { BrewEvent, Snapshot } from '~/types'

/** Поток SSE посредника → стор пивоварни. EventSource переподключается сам. */
export default defineNuxtPlugin({
  name: 'brewery-stream',
  dependsOn: ['api'],
  setup(nuxtApp) {
    const brewery = useBreweryStore()
    const source = new EventSource(`${nuxtApp.$bridgeUrl}/api/stream`)

    source.addEventListener('open', () => {
      brewery.setConnected(true)
      brewery.resync()                       // догнать то, что пропустили, пока связи не было
    })
    source.addEventListener('error', () => brewery.setConnected(false))
    source.addEventListener('state', e => brewery.applySnapshot(JSON.parse((e as MessageEvent).data) as Snapshot))
    source.addEventListener('event', e => brewery.pushEvent(JSON.parse((e as MessageEvent).data) as BrewEvent))

    if (import.meta.hot) import.meta.hot.dispose(() => source.close())
  },
})
