// Графики. SVG (профиль программы и брожения рецепта, брожение партии): шкала с круглыми делениями и место
// подсказки у точки — сетка и сама подсказка в компонентах ChartGrid и ChartTip. uPlot (температура варки):
// цвета темы для canvas.

/** CSS-переменная цвета (oklch и т. п.) → rgba(): canvas понимает не все форматы. Только в браузере. */
export function cssColor(cssVar: string, alpha = 1) {
  const probe = document.createElement('span')
  probe.style.color = `var(${cssVar})`
  document.body.appendChild(probe)
  const color = getComputedStyle(probe).color
  probe.remove()
  const ctx = document.createElement('canvas').getContext('2d')!
  ctx.fillStyle = color
  ctx.fillRect(0, 0, 1, 1)
  const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export interface AxisScale {
  min: number
  max: number
  ticks: number[]            // края и середина, кратные шагу
}

/** Шкала по значениям: от наименьшего − margin до наибольшего + margin, края кратны step, не ниже нуля; max —
 *  верхний край задан (кипячение — 100 °C); значений нет — empty. */
export function axisScale(values: number[], o: { step: number; margin?: number; max?: number; empty?: [number, number] }): AxisScale {
  const margin = o.margin ?? o.step
  const [lo0, hi0] = o.empty ?? [0, o.step]
  const min = values.length ? Math.max(0, Math.floor((Math.min(...values) - margin) / o.step) * o.step) : lo0
  const max = o.max ?? (values.length ? Math.ceil((Math.max(...values) + margin) / o.step) * o.step : hi0)
  const mid = Math.round((min + max) / 2 / o.step) * o.step
  return { min, max, ticks: [...new Set([min, mid, max])] }
}

/** Значение → y в SVG: шкала s на панели от top высотой height (больше — выше). */
export function scaleY(s: Pick<AxisScale, 'min' | 'max'>, top: number, height: number) {
  return (v: number) => top + ((s.max - v) / (s.max - s.min || 1)) * height
}

export interface TipPlace {
  left: string
  top: string
  shift: string              // сдвиг по горизонтали: у краёв подсказка прижимается внутрь графика
}

/** Где подсказка у точки (x, y) графика с viewBox w × h: в процентах — график тянется по ширине. */
export function tipPlace(x: number, y: number, w: number, h: number): TipPlace {
  const rx = x / w
  return {
    left: `${rx * 100}%`,
    top: `${(y / h) * 100}%`,
    shift: rx < 0.25 ? '-12px' : rx > 0.75 ? 'calc(-100% + 12px)' : '-50%',
  }
}
