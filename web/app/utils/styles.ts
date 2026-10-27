// Стили BJCP 2021 и их рамки (data/bjcp-2021.json, генерирует scripts/bjcp.py).
import data from '~/data/bjcp-2021.json'

type Span = [number, number] | null

export interface BjcpStyle {
  code: string
  name: string
  category: string
  og: Span
  fg: Span
  ibu: Span
  ebc: Span
  abv: Span
}

export const STYLES = data as BjcpStyle[]
const BY_CODE = new Map(STYLES.map(s => [s.code, s]))

export function styleByCode(code: string | null | undefined) {
  return code ? BY_CODE.get(code) ?? null : null
}

/** Где значение относительно рамок стиля: ниже, в рамках, выше; null — сравнивать не с чем. */
export function rangePosition(value: number | null | undefined, span: Span) {
  if (value == null || !span) return null
  return value < span[0] ? 'low' : value > span[1] ? 'high' : 'in'
}

/** «5B · Kölsch», «Авторский: хмельной лагер», «Авторский рецепт»; стиль не задан — «Стиль не выбран». */
export function styleLabel(style: { code?: string | null; name: string } | null | undefined) {
  if (!style) return 'Стиль не выбран'
  if (style.code) return `${style.code} · ${style.name}`
  return style.name.trim() ? `Авторский: ${style.name.trim()}` : 'Авторский рецепт'
}
