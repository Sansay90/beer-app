// Оборудование: иконки видов, значения параметров формой и кратким описанием. Виды и их поля — каталог сервиса
// (service/app/brewery/kinds.py, useEquipmentKinds): у варочной системы параметры — свои поля оборудования (объём,
// эффективность, испарение, котёл), у прочего — props.
import type { Equipment, EquipmentField, EquipmentKindInfo } from '~/types'
import { fmtNumber, SEP } from '~/utils/format'

const ICONS: Record<string, string> = {
  manual: 'i-lucide-cooking-pot', allinone: 'i-lucide-cylinder', easybrew: 'i-lucide-plug', mash_tun: 'i-lucide-box',
  hlt: 'i-lucide-droplets', burner: 'i-lucide-flame', hop_spider: 'i-lucide-hop', mill: 'i-lucide-wheat',
  chiller: 'i-lucide-snowflake', pump: 'i-lucide-waves', fermenter: 'i-lucide-flask-conical', chamber: 'i-lucide-refrigerator',
  glycol: 'i-lucide-thermometer-snowflake', controller: 'i-lucide-gauge', heater: 'i-lucide-heater', sensor: 'i-lucide-radio',
  hydrometer: 'i-lucide-test-tube', refractometer: 'i-lucide-pipette', ph_meter: 'i-lucide-droplet',
  thermometer: 'i-lucide-thermometer', scale: 'i-lucide-weight', stir_plate: 'i-lucide-magnet', flask: 'i-lucide-flask-round',
  keg: 'i-lucide-barrel', co2: 'i-lucide-fire-extinguisher', tap: 'i-lucide-beer', kegerator: 'i-lucide-container',
  filter: 'i-lucide-filter', bottles: 'i-lucide-bottle-wine', other: 'i-lucide-wrench',
}

export function equipmentIcon(kind: string) {
  return ICONS[kind] ?? 'i-lucide-wrench'
}

export type EquipmentValue = number | string | boolean | null
export type EquipmentValues = Record<string, EquipmentValue>
type SystemKey = 'volume' | 'efficiency' | 'evaporation' | 'kettle'

/** Значения параметров оборудования для формы: у системы — её поля, у прочего — props; «да/нет» без значения —
 *  «нет», как у переключателя (иначе включить и выключить — уже «изменено»). */
export function equipmentValues(e: Equipment, kind: EquipmentKindInfo | undefined): EquipmentValues {
  const out: EquipmentValues = {}
  for (const f of kind?.fields ?? []) {
    const v = (kind!.system ? e[f.key as SystemKey] : e.props?.[f.key]) ?? null
    out[f.key] = f.type === 'bool' ? !!v : v
  }
  return out
}

/** Значения по умолчанию для нового оборудования этого вида. */
export function equipmentDefaults(kind: EquipmentKindInfo): EquipmentValues {
  return Object.fromEntries(kind.fields.map(f => [f.key, f.default ?? (f.type === 'bool' ? false : null)]))
}

/** Тело запроса из значений формы: у системы — поля оборудования, у прочего — props. */
export function equipmentBody(kind: EquipmentKindInfo, values: EquipmentValues) {
  if (!kind.system) return { props: values }
  const n = (k: string) => (typeof values[k] === 'number' ? values[k] as number : null)
  return { volume: n('volume'), efficiency: n('efficiency'), evaporation: n('evaporation'), kettle: n('kettle'), props: {} }
}

function factOf(f: EquipmentField, v: EquipmentValue) {
  if (v == null || v === '' || v === false) return null
  if (f.type === 'bool') return f.short ?? f.label
  if (f.type === 'select') return f.options?.find(o => o.value === v)?.label ?? String(v)
  // где бывает минус (погрешность, температура), плюс пишется явно: «погрешность +0,5 °P»
  const n = v as number
  const text = (f.min ?? 0) < 0 && n > 0 ? `+${fmtNumber(n, f.digits ?? 0)}` : fmtNumber(n, f.digits ?? 0)
  return [f.prefix, text, f.unit].filter(Boolean).join(' ')
}

/** Кратко о параметрах: «15 л · 70 % · 2,5 л/ч · котёл 20 л», «32 л · до 1 бар · рубашка». */
export function equipmentFacts(e: Equipment, kind: EquipmentKindInfo | undefined) {
  const values = equipmentValues(e, kind)
  return (kind?.fields ?? []).map(f => factOf(f, values[f.key] ?? null)).filter(Boolean).join(SEP)
}
