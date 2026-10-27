// Пивные величины: плотность (хранится в SG, показывается в °P или SG), крепость, цвет по EBC.

export type GravityUnit = 'plato' | 'sg'

export function platoFromSg(sg: number) {
  return -616.868 + 1111.14 * sg - 630.272 * sg ** 2 + 135.997 * sg ** 3
}

export function sgFromPlato(p: number) {
  return 1 + p / (258.6 - (p / 258.2) * 227.1)
}

/** Плотность в единицах человека: 12.0 (°P) или 1.048 (SG). */
export function gravityIn(sg: number, unit: GravityUnit) {
  return unit === 'plato' ? Math.round(platoFromSg(sg) * 10) / 10 : Math.round(sg * 1000) / 1000
}

export function fmtGravity(sg: number | null | undefined, unit: GravityUnit) {
  if (sg == null) return '—'
  const digits = unit === 'plato' ? 1 : 3
  const text = gravityIn(sg, unit).toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })
  return unit === 'plato' ? `${text} °P` : text
}

/** Крепость по начальной и конечной плотности, % об. */
export function abvOf(og: number | null | undefined, fg: number | null | undefined) {
  if (!og || !fg || fg >= og) return null
  return ((76.08 * (og - fg)) / (1.775 - og)) * (fg / 0.794)
}

// Цвет пива в бокале по EBC — опорные точки, между ними линейно. Для отображения, не для расчётов.
// Таблицы SRM обычно сняты в тонком слое: тёмное пиво по ним красно-коричневое, а в бокале оно
// уже с ~50 EBC почти чёрное — поэтому шкала своя.
const EBC_STOPS: [number, string][] = [
  [2, '#F8EAA2'], [4, '#F6E07A'], [6, '#F2D04E'], [8, '#EDC03A'], [12, '#E2A42C'], [16, '#D58A26'], [20, '#C77423'],
  [26, '#B4561A'], [33, '#923F16'], [40, '#692B12'], [47, '#3D1C0F'], [57, '#1F100B'], [69, '#120A07'], [80, '#0A0605'],
]

const rgb = (hex: string) => [1, 3, 5].map(i => Number.parseInt(hex.slice(i, i + 2), 16))
const hex = (c: number[]) => `#${c.map(v => Math.round(v).toString(16).padStart(2, '0')).join('')}`

/** «#C77423» по EBC; null — цвет не задан. */
export function beerColor(ebc: number | null | undefined) {
  if (ebc == null) return null
  const i = EBC_STOPS.findIndex(([e]) => e >= ebc)
  if (i <= 0) return EBC_STOPS[i === 0 ? 0 : EBC_STOPS.length - 1]![1]
  const [e0, c0] = EBC_STOPS[i - 1]!, [e1, c1] = EBC_STOPS[i]!
  const k = (ebc - e0) / (e1 - e0)
  const a = rgb(c0), b = rgb(c1)
  return hex(a.map((v, n) => v + (b[n]! - v) * k))
}

/** CSS-градиент цвета пива слева направо от from до to EBC — для шкал. */
export function ebcGradient(from: number, to: number) {
  if (to <= from) return beerColor(from)!
  const points = [from, ...EBC_STOPS.map(([e]) => e).filter(e => e > from && e < to), to]
  return `linear-gradient(to right, ${points.map(e => `${beerColor(e)} ${(((e - from) / (to - from)) * 100).toFixed(1)}%`).join(', ')})`
}
