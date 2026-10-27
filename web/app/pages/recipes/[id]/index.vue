<script setup lang="ts">
// Рецепт: свой или опубликованный. Рендерится на сервере — для превью ссылок и поисковиков; вошедшему — по его cookie.
// Разделы — components/recipe/view/, действия в шапке — view/Actions.vue.
const route = useRoute()

const id = computed(() => route.params.id as string)
const { data: recipe, error } = await useRecipe(id)
const { data: equipment, error: equipmentError } = useEquipment()
useErrorToast(equipmentError)

// рецепта нет или он закрыт — к списку: на сервере перенаправлением, в браузере ещё и с тостом
const showError = useErrorToast()
async function notFound(e: unknown) {
  if (import.meta.client) showError(e)
  await navigateTo('/recipes', { replace: true })
}
if (error.value) await notFound(error.value)
watch(error, e => e && notFound(e))

const style = computed(() => styleByCode(recipe.value?.style?.code))
const volumes = computed(() => waterVolumes(recipe.value ?? {}, equipment.value?.evaporation))
// показатели — по ингредиентам, как в редакторе (сохранённые targets — снимок для списка); цифры — в панели «Стиль»
const calc = computed(() => (recipe.value ? calcRecipe(recipe.value) : null))

// превью ссылки и поисковики: название, стиль и цифры, начало описания
const description = computed(() => (recipe.value ? recipeDescription(recipe.value, calc.value) : undefined))
useSeoMeta({
  title: () => recipe.value?.name ?? 'Рецепт',
  description,
  ogTitle: () => recipe.value?.name,
  ogDescription: description,
  ogType: 'article',
})
</script>

<template>
  <UDashboardPanel id="recipe">
    <template #header>
      <UDashboardNavbar :title="recipe?.name ?? 'Рецепт'">
        <template #leading>
          <UButton icon="i-lucide-arrow-left" color="neutral" variant="ghost" to="/recipes" aria-label="К рецептам" />
        </template>
        <template v-if="recipe" #right>
          <RecipeViewActions :recipe="recipe" :recipe-id="id" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="!recipe" class="m-auto">
        <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin text-muted" />
      </div>

      <div v-else class="mx-auto grid w-full max-w-7xl gap-6 pb-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div class="min-w-0 space-y-6">
          <RecipeViewIntro :recipe="recipe" :recipe-id="id" :ebc="calc?.ebc" />
          <RecipeWaterSummary v-if="recipe.water && (recipe.water.ratio || recipe.water.additions?.length)" :water="recipe.water" :volumes="volumes" />
          <RecipeViewFermentables v-if="recipe.fermentables?.length" :items="recipe.fermentables" />
          <RecipeViewHops v-if="recipe.hops?.length" :items="recipe.hops" />
          <RecipeViewYeasts v-if="recipe.yeasts?.length" :items="recipe.yeasts" />
          <RecipeViewMiscs v-if="recipe.miscs?.length" :items="recipe.miscs" />
          <RecipeViewProgram :recipe="recipe" />
          <RecipeViewFermentation v-if="recipe.fermentation?.length" :items="recipe.fermentation" />
        </div>

        <aside class="space-y-4 xl:sticky xl:top-0 xl:self-start">
          <UCard :ui="{ body: 'p-5 sm:p-5' }">
            <div class="mb-4 text-xs font-medium uppercase tracking-wider text-dimmed">Стиль</div>
            <RecipeStyleRanges :bjcp="style" :custom="!!recipe.style && !recipe.style.code" :og="calc?.og" :fg="calc?.fg" :ibu="calc?.ibu" :ebc="calc?.ebc" />
          </UCard>
          <RecipeViewBatch :recipe="recipe" />
          <RecipeViewBrews v-if="recipe.meta.canEdit" :recipe-id="id" />
        </aside>
      </div>
    </template>
  </UDashboardPanel>
</template>
