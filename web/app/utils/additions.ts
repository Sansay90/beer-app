// Закладки: что кладут в затор, кипячение и брожение помимо солода — подписи, иконки, единицы.
// Пивоварня знает только минуты закладок на кипячении (таймер с писком) — что класть, хранит рецепт.
import type { Addition, AdditionKind, AdditionUnit } from '~/types'

export interface AdditionKindMeta {
  label: string
  icon: string
  tint: string               // цвет иконки
  placeholder: string
  measured: boolean          // есть ли количество
}

export const ADDITION_KINDS: Record<AdditionKind, AdditionKindMeta> = {
  hop: { label: 'Хмель', icon: 'i-lucide-hop', tint: 'text-success', placeholder: 'Сорт хмеля', measured: true },
  spice: { label: 'Специи', icon: 'i-lucide-leaf', tint: 'text-orange-500 dark:text-orange-400', placeholder: 'Кориандр, цедра…', measured: true },
  fining: { label: 'Осветлитель', icon: 'i-lucide-sparkles', tint: 'text-info', placeholder: 'Ирландский мох, Brewtan B…', measured: true },
  water: { label: 'Соли', icon: 'i-lucide-droplet', tint: 'text-sky-500 dark:text-sky-400', placeholder: 'CaCl₂, гипс, молочная кислота…', measured: true },
  adjunct: { label: 'Добавка', icon: 'i-lucide-flask-conical', tint: 'text-violet-500 dark:text-violet-400', placeholder: 'Питание дрожжей, лактоза…', measured: true },
  sugar: { label: 'Сахар', icon: 'i-lucide-candy', tint: 'text-amber-500 dark:text-amber-400', placeholder: 'Декстроза, инвертный сироп…', measured: true },
  equipment: { label: 'Оборудование', icon: 'i-lucide-wrench', tint: 'text-muted', placeholder: 'Чиллер', measured: false },
}

/** Типы в таблице «Другое»: хмель и сахар — в своих таблицах, соли — в разделе «Вода». */
export const MISC_KINDS = ['spice', 'fining', 'adjunct', 'equipment'] as const satisfies AdditionKind[]

export const ADDITION_UNITS: { value: AdditionUnit; label: string }[] = [
  { value: 'g', label: 'г' },
  { value: 'kg', label: 'кг' },
  { value: 'ml', label: 'мл' },
  { value: 'pcs', label: 'шт' },
  { value: 'pkg', label: 'пак.' },
]

type Item = Pick<Addition, 'kind' | 'name' | 'amount' | 'unit'>

export function additionKind(a: Item) {
  return ADDITION_KINDS[a.kind ?? 'hop']
}

/** Название или, если не задано, тип: «Hallertau», «Оборудование». */
export function additionName(a: Item) {
  return a.name?.trim() || additionKind(a).label
}

export function unitLabel(unit: AdditionUnit | null | undefined) {
  return ADDITION_UNITS.find(u => u.value === (unit ?? 'g'))!.label
}

/** «30 г», «1 шт»; null — количества нет. */
export function additionAmount(a: Item) {
  if (!a.amount || !additionKind(a).measured) return null
  return `${a.amount.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${unitLabel(a.unit)}`
}

/** Иконка напоминания: тип, если всё по нему одного типа, иначе общая. */
export function slotIcon(items: Item[]) {
  const kinds = new Set(items.map(a => a.kind ?? 'hop'))
  return kinds.size === 1 ? ADDITION_KINDS[[...kinds][0]!].icon : 'i-lucide-list-plus'
}
