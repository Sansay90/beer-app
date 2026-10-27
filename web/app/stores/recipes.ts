import type { Recipe, RecipeSummary, Visibility } from '~/types'

/** Рецепты на сервисе — опубликованные и свои, фото пива, публикация и загрузка рецепта в пивоварню. */
export const useRecipesStore = defineStore('recipes', () => {
  const { $api, $bridgeUrl } = useNuxtApp()

  const list = ref<RecipeSummary[]>([])
  const loaded = ref(false)

  async function fetchList() {
    list.value = unwrap(await $api.GET('/api/recipes'))
    loaded.value = true
  }

  async function get(id: string) {
    return unwrap(await $api.GET('/api/recipes/{rid}', { params: { path: { rid: id } } }))
  }

  /** Сохранить; id = null — новый рецепт. Возвращает id. */
  async function save(id: string | null, recipe: Recipe) {
    const res = id
      ? unwrap(await $api.PUT('/api/recipes/{rid}', { params: { path: { rid: id } }, body: recipe }))
      : unwrap(await $api.POST('/api/recipes', { body: recipe }))
    await fetchList()
    return res.id
  }

  /** Опубликовать или снять с публикации (автор; администратор — снять чужой). */
  async function setVisibility(id: string, visibility: Visibility) {
    unwrap(await $api.PUT('/api/recipes/{rid}/visibility', { params: { path: { rid: id } }, body: { visibility } }))
    await fetchList()
  }

  async function remove(id: string) {
    unwrap(await $api.DELETE('/api/recipes/{rid}', { params: { path: { rid: id } } }))
    await fetchList()
    return true
  }

  async function upload(id: string) {
    unwrap(await $api.POST('/api/recipes/{rid}/upload', { params: { path: { rid: id } } }))
    return true
  }

  /** Варки по рецепту, новые первыми. */
  async function brews(id: string) {
    return unwrap(await $api.GET('/api/brews', { params: { query: { recipe: id } } }))
  }

  // ── фото пива ──────────────────────────────────────────────────────────────
  async function photos(id: string) {
    return unwrap(await $api.GET('/api/recipes/{rid}/photos', { params: { path: { rid: id } } }))
  }

  /** Добавить фото: тело — сама картинка (уменьшенная shrinkPhoto). */
  async function addPhoto(id: string, image: Blob) {
    return unwrap(await $api.POST('/api/recipes/{rid}/photos', {
      params: { path: { rid: id } },
      body: image as unknown as string,
      bodySerializer: (b: unknown) => b as Blob,
      headers: { 'Content-Type': image.type },
    }))
  }

  async function removePhoto(pid: string) {
    unwrap(await $api.DELETE('/api/photos/{pid}', { params: { path: { pid } } }))
    return true
  }

  /** thumb — превью до 480 px для лент и карточек. */
  const photoUrl = (pid: string, thumb = false) => `${$bridgeUrl}/api/photos/${pid}${thumb ? '?thumb=true' : ''}`

  return { list, loaded, fetchList, get, save, setVisibility, remove, upload, brews, photos, addPhoto, removePhoto, photoUrl }
})
