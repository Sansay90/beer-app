/** Ключ рецепта в данных Nuxt — для refreshNuxtData после правки. */
export const recipeKey = (id: string | null) => `recipe:${id ?? 'new'}`

/** Рецепт по id — страница рецепта и редактор читают его по одному ключу; id = null — рецепта нет (новый).
 *  После входа и выхода перечитывается: от этого зависят права (meta). */
export function useRecipe(id: MaybeRefOrGetter<string | null>) {
  const { $api } = useNuxtApp()
  const auth = useAuthStore()
  return useAsyncData(
    () => recipeKey(toValue(id)),
    () => {
      const rid = toValue(id)
      return rid ? $api('/api/recipes/{rid}', { path: { rid } }) : Promise.resolve(null)
    },
    { watch: [() => auth.user?.id] },
  )
}
