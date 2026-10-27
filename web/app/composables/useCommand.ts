/** Выполнить действие стора с индикатором и тостом: успех — коротко, ошибка — текстом посредника. */
export function useCommand() {
  const toast = useToast()
  const pending = ref(false)

  async function exec<T>(action: () => Promise<T>, success?: string): Promise<T | undefined> {
    pending.value = true
    try {
      const result = await action()
      if (success) toast.add({ title: success, color: 'success', icon: 'i-lucide-circle-check' })
      return result
    } catch (e) {
      const offline = e instanceof TypeError                       // fetch не достучался до посредника
      toast.add({
        title: offline ? 'Нет связи с посредником' : 'Не получилось',
        description: offline ? 'Проверьте, что он запущен.' : e instanceof Error ? e.message : String(e),
        color: 'error',
        icon: 'i-lucide-circle-alert',
      })
      return undefined
    } finally {
      pending.value = false
    }
  }

  return { exec, pending }
}
