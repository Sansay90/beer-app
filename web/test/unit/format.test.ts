import { describe, expect, it } from 'vitest'
import { fmtClock, fmtDuration, fmtEnergy, fmtMinutes, fmtNumber, fmtTemp, fmtWatts, plural } from '~/utils/format'

describe('форматирование', () => {
  it('число по-русски', () => {
    expect(fmtNumber(5.256, 2, ' кг')).toBe('5,26 кг')
    expect(fmtNumber(1234.5)).toBe('1\u00A0235')       // разряды — неразрывным пробелом
    expect(fmtNumber(0, 1, ' л')).toBe('0 л')
    expect(fmtNumber(null, 1, ' л')).toBe('—')
  })

  it('температура', () => {
    expect(fmtTemp(66)).toBe('66,0')                 // дробная часть — через запятую, как везде в интерфейсе
    expect(fmtTemp(65.97, 0)).toBe('66')
    expect(fmtTemp(null)).toBe('—')
  })

  it('длительность', () => {
    expect(fmtDuration(3725)).toBe('1:02:05')
    expect(fmtDuration(125)).toBe('2:05')
    expect(fmtDuration(59.6)).toBe('1:00')
    expect(fmtDuration(-5)).toBe('0:00')
    expect(fmtDuration(null)).toBe('—')
  })

  it('минуты', () => {
    expect(fmtMinutes(45)).toBe('45 мин')
    expect(fmtMinutes(60)).toBe('1 ч')
    expect(fmtMinutes(70)).toBe('1 ч 10 мин')
  })

  it('время суток', () => {
    expect(fmtClock(0)).toMatch(/^\d{2}:\d{2}:\d{2}$/)
  })

  it('мощность и энергия', () => {
    expect(fmtWatts(2500)).toBe('2500 W')
    expect(fmtWatts(undefined)).toBe('—')
    expect(fmtEnergy(849.6)).toBe('850 Вт·ч')
    expect(fmtEnergy(2350)).toBe('2,35 кВт·ч')
    expect(fmtEnergy(null)).toBe('—')
  })

  it.each([
    [0, 'шагов'], [1, 'шаг'], [2, 'шага'], [4, 'шага'], [5, 'шагов'], [11, 'шагов'], [12, 'шагов'], [14, 'шагов'],
    [21, 'шаг'], [22, 'шага'], [111, 'шагов'], [101, 'шаг'],
  ])('%i %s', (n, word) => {
    expect(plural(n, 'шаг', 'шага', 'шагов')).toBe(word)
  })
})
