import type { GravityUnit } from '~/utils/beer'

/** Настройки этого устройства (не пивоварни): живут в localStorage браузера. */
export const usePreferencesStore = defineStore('preferences', () => {
  const sound = useLocalStorage('brewapp.sound', false)
  const gravityUnit = useLocalStorage<GravityUnit>('brewapp.gravityUnit', 'plato')
  return { sound, gravityUnit }
})
