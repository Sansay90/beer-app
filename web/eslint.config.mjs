// Правила — @nuxt/eslint, стиль кода задан в nuxt.config.ts (eslint.config.stylistic); здесь — отступления проекта.
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt(
  {
    rules: {
      // однострочный тип — через «;»: { title: string; icon?: string }
      '@stylistic/member-delimiter-style': ['error', {
        multiline: { delimiter: 'none' },
        singleline: { delimiter: 'semi', requireLast: false },
      }],
      // комментарии в конце строк выравниваются в столбец
      '@stylistic/no-multi-spaces': ['error', { ignoreEOLComments: true }],
      // однострочники вида async () => { unwrap(await …) } — осознанный стиль
      '@stylistic/max-statements-per-line': 'off',
      // разметка компактная: атрибуты и короткий текст элемента — в одной строке
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
    },
  },
)
