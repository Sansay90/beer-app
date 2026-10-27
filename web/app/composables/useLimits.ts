/** Ограничения пивоварни: шаги, температуры, мощность. Зависят только от модели — при её смене перечитываются;
 *  гостю и без пивоварни сервис отдаёт ограничения по умолчанию. Общие для всех компонентов — по ключу. */
export function useLimits() {
  const brewery = useBreweryStore()
  return useApi('/api/limits', { key: 'limits', watch: [() => brewery.snapshot?.settings.model] })
}
