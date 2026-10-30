/** Партия, у которой идёт варочный день: её страница и есть «Варка» в меню, туда же ведёт главная. Общее для всех
 *  компонентов — по ключу; меню освежает его при переходах и когда варка изменилась на сервисе (useBrewChanged).
 *  Гостю и без идущей партии — null. */
export function useCurrentBrew() {
  const { $api } = useNuxtApp()
  const auth = useAuthStore()
  const res = useAsyncData('current-brew', async () => (auth.user
    ? (await $api('/api/brews', { query: { phase: 'brewday', limit: 1 } }))[0] ?? null
    : null), { watch: [() => auth.user?.id], default: () => null })
  return { brew: res.data, status: res.status, refresh: res.refresh }
}

/** Последняя варка, изменившаяся на сервисе (поток SSE, `brew`): пивоварня начала или закончила варку, сменила шаг,
 *  варочный день закрылся сам. seq растёт с каждым сообщением — следить через watch. */
export function useBrewChanged() {
  return useState<{ id: string; seq: number } | null>('brew-changed', () => null)
}
