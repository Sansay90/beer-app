export function fmtTemp(t: number | null | undefined, digits = 1) {
  return t == null ? '—' : t.toFixed(digits)
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

/** Вт·ч → «850 Вт·ч» / «2.35 кВт·ч». */
export function fmtEnergy(wh: number | null | undefined) {
  if (wh == null) return '—'
  return wh < 1000 ? `${Math.round(wh)} Вт·ч` : `${(wh / 1000).toFixed(2)} кВт·ч`
}
