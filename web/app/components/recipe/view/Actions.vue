<script setup lang="ts">
// Действия с рецептом в шапке: «Сварить» (главное; гостю — панель входа, после входа окно откроется само),
// избранное, правка, копия, публикация, удаление. В пивоварню программа уходит вместе с партией — из «Сварить».
// Что можно — решает сервис (meta.canEdit, meta.canModerate), здесь только кнопки.
import type { RecipeDetail, Visibility } from '~/types'

const props = defineProps<{ recipe: RecipeDetail; recipeId: string }>()

const { $api } = useNuxtApp()
const auth = useAuthStore()
const { exec } = useCommand()
const { exec: execVisibility, pending: visibilityPending } = useCommand()
const confirm = useConfirm()
const favorite = useFavorite()
const drawer = useAuthDrawer()

// «Сварить»: вошедшему — окно, гостю — вход; вошёл — окно открывается само
const starting = ref(false)
const wantStart = ref(false)
function start() {
  if (auth.user) {
    starting.value = true
    return
  }
  wantStart.value = true
  drawer.show('login')
}
watch(() => auth.user, (u) => {
  if (u && wantStart.value) {
    wantStart.value = false
    starting.value = true
  }
})

const meta = computed(() => props.recipe.meta)
async function setVisibility(visibility: Visibility) {
  // публиковать — с подтверждённой почтой: сразу сказать и предложить письмо, а не ждать отказа сервиса
  if (visibility === 'public' && !auth.user?.emailVerified) {
    useToast().add({
      title: 'Сначала подтвердите почту',
      description: `Ссылка — в письме на ${auth.user?.email}.`,
      color: 'warning',
      icon: 'i-lucide-mail-warning',
      actions: [{ label: 'Отправить ещё раз', color: 'neutral', variant: 'outline', onClick: () => { exec(() => auth.resendVerify(), 'Письмо отправлено') } }],
    })
    return
  }
  if (visibility === 'public' && !await confirm({
    title: 'Опубликовать рецепт в каталоге?',
    description: 'Его смогут найти и сварить другие пивовары.',
    confirmLabel: 'Опубликовать',
    confirmIcon: 'i-lucide-globe',
  })) return
  // снять — тоже с вопросом: кнопка-переключатель в шапке, нажать её случайно легко
  if (visibility === 'private' && !await confirm({
    title: 'Убрать рецепт из каталога?',
    description: 'Другие пивовары перестанут его видеть. Вернуть можно в любой момент.',
    confirmLabel: 'Убрать',
    confirmIcon: 'i-lucide-eye-off',
  })) return
  const done = await execVisibility(() => $api('/api/recipes/{rid}/visibility', { method: 'PUT', path: { rid: props.recipeId }, body: { visibility } }),
    visibility === 'public' ? 'Рецепт опубликован' : 'Рецепт снят с публикации')
  if (done) await refreshNuxtData(recipeKey(props.recipeId))
}

async function remove() {
  const ok = await confirm({
    title: 'Удалить рецепт?',
    description: meta.value.canEdit
      ? `«${props.recipe.name}» будет удалён без возможности восстановления. Варки по нему останутся в «Моих варках».`
      : `«${props.recipe.name}» автора ${brewerName(meta.value.author)} будет удалён без возможности восстановления.`,
    confirmLabel: 'Удалить',
    confirmIcon: 'i-lucide-trash-2',
    color: 'error',
  })
  if (ok && await exec(() => $api('/api/recipes/{rid}', { method: 'DELETE', path: { rid: props.recipeId } }), 'Рецепт удалён')) navigateTo('/recipes')
}

const menu = computed(() => {
  const m = meta.value
  const copy = {
    label: m.canEdit ? 'Дублировать' : 'Сохранить себе копию',
    icon: 'i-lucide-copy',
    to: { path: '/recipes/new', query: { from: props.recipeId } },
  }
  const publish = m.visibility === 'public'
    ? { label: 'Снять с публикации', icon: 'i-lucide-eye-off', onSelect: () => setVisibility('private') }
    : { label: 'Опубликовать', icon: 'i-lucide-globe', onSelect: () => setVisibility('public') }
  return [
    [copy],
    ...(m.canModerate ? [[publish]] : []),           // свой — переключателем в шапке; здесь — администратору у чужого
    ...(m.canEdit || m.canModerate ? [[{ label: 'Удалить', icon: 'i-lucide-trash-2', color: 'error' as const, onSelect: remove }]] : []),
  ]
})
</script>

<template>
  <!-- признаки рецепта — вместе, в верхней строке: видимость своего, избранное. Как у избранного:
       пока нет — действие («Опубликовать»), есть — состояние («Опубликован»), клик — обратно -->
  <UButton
    v-if="meta.canEdit"
    icon="i-lucide-globe"
    :label="meta.visibility === 'public' ? 'Опубликован' : 'Опубликовать'"
    :color="meta.visibility === 'public' ? 'success' : 'neutral'"
    :variant="meta.visibility === 'public' ? 'soft' : 'outline'"
    :aria-pressed="meta.visibility === 'public'"
    :ui="{ label: 'hidden sm:inline' }"
    :loading="visibilityPending"
    @click="setVisibility(meta.visibility === 'public' ? 'private' : 'public')"
  />
  <UButton
    :icon="meta.favorite ? 'i-lucide-bookmark-check' : 'i-lucide-bookmark'"
    :label="meta.favorite ? 'В избранном' : 'В избранное'"
    :color="meta.favorite ? 'primary' : 'neutral'"
    :variant="meta.favorite ? 'soft' : 'outline'"
    :aria-pressed="meta.favorite"
    :ui="{ label: 'hidden sm:inline' }"
    @click="favorite.toggle(recipeId, !meta.favorite)"
  />
  <UButton v-if="meta.canEdit" icon="i-lucide-pencil" label="Изменить" color="neutral" variant="outline" :to="`/recipes/${recipeId}/edit`" />
  <UButton icon="i-lucide-flame" label="Сварить" @click="start" />
  <BrewStartModal v-model:open="starting" :recipe-id="recipeId" :recipe="recipe" />
  <UDropdownMenu :items="menu" :content="{ align: 'end' }">
    <UButton icon="i-lucide-ellipsis-vertical" color="neutral" variant="ghost" aria-label="Ещё" />
  </UDropdownMenu>
</template>
