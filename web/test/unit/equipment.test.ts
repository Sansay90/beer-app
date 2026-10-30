// Оборудование: значения формы, тело запроса и краткое описание — по каталогу вида.
import { describe, expect, it } from 'vitest'
import type { Equipment, EquipmentKindInfo } from '~/types'
import { equipmentBody, equipmentDefaults, equipmentFacts, equipmentIcon, equipmentValues } from '~/utils/equipment'
import { dots } from './fixtures'

const POT: EquipmentKindInfo = {
  id: 'manual', label: 'Кастрюля или котёл', hint: '', system: true,
  fields: [
    { key: 'volume', label: 'Объём партии', type: 'number', unit: 'л', digits: 1 },
    { key: 'efficiency', label: 'Эффективность', type: 'number', unit: '%', default: 75 },
    { key: 'evaporation', label: 'Испарение', type: 'number', unit: 'л/ч', digits: 1, default: 3 },
    { key: 'kettle', label: 'Объём котла', type: 'number', unit: 'л', digits: 1, prefix: 'котёл' },
  ],
}
const TANK: EquipmentKindInfo = {
  id: 'fermenter', label: 'Ферментер', hint: '', system: false,
  fields: [
    { key: 'volume', label: 'Объём', type: 'number', unit: 'л', digits: 1 },
    { key: 'pressure', label: 'Давление', type: 'number', unit: 'бар', digits: 1, prefix: 'до' },
    { key: 'cooling', label: 'Охлаждение', type: 'select', options: [{ value: 'jacket', label: 'рубашка' }] },
  ],
}
const ATC: EquipmentKindInfo = { id: 'refractometer', label: 'Рефрактометр', hint: '', system: false, fields: [{ key: 'atc', label: 'Термокомпенсация (ATC)', type: 'bool', short: 'ATC' }] }
const item = (over: Partial<Equipment>): Equipment => ({
  id: 'e1', name: 'X', kind: 'manual', category: 'brew', system: true, connected: false, controlled: false, main: false, props: {}, ...over,
})

describe('оборудование', () => {
  it('система — свои поля, прочее — props', () => {
    const pot = item({ volume: 15, efficiency: 70, evaporation: 2.5, kettle: 20 })
    expect(equipmentValues(pot, POT)).toEqual({ volume: 15, efficiency: 70, evaporation: 2.5, kettle: 20 })
    expect(equipmentFacts(pot, POT)).toBe(dots('15 л · 70 % · 2,5 л/ч · котёл 20 л'))
    const tank = item({ kind: 'fermenter', system: false, props: { volume: 32, pressure: 1, cooling: 'jacket' } })
    expect(equipmentFacts(tank, TANK)).toBe(dots('32 л · до 1 бар · рубашка'))
    expect(equipmentFacts(item({ kind: 'refractometer', system: false, props: { atc: true } }), ATC)).toBe('ATC')
    expect(equipmentFacts(item({ kind: 'refractometer', system: false }), ATC)).toBe('')
    expect(equipmentValues(item({ kind: 'refractometer', system: false }), ATC)).toEqual({ atc: false })   // как у переключателя
    const HYDRO: EquipmentKindInfo = { id: 'hydrometer', label: 'Ареометр', hint: '', system: false, fields: [{ key: 'offset', label: 'Погрешность', type: 'number', unit: '°P', min: -5, digits: 1, prefix: 'погрешность' }] }
    expect(['+0,5', '-0,3'].map((_, i) => equipmentFacts(item({ kind: 'hydrometer', system: false, props: { offset: [0.5, -0.3][i]! } }), HYDRO)))
      .toEqual(['погрешность +0,5 °P', 'погрешность -0,3 °P'])
  })

  it('новое — со средними; тело запроса — по виду', () => {
    expect(equipmentDefaults(POT)).toEqual({ volume: null, efficiency: 75, evaporation: 3, kettle: null })
    expect(equipmentDefaults(ATC)).toEqual({ atc: false })
    expect(equipmentBody(POT, { volume: 30, efficiency: 83, evaporation: 3, kettle: null }))
      .toEqual({ volume: 30, efficiency: 83, evaporation: 3, kettle: null, props: {} })
    expect(equipmentBody(TANK, { volume: 32 })).toEqual({ props: { volume: 32 } })
    expect([equipmentIcon('keg'), equipmentIcon('нет такого')]).toEqual(['i-lucide-barrel', 'i-lucide-wrench'])
  })
})
