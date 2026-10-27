// Тексты для превью ссылок и поисковиков (useSeoMeta): одной строкой, без разметки.
import type { StyleRef } from '~/types'
import { fmtGravity } from '~/utils/beer'
import type { RecipeCalc } from '~/utils/calc'
import { fmtNumber } from '~/utils/format'
import { styleLabel } from '~/utils/styles'

/** Длина описания: дальше поисковики и мессенджеры всё равно обрежут. */
export const DESCRIPTION_MAX = 200

/** Обрезать по слову, с многоточием. */
export function clip(text: string, max = DESCRIPTION_MAX) {
  if (text.length <= max) return text
  const cut = text.slice(0, max - 1)
  return `${cut.slice(0, Math.max(cut.lastIndexOf(' '), max / 2)).replace(/[\s.,;:—-]+$/, '')}…`
}

/** «26B · Belgian Dubbel · 16,4 °P · 19 IBU · 7,2 % ABV. Тёмно-янтарный…» — стиль, цифры и первый абзац описания. */
export function recipeDescription(r: { style?: StyleRef | null; notes?: string }, c: Pick<RecipeCalc, 'og' | 'ibu' | 'abv'> | null) {
  const facts = [
    r.style && styleLabel(r.style),
    c?.og != null && fmtGravity(c.og, 'plato'),
    c?.ibu != null && `${fmtNumber(c.ibu)} IBU`,
    c?.abv != null && `${fmtNumber(c.abv, 1)} % ABV`,
  ].filter(Boolean).join(' · ')
  const about = r.notes?.split(/\n\s*\n/)[0]?.replace(/\s+/g, ' ').trim()
  return clip([facts, about].filter(Boolean).join('. '))
}
