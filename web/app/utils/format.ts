/** Число по-русски, с единицей: fmtNumber(5.25, 2, ' кг') → «5,25 кг»; нет значения — «—». */
export function fmtNumber(v: number | null | undefined, digits = 0, unit = '') {
  return v == null ? '—' : `${v.toLocaleString('ru-RU', { maximumFractionDigits: digits })}${unit}`
}

/** Ровно digits знаков после запятой: fixed(65, 1) → «65,0». */
function fixed(v: number, digits: number) {
  return v.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

/** Температура: 65 → «65,0». */
export function fmtTemp(t: number | null | undefined, digits = 1) {
  return t == null ? '—' : fixed(t, digits)
}

/** 3725 → «1:02:05», 125 → «2:05». */
export function fmtDuration(sec: number | null | undefined) {
  if (sec == null) return '—'
  const s = Math.max(0, Math.round(sec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

/** Слово по числу: plural(3, 'шаг', 'шага', 'шагов') → «шага». */
export function plural(n: number, one: string, few: string, many: string) {
  const m10 = n % 10
  const m100 = n % 100
  if (m10 === 1 && m100 !== 11) return one
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few
  return many
}

/** Минуты → «1 ч 10 мин» / «45 мин». */
export function fmtMinutes(min: number) {
  const h = Math.floor(min / 60)
  const m = min % 60
  if (!h) return `${m} мин`
  return m ? `${h} ч ${m} мин` : `${h} ч`
}

export function fmtClock(epoch: number) {
  return new Date(epoch * 1000).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function fmtWatts(w: number | null | undefined) {
  return w == null ? '—' : `${w} W`
}

/** Вт·ч → «850 Вт·ч» / «2,35 кВт·ч». */
export function fmtEnergy(wh: number | null | undefined) {
  if (wh == null) return '—'
  return wh < 1000 ? `${Math.round(wh)} Вт·ч` : `${fixed(wh / 1000, 2)} кВт·ч`
}
