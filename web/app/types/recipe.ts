// Модель формы редактора рецепта: все поля на месте (необязательные — null), строки — не null.
import type {
  Batch, Boil, Fermentable, FermentationStep, Hop, MashStep, Misc, StyleRef, WaterAddition, WaterProfile, Yeast,
} from '~/types'

type Row<T> = Required<T>

export type FermentableRow = Row<Fermentable>
export type HopRow = Row<Hop>
export type MiscRow = Row<Misc>
export type YeastRow = Row<Yeast>
export type MashRow = Row<MashStep> & { name: string }
export type FermentationRow = Row<FermentationStep> & { name: string }
export type WaterAdditionRow = Row<WaterAddition>

export interface WaterDraft {
  ratio: number | null                  // гидромодуль, л/кг; литры считаются (utils/water.ts)
  source: Row<WaterProfile>
  additions: WaterAdditionRow[]
}

export interface RecipeDraft {
  name: string
  style: StyleRef | null
  batch: Row<Omit<Batch, 'evaporation'>>   // испарение — у рецепта партии, не у рецепта; показатели (OG, IBU…) не хранятся в форме — считаются (utils/calc.ts)
  fermentables: FermentableRow[]
  hops: HopRow[]
  miscs: MiscRow[]
  yeasts: YeastRow[]
  water: WaterDraft
  mash: MashRow[]
  boil: Boil | null
  fermentation: FermentationRow[]
  notes: string
}

/** Вариант типа строки для KindButton: иконка, подпись, цвет иконки. */
export interface KindOption<V extends string = string> {
  value: V
  label: string
  icon: string
  tint?: string
}
