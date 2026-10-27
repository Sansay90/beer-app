/** Профиль оборудования того, кто вошёл: эффективность для новых рецептов, испарение для расчёта воды.
 *  Гостю — null. Общий для всех компонентов — по ключу; после сохранения data присваивается ответом сервиса. */
export function useEquipment() {
  const { $api } = useNuxtApp()
  const auth = useAuthStore()
  return useAsyncData('equipment', () => (auth.user ? $api('/api/equipment') : Promise.resolve(null)), {
    watch: [() => auth.user?.id],
  })
}
