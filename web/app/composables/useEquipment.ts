import type { EquipmentKindInfo } from '~/types'

/** Оборудование того, кто вошёл: list — всё, основное первым; systems — варочные системы (на них варят);
 *  data — основная система: объём и эффективность для новых рецептов, испарение для расчёта воды (нет — null).
 *  Гостю — пусто. Общее для всех компонентов — по ключу; после правки — refresh(). */
export function useEquipment() {
  const { $api } = useNuxtApp()
  const auth = useAuthStore()
  const res = useAsyncData('equipment', () => (auth.user ? $api('/api/equipment') : Promise.resolve([])), {
    watch: [() => auth.user?.id],
    default: () => [],
  })
  const main = computed(() => res.data.value.find(e => e.main) ?? null)
  const systems = computed(() => res.data.value.filter(e => e.system))
  return { list: res.data, systems, data: main, status: res.status, error: res.error, refresh: res.refresh }
}

/** Каталог оборудования с сервиса: группы, виды и их параметры (service/app/brewery/kinds.py). Один на сайт.
 *  kindOf — вид оборудования; вида уже нет в каталоге — «Другое» (так его показывает и сервис). */
export function useEquipmentKinds() {
  const { $api } = useNuxtApp()
  const res = useAsyncData('equipment-kinds', () => $api('/api/equipment/kinds'), { default: () => [] })
  const kinds = computed(() => new Map<string, EquipmentKindInfo>(res.data.value.flatMap(c => c.kinds.map(k => [k.id, k] as const))))
  const categoryLabel = computed(() => new Map(res.data.value.map(c => [c.id, c.label] as const)))
  const kindOf = (id: string) => kinds.value.get(id) ?? kinds.value.get('other')
  return { categories: res.data, kinds, kindOf, categoryLabel, status: res.status, error: res.error, refresh: res.refresh }
}
