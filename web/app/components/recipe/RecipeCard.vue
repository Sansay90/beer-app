<script setup lang="ts">
// Карточка рецепта в списке: бокал в цвет пива, начало описания, цифры одной строкой, внизу — миниатюры фото пива.
// Высота у всех карточек одна: описание всегда в две строки, цифры и низ — фиксированной высоты.
// Ссылка на рецепт — название, растянутое на всю карточку; миниатюры — кнопки поверх неё: фото открываются тут же.
// Чужой рецепт — с автором внизу, свой опубликованный — со значком глобуса.
import type { Photo, RecipeSummary } from '~/types'

const props = defineProps<{ recipe: RecipeSummary; inDevice?: boolean }>()
const prefs = usePreferencesStore()
const recipes = useRecipesStore()
const { exec } = useCommand()

const t = computed(() => props.recipe.targets)
const color = computed(() => beerColor(t.value.ebc))
// отсвет цвета пива из угла с бокалом
const glow = computed(() => (color.value
  ? { backgroundImage: `radial-gradient(130% 100% at 0% 0%, color-mix(in oklab, ${color.value} 13%, transparent), transparent 65%)` }
  : undefined))

const num = (v: number, digits = 0) => v.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })
const stats = computed(() => {
  const { og, fg, ibu, ebc } = t.value
  const abv = abvOf(og, fg)
  return [
    og != null && (prefs.gravityUnit === 'plato'
      ? { value: num(gravityIn(og, 'plato'), 1), unit: '°P' }
      : { value: num(gravityIn(og, 'sg'), 3), unit: 'OG' }),
    abv != null && { value: num(abv, 1), unit: '% ABV' },
    ibu != null && { value: num(ibu), unit: 'IBU' },
    ebc != null && { value: num(ebc), unit: 'EBC' },
  ].filter(s => !!s)
})

// миниатюр — не больше MAX, остальные — счётчиком
const MAX_THUMBS = 3
const thumbs = computed(() => props.recipe.photos.slice(0, MAX_THUMBS))
const more = computed(() => props.recipe.photos.length - thumbs.value.length)

// просмотр фото прямо из списка: подписи авторов приходят со списком фото рецепта
const viewer = ref<Photo[]>([])
const viewing = ref<number | null>(null)
async function openPhoto(i: number) {
  viewer.value = (await exec(() => recipes.photos(props.recipe.id))) ?? []
  if (viewer.value.length) viewing.value = Math.min(i, viewer.value.length - 1)
}

const footer = computed(() => {
  const r = props.recipe
  const program = r.steps ? fmtMinutes(r.minutes) : 'без программы'
  if (!r.mine) return `${program} · автор ${r.author}`          // варки — свои, по чужому рецепту их не видно
  if (!r.brews) return `${program} · ещё не варили`
  const last = new Date(r.lastBrewedAt! * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
  return `${program} · варили ${r.brews} ${plural(r.brews, 'раз', 'раза', 'раз')}, ${last}`
})
</script>

<template>
  <div
    class="group relative flex gap-4 rounded-xl bg-default p-4 ring ring-default transition hover:ring-accented has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-primary"
    :style="glow"
  >
    <RecipeGlass :ebc="t.ebc" :style-code="recipe.style?.code" class="h-24 transition-transform duration-300 group-hover:-translate-y-1 group-hover:-rotate-3" />

    <div class="flex min-w-0 flex-1 flex-col">
      <div class="flex items-start gap-2">
        <div class="min-w-0 flex-1">
          <NuxtLink :to="`/recipes/${recipe.id}`" class="block truncate font-semibold text-highlighted outline-none after:absolute after:inset-0 after:rounded-xl">
            {{ recipe.name }}
          </NuxtLink>
          <div class="flex items-center gap-1 text-sm text-muted">
            <UIcon v-if="recipe.mine && recipe.visibility === 'public'" name="i-lucide-globe" class="size-3.5 shrink-0" aria-label="Опубликован" />
            <span class="truncate">{{ styleLabel(recipe.style) }}</span>
          </div>
        </div>
        <UBadge v-if="inDevice" color="success" variant="subtle" size="sm" label="в пивоварне" class="shrink-0" />
      </div>

      <p class="mt-2 line-clamp-2 h-10 text-sm text-toned">{{ recipe.about }}</p>

      <div class="num mt-3 flex h-5 flex-nowrap gap-x-3.5 overflow-hidden text-sm">
        <span v-for="s in stats" :key="s.unit" class="whitespace-nowrap">
          <span class="font-semibold text-highlighted">{{ s.value }}</span>
          <span class="ms-1 text-muted">{{ s.unit }}</span>
        </span>
        <span v-if="!stats.length" class="text-dimmed">Только программа пивоварни</span>
      </div>

      <div class="num mt-auto flex h-11 items-end justify-between gap-3 text-xs text-dimmed">
        <span class="truncate pb-1">{{ footer }}</span>
        <div v-if="thumbs.length" class="relative z-10 flex shrink-0 -space-x-2.5">
          <button
            v-for="(pid, i) in thumbs"
            :key="pid"
            type="button"
            class="relative size-10 overflow-hidden rounded-md ring-2 ring-(--ui-bg) transition hover:z-10 hover:-translate-y-0.5 focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-primary"
            :aria-label="`Фото ${i + 1}`"
            @click="openPhoto(i)"
          >
            <img :src="recipes.photoUrl(pid, true)" alt="" loading="lazy" class="size-full object-cover">
          </button>
          <button
            v-if="more > 0"
            type="button"
            class="relative grid size-10 place-items-center rounded-md bg-elevated text-xs text-muted ring-2 ring-(--ui-bg) transition hover:text-highlighted focus-visible:outline-2 focus-visible:outline-primary"
            :aria-label="`Ещё ${more} фото`"
            @click="openPhoto(MAX_THUMBS)"
          >
            +{{ more }}
          </button>
        </div>
      </div>
    </div>

    <RecipePhotoViewer v-model:index="viewing" :photos="viewer" :title="recipe.name" :to="`/recipes/${recipe.id}`" />
  </div>
</template>
