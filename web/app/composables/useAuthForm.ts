import type { FormError } from '@nuxt/ui'

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
export const PASSWORD_MIN = 8

/** Форма входа: ошибка — текстом над кнопкой, а не всплывающим сообщением, чтобы её было видно при исправлении. */
export function useAuthForm() {
  const pending = ref(false)
  const error = ref('')

  async function run(action: () => Promise<unknown>) {
    pending.value = true
    error.value = ''
    try {
      await action()
      return true
    } catch (e) {
      const text = isOffline(e) ? 'нет связи с сервисом' : errorText(e)
      error.value = text.charAt(0).toUpperCase() + text.slice(1)
      return false
    } finally {
      pending.value = false
    }
  }

  return { pending, error, run }
}

export function checkEmail(email: string): FormError[] {
  return EMAIL.test(email.trim()) ? [] : [{ name: 'email', message: 'Похоже, в адресе ошибка' }]
}

export function checkNewPassword(password: string): FormError[] {
  return password.length >= PASSWORD_MIN ? [] : [{ name: 'password', message: `Не короче ${PASSWORD_MIN} символов` }]
}

// ник — те же правила, что у сервиса (service/app/auth/profile.py); занят ли — скажет сервис
const NICK = /^[0-9A-Za-zА-Яа-яЁё][0-9A-Za-zА-Яа-яЁё_-]{2,23}$/
export const NICK_HELP = 'От 3 до 24 знаков: буквы, цифры, «_» и «-». Его увидят другие пивовары'
export const NICK_OPTIONAL_HELP = 'Необязательно, можно позже в настройках. Без ника под рецептами будет «Неизвестный пивовар»'

export function checkNick(nick: string, name = 'name'): FormError[] {
  const n = nick.trim()
  if (!NICK.test(n)) return [{ name, message: 'От 3 до 24 знаков: буквы, цифры, «_» и «-»; без пробелов' }]
  if (/[A-Za-z]/.test(n) && /[А-Яа-яЁё]/.test(n)) return [{ name, message: 'Русские или латинские буквы, не вперемешку' }]
  return []
}
