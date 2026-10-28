/** Уведомления на сайте: сколько непрочитанных — метка у пункта меню; отметить все прочитанными.
 *  Число общее для страницы (useState): меню его показывает, страница уведомлений обнуляет. */
export function useNotifications() {
  const { $api } = useNuxtApp()
  const auth = useAuthStore()
  const unread = useState('notifications:unread', () => 0)

  async function refresh() {
    if (!auth.user) {
      unread.value = 0
      return
    }
    try {
      unread.value = (await $api('/api/notifications/unread')).count
    } catch {
      // нет связи — метка обновится в следующий раз
    }
  }

  async function readAll() {
    await $api('/api/notifications/read', { method: 'POST', body: {} })
    unread.value = 0
  }

  return { unread, refresh, readAll }
}
