import { describe, expect, it } from 'vitest'
import type { Addition } from '~/types'
import { ADDITION_KINDS, additionAmount, additionKind, additionName, slotIcon, unitLabel } from '~/utils/additions'

describe('закладки', () => {
  // тип в схеме обязателен, но закладки из старых данных могут прийти без него
  const untyped = { name: 'Saaz', unit: 'g' } as Addition

  it('тип по умолчанию — хмель', () => {
    expect(additionKind(untyped)).toBe(ADDITION_KINDS.hop)
  })

  it('название или тип', () => {
    expect(additionName({ kind: 'fining', name: ' Мох ', unit: 'g' })).toBe('Мох')
    expect(additionName({ kind: 'equipment', name: '  ', unit: 'pcs' })).toBe('Оборудование')
    expect(additionName({ kind: 'spice', unit: 'g' })).toBe('Специи')
  })

  it('количество с единицей; у оборудования количества нет', () => {
    expect(additionAmount({ kind: 'hop', amount: 30, unit: 'g' })).toBe('30 г')
    expect(additionAmount({ kind: 'sugar', amount: 0.25, unit: 'kg' })).toBe('0,25 кг')
    expect(additionAmount({ kind: 'adjunct', amount: 1.234, unit: 'pkg' })).toBe('1,23 пак.')
    expect(additionAmount({ kind: 'equipment', amount: 1, unit: 'pcs' })).toBeNull()
    expect(additionAmount({ kind: 'hop', amount: null, unit: 'g' })).toBeNull()
  })

  it('единица по умолчанию — граммы', () => {
    expect(unitLabel(null)).toBe('г')
    expect(unitLabel('ml')).toBe('мл')
  })

  it('иконка напоминания: один тип — его, разные — общая', () => {
    expect(slotIcon([{ kind: 'hop', unit: 'g' }, untyped])).toBe(ADDITION_KINDS.hop.icon)
    expect(slotIcon([{ kind: 'hop', unit: 'g' }, { kind: 'fining', unit: 'g' }])).toBe('i-lucide-list-plus')
    expect(slotIcon([])).toBe('i-lucide-list-plus')
  })
})
