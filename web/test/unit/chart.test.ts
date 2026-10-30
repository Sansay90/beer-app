// Общее у SVG-графиков: шкала с круглыми делениями, место подсказки у точки.
import { describe, expect, it } from 'vitest'
import { axisScale, scaleY, tipPlace } from '~/utils/chart'

describe('шкала графика', () => {
  it('края кратны шагу с запасом, середина тоже кратна, не ниже нуля', () => {
    expect(axisScale([18, 20, 4], { step: 5, margin: 4 })).toEqual({ min: 0, max: 25, ticks: [0, 15, 25] })
    expect(axisScale([66, 78, 100], { step: 10, margin: 8, max: 100 })).toEqual({ min: 50, max: 100, ticks: [50, 80, 100] })
    expect(axisScale([], { step: 5, empty: [0, 30] })).toEqual({ min: 0, max: 30, ticks: [0, 15, 30] })
  })

  it('больше — выше, края шкалы — края панели', () => {
    const y = scaleY({ min: 0, max: 30 }, 20, 150)
    expect([y(30), y(0), y(15)]).toEqual([20, 170, 95])
  })
})

describe('подсказка', () => {
  it('в процентах от размера графика; у краёв прижата внутрь', () => {
    expect(tipPlace(320, 90, 640, 180)).toEqual({ left: '50%', top: '50%', shift: '-50%' })
    expect(tipPlace(64, 0, 640, 180).shift).toBe('-12px')
    expect(tipPlace(600, 0, 640, 180).shift).toBe('calc(-100% + 12px)')
  })
})
