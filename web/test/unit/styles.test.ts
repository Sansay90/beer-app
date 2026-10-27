import { describe, expect, it } from 'vitest'
import { rangePosition, styleByCode, styleLabel, STYLES } from '~/utils/styles'

describe('стили BJCP', () => {
  it('справочник загружен, стиль ищется по коду', () => {
    expect(STYLES.length).toBeGreaterThan(100)
    expect(styleByCode('5B')?.name).toBe('Kölsch')
    expect(styleByCode('нет такого')).toBeNull()
    expect(styleByCode(null)).toBeNull()
  })

  it('положение относительно рамок', () => {
    expect(rangePosition(1.04, [1.044, 1.05])).toBe('low')
    expect(rangePosition(1.047, [1.044, 1.05])).toBe('in')
    expect(rangePosition(1.05, [1.044, 1.05])).toBe('in')
    expect(rangePosition(1.06, [1.044, 1.05])).toBe('high')
    expect(rangePosition(null, [1.044, 1.05])).toBeNull()
    expect(rangePosition(1.05, null)).toBeNull()
  })

  it('подпись стиля', () => {
    expect(styleLabel({ code: '5B', name: 'Kölsch' })).toBe('5B · Kölsch')
    expect(styleLabel({ code: null, name: ' хмельной лагер ' })).toBe('Авторский: хмельной лагер')
    expect(styleLabel({ name: '' })).toBe('Авторский рецепт')
    expect(styleLabel(null)).toBe('Стиль не выбран')
  })
})
