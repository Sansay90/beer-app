<script setup lang="ts">
// Действия с рецептом в шапке: правка, загрузка в пивоварню, копия, публикация, удаление.
// Что можно — решает сервис (meta.canEdit, meta.canModerate), здесь только кнопки.
import type { RecipeDetail, Visibility } from '~/types'

const props = defineProps<{ recipe: RecipeDetail; recipeId: string }>()

const { $api } = useNuxtApp()
const auth = useAuthStore()
const brewery = useBreweryStore()
const { exec, pending } = useCommand()
const confirm = useConfirm()

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
  if (visibility === 'public' && !await confirm({
    title: 'Опубликовать рецепт?',
    description: 'Его увидят все, и гости тоже. Править сможете только вы, снять с публикации — в любой момент.',
    confirmLabel: 'Опубликовать',
    confirmIcon: 'i-lucide-globe',
  })) return
  const done = await exec(() => $api('/api/recipes/{rid}/visibility', { method: 'PUT', path: { rid: props.recipeId }, body: { visibility } }),
    visibility === 'public' ? 'Рецепт опубликован' : 'Рецепт снят с публикации')
  if (done) await refreshNuxtData(recipeKey(props.recipeId))
}

async function remove() {
  const ok = await confirm({
    title: 'Удалить рецепт?',
    description: meta.value.canEdit
      ? `«${props.recipe.name}» будет удалён без возможности восстановления. История варок останется.`
      : `«${props.recipe.name}» автора ${meta.value.author} будет удалён без возможности восстановления.`,
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
    ...(m.canEdit || m.canModerate ? [[publish]] : []),
    ...(m.canEdit || m.canModerate ? [[{ label: 'Удалить', icon: 'i-lucide-trash-2', color: 'error' as const, onSelect: remove }]] : []),
  ]
})
</script>

<template>
  <UBadge v-if="inDevice" color="success" variant="subtle" icon="i-lucide-check" label="в пивоварне" class="hidden sm:inline-flex" />
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
