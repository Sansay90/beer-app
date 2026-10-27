/** Ошибку запроса — тостом: нет связи или текст сервиса. errors — error из useFetch / useAsyncData:
 *  их ошибки показываются сами, как у команд. */
export function useErrorToast(...errors: Ref<unknown>[]) {
  const toast = useToast()
  const auth = useAuthStore()

  function show(e: unknown) {
    if (auth.expiredOn && errorStatus(e) === 401) return       // вход истёк — об этом говорит панель входа
    const offline = isOffline(e)
    toast.add({
      title: offline ? 'Нет связи с сервисом' : 'Не получилось',
      description: offline ? 'Попробуйте чуть позже.' : errorText(e),
      color: 'error',
      icon: 'i-lucide-circle-alert',
    })
  }

  for (const error of errors) {
    watch(error, e => e && show(e))
    // ошибка уже есть — пришла с отрисованной на сервере страницей: тост — когда страница оживёт, не во время сверки
    if (import.meta.client && error.value) onNuxtReady(() => show(error.value))
  }
  return show
}

/** Выполнить действие (запрос, изменяющий данные) с индикатором и тостом: успех — коротко, ошибка — текстом сервиса. */
export function useCommand() {
  const toast = useToast()
  const showError = useErrorToast()
  const pending = ref(false)

  async function exec<T>(action: () => Promise<T>, success?: string): Promise<T | undefined> {
    pending.value = true
    try {
      const result = await action()
      if (success) toast.add({ title: success, color: 'success', icon: 'i-lucide-circle-check' })
      return result
    } catch (e) {
      showError(e)
      return undefined
    } finally {
      pending.value = false
    }
  }

  return { exec, pending }
}
