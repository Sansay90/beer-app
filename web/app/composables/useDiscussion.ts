import type { Comment, RecipeDetail, RecipeSummary } from '~/types'
import type { VoteState } from '~/utils/votes'

// счётчики рецепта — в загруженных каталоге и странице (данные Nuxt, shallowRef: объект меняется целиком)
function patchRecipe(rid: string, list: (r: RecipeSummary) => Partial<RecipeSummary>, meta: (m: RecipeDetail['meta']) => Partial<RecipeDetail['meta']>) {
  const recipes = useNuxtData<RecipeSummary[]>('recipes').data
  if (recipes.value) recipes.value = recipes.value.map(r => (r.id === rid ? { ...r, ...list(r) } : r))
  const detail = useNuxtData<RecipeDetail | null>(recipeKey(rid)).data
  if (detail.value) detail.value = { ...detail.value, meta: { ...detail.value.meta, ...meta(detail.value.meta) } }
}

function setRecipeVotes(rid: string, v: VoteState) {
  patchRecipe(rid, () => ({ likes: v.likes, dislikes: v.dislikes }), () => ({ ...v }))
}

function bumpComments(rid: string, delta: number) {
  patchRecipe(rid, r => ({ comments: Math.max(0, r.comments + delta) }), m => ({ comments: Math.max(0, m.comments + delta) }))
}

/** Голос за рецепт: «нравится» / «не нравится», повторное нажатие снимает. Счётчики меняются сразу, сервис их уточняет;
 *  отказал — возвращаются с тостом. Гостю — панель входа. */
export function useRecipeVote() {
  const { $api } = useNuxtApp()
  const auth = useAuthStore()
  const drawer = useAuthDrawer()
  const showError = useErrorToast()

  async function vote(rid: string, current: VoteState, pressed: 1 | -1) {
    if (!auth.user) return drawer.show('login')
    const next = nextVote(current, pressed)
    setRecipeVotes(rid, next)
    try {
      setRecipeVotes(rid, await $api('/api/recipes/{rid}/vote', { method: 'PUT', path: { rid }, body: { value: next.vote } }))
    } catch (e) {
      setRecipeVotes(rid, current)
      showError(e)
    }
  }
  return { vote }
}

/** Обсуждение рецепта: комментарии (старые первыми, ответы — с parentId), написать, изменить, удалить, голос. */
export function useComments(rid: MaybeRefOrGetter<string>) {
  const { $api } = useNuxtApp()
  const auth = useAuthStore()
  const drawer = useAuthDrawer()
  const showError = useErrorToast()

  const id = computed(() => toValue(rid))
  const { data: comments, status, refresh } = useApi('/api/recipes/{rid}/comments', {
    path: { rid: id },
    key: () => `comments:${id.value}`,
    watch: [() => auth.user?.id],
    default: () => [],
  })

  const replace = (c: Comment) => { comments.value = comments.value.map(x => (x.id === c.id ? c : x)) }

  async function add(text: string, parentId?: string) {
    const c = await $api('/api/recipes/{rid}/comments', { method: 'POST', path: { rid: id.value }, body: { text, parentId } })
    comments.value = [...comments.value, c]
    bumpComments(id.value, 1)
  }

  async function edit(cid: string, text: string) {
    replace(await $api('/api/comments/{cid}', { method: 'PATCH', path: { cid }, body: { text } }))
  }

  async function remove(cid: string) {
    await $api('/api/comments/{cid}', { method: 'DELETE', path: { cid } })
    bumpComments(id.value, -1)
    await refresh()                                  // удалённый с ответами остаётся пустым — как решил сервис
  }

  async function vote(c: Comment, pressed: 1 | -1) {
    if (!auth.user) return drawer.show('login')
    const next = nextVote(c, pressed)
    replace({ ...c, ...next })
    try {
      replace({ ...c, ...await $api('/api/comments/{cid}/vote', { method: 'PUT', path: { cid: c.id }, body: { value: next.vote } }) })
    } catch (e) {
      replace(c)
      showError(e)
    }
  }

  return { comments, status, add, edit, remove, vote }
}
