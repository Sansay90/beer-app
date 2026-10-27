<script setup lang="ts">
// Действия с рецептом в шапке: избранное, правка, загрузка в пивоварню, копия, публикация, удаление.
// Что можно — решает сервис (meta.canEdit, meta.canModerate), здесь только кнопки.
import type { RecipeDetail, Visibility } from '~/types'

const props = defineProps<{ recipe: RecipeDetail; recipeId: string }>()

const { $api } = useNuxtApp()
const auth = useAuthStore()
const brewery = useBreweryStore()
const { exec, pending } = useCommand()
const { exec: execVisibility, pending: visibilityPending } = useCommand()   // своя загрузка — не крутить «В пивоварню»
const confirm = useConfirm()
const favorite = useFavorite()

const meta = computed(() => props.recipe.meta)
const inDevice = computed(() => brewery.snapshot?.deviceRecipe?.id === props.recipeId)
const programActive = computed(() => brewery.phase.running || brewery.phase.paused)
const hasProgram = computed(() => programOf(props.recipe).length > 0)

const uploadHint = computed(() => {
  if (!hasProgram.value) return 'В рецепте нет программы — добавьте паузы или кипячение'
  if (!brewery.online) return 'Пивоварня не в сети'
  if (programActive.value) return 'Программа идёт — заменить рецепт можно после её окончания'
  return 'Записать программу рецепта в пивоварню'
})

async function upload() {
  const current = brewery.snapshot?.deviceRecipe
  const ok = await confirm({
    title: 'Загрузить в пивоварню?',
    description: current
      ? `${current.name ? `«${current.name}»` : 'Текущая программа'} будет заменена на «${props.recipe.name}».`
      : `В пивоварню запишется «${props.recipe.name}».`,
    confirmLabel: 'Загрузить',
    confirmIcon: 'i-lucide-upload',
  })
  if (ok) await exec(() => $api('/api/recipes/{rid}/upload', { method: 'POST', path: { rid: props.recipeId } }), 'Рецепт загружен в пивоварню')
}

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
      ? `«${props.recipe.name}» будет удалён без возможности восстановления. История варок останется.`
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
  <!-- признаки рецепта — вместе, в верхней строке: видимость своего, «в пивоварне», избранное. Как у избранного:
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
  <UBadge v-if="inDevice" color="success" variant="subtle" size="lg" icon="i-lucide-check" label="в пивоварне" class="hidden h-8 sm:inline-flex" />
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
  <UTooltip v-if="auth.user" :text="uploadHint">
    <UButton
      icon="i-lucide-upload"
      label="В пивоварню"
      :loading="pending"
      :disabled="!hasProgram || !brewery.online || programActive"
      @click="upload"
    />
  </UTooltip>
  <UDropdownMenu :items="menu" :content="{ align: 'end' }">
    <UButton icon="i-lucide-ellipsis-vertical" color="neutral" variant="ghost" aria-label="Ещё" />
  </UDropdownMenu>
</template>
