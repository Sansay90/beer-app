/** Оборудование того, кто вошёл: list — всё, основное первым; data — основное: объём и эффективность для новых
 *  рецептов, испарение для расчёта воды (нет оборудования — null). Гостю — пусто. Общее для всех компонентов —
 *  по ключу; после правки — refresh(). */
export function useEquipment() {
  const { $api } = useNuxtApp()
  const auth = useAuthStore()
  const res = useAsyncData('equipment', () => (auth.user ? $api('/api/equipment') : Promise.resolve([])), {
    watch: [() => auth.user?.id],
    default: () => [],
  })
  const main = computed(() => res.data.value.find(e => e.main) ?? null)
  return { list: res.data, data: main, status: res.status, error: res.error, refresh: res.refresh }
}
