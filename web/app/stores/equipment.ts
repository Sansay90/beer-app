import type { Equipment } from '~/types'

/** Профиль оборудования пивоварни: эффективность для новых рецептов, испарение для расчёта воды. */
export const useEquipmentStore = defineStore('equipment', () => {
  const { $api } = useNuxtApp()
  const value = ref<Equipment | null>(null)

  async function fetch() {
    value.value = unwrap(await $api.GET('/api/equipment'))
    return value.value
  }

  async function save(e: Equipment) {
    value.value = unwrap(await $api.PUT('/api/equipment', { body: e }))
    return value.value
  }

  return { value, fetch, save }
})
