import type { BrewEvent } from '~/types'

const REPEAT_MS = 4_000            // пока не подтверждено — сигнал почти без перерыва

/** Звук на события варки и напоминание, пока подсказка не подтверждена — на любой странице. */
export default defineNuxtPlugin({
  name: 'notifications',
  dependsOn: ['brewery-stream'],
  setup() {
    const brewery = useBreweryStore()
    const sound = useSound()
    const push = usePush()

    brewery.$onAction(({ name, args }) => {
      if (name !== 'pushEvent') return
      const e = args[0] as BrewEvent
      sound.forEvent(e)
      // подтвердили в приложении — системное уведомление больше не нужно
      if (e.kind === 'added' && e.addition) push.close(`addition-${e.addition.minutes}`)
      else if (e.kind === 'alertCleared') push.close('alert')
    })

    // подсказка пивоварни или закладка хмеля без подтверждения — сигнал повторяется, пока не подтвердят
    let repeat: ReturnType<typeof setInterval> | undefined
    const waiting = computed(() => (brewery.snapshot?.alert ? 'alert' : brewery.snapshot?.additionsPending.length ? 'addition' : null))
    watch(waiting, (kind) => {
      clearInterval(repeat)
      if (kind) repeat = setInterval(() => sound.play(kind), REPEAT_MS)
    })
  },
})
