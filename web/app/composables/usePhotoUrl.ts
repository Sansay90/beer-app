/** Адрес фото пива: thumb — превью до 480 px для лент и карточек. Без apiBase — /api того же сайта. */
export function usePhotoUrl() {
  const { $apiBase } = useNuxtApp()
  return (pid: string, thumb = false) => `${$apiBase}/api/photos/${pid}${thumb ? '?thumb=true' : ''}`
}
