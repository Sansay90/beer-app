import { describe, expect, it } from 'vitest'
import { clip, DESCRIPTION_MAX, recipeDescription } from '~/utils/seo'
import { dots } from './fixtures'

describe('тексты для превью', () => {
  it('короткое — как есть, длинное — по слову и с многоточием', () => {
    expect(clip('Светлый лагер')).toBe('Светлый лагер')
    const long = 'слово '.repeat(60).trim()
    const cut = clip(long)
    expect(cut.length).toBeLessThanOrEqual(DESCRIPTION_MAX)
    expect(cut.endsWith('слово…')).toBe(true)
  })

  it('описание рецепта: стиль, цифры и первый абзац', () => {
    const r = { style: { code: '5B', name: 'Kölsch' }, notes: 'Светлый, сухой,\nс тонким фруктовым тоном.\n\nВторой абзац не нужен.' }
    expect(recipeDescription(r, { og: 1.0484, ibu: 24.6, abv: 4.83 }))
      .toBe(dots('5B · Kölsch · 12,0 °P · 25 IBU · 4,8 % ABV. Светлый, сухой, с тонким фруктовым тоном.'))
  })

  it('без стиля, цифр и описания — что есть', () => {
    expect(recipeDescription({ style: null, notes: '' }, { og: null, ibu: null, abv: null })).toBe('')
    expect(recipeDescription({ notes: 'Только описание.' }, null)).toBe('Только описание.')
  })
})
