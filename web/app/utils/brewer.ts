/** Страница пивовара по нику; ник бывает русским — в адресе он кодируется. */
export const brewerPath = (nick: string) => `/brewers/${encodeURIComponent(nick)}`

/** Ник необязателен: без него под рецептами — «Неизвестный пивовар», страницы у такого нет. */
export const UNKNOWN_BREWER = 'Неизвестный пивовар'
export const brewerName = (who: { name?: string | null }) => who.name || UNKNOWN_BREWER
