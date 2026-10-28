<script setup lang="ts">
// Карточка рецепта в списке: бокал в цвет пива, начало описания, цифры одной строкой, под ними — автор;
// внизу — отклик (нравится, не нравится, комментарии, сколько раз сварили все) и миниатюры фото пива:
// в широкой карточке — до трёх внахлёст, в узкой — одна со значком «+N», чтобы не теснить отклик.
// Высота у всех карточек одна: описание всегда в две строки, цифры и низ — фиксированной высоты.
// Ссылка на рецепт — название, растянутое на всю карточку; миниатюры — кнопки поверх неё: фото открываются тут же.
// Свой опубликованный — со значком глобуса.
import type { RecipeSummary } from '~/types'

const props = defineProps<{ recipe: RecipeSummary; inDevice?: boolean }>()
const prefs = usePreferencesStore()
const auth = useAuthStore()
const favorite = useFavorite()
const photoUrl = usePhotoUrl()

const t = computed(() => props.recipe.targets)
const color = computed(() => beerColor(t.value.ebc))
// отсвет цвета пива из угла с бокалом
const glow = computed(() => (color.value
  ? { backgroundImage: `radial-gradient(130% 100% at 0% 0%, color-mix(in oklab, ${color.value} 13%, transparent), transparent 65%)` }
  : undefined))

const num = (v: number, digits = 0) => v.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })
const stats = computed(() => {
  const { og, fg, ibu, ebc } = t.value
  // крепость сохраняет сервис (с сахаром на брожении); у рецептов, сохранённых раньше, — по OG и FG
  const abv = t.value.abv ?? abvOf(og, fg)
  return [
    og != null && (prefs.gravityUnit === 'plato'
      ? { value: num(gravityIn(og, 'plato'), 1), unit: '°P' }
      : { value: num(gravityIn(og, 'sg'), 3), unit: 'OG' }),
    abv != null && { value: num(abv, 1), unit: '% ABV' },
    ibu != null && { value: num(ibu), unit: 'IBU' },
    ebc != null && { value: num(ebc), unit: 'EBC' },
  ].filter(s => !!s)
})

const counts = computed(() => [
  { label: 'нравится', icon: 'i-lucide-thumbs-up', value: props.recipe.likes },
  { label: 'не нравится', icon: 'i-lucide-thumbs-down', value: props.recipe.dislikes },
  { label: 'комментариев', icon: 'i-lucide-message-circle', value: props.recipe.comments },
  { label: 'раз сварили', icon: 'i-lucide-beer', value: props.recipe.brewsTotal },
])

// миниатюр — не больше MAX, остальные — счётчиком
const MAX_THUMBS = 3
const thumbs = computed(() => props.recipe.photos.slice(0, MAX_THUMBS))
const more = computed(() => props.recipe.photos.length - thumbs.value.length)

// просмотр фото прямо из списка: подписи авторов приходят со списком фото рецепта — его читаем по первому нажатию
const { data: viewer, error, execute } = useApi('/api/recipes/{rid}/photos', {
  path: { rid: props.recipe.id },
  key: `photos:${props.recipe.id}`,
  default: () => [],
  immediate: false,
})
const showError = useErrorToast()
const viewing = ref<number | null>(null)
async function openPhoto(i: number) {
  await execute()
  if (error.value) return showError(error.value)
  if (viewer.value.length) viewing.value = Math.min(i, viewer.value.length - 1)
}
</script>

<template>
  <div
    class="group relative flex min-w-0 gap-4 rounded-xl bg-default p-4 ring ring-default transition hover:ring-accented has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-primary"
    :style="glow"
  >
    <RecipeGlass :ebc="t.ebc" :style-code="recipe.style?.code" class="h-24 transition-transform duration-300 group-hover:-translate-y-1 group-hover:-rotate-3" />

    <div class="@container flex min-w-0 flex-1 flex-col">
      <div class="flex items-start gap-2">
        <div class="min-w-0 flex-1">
          <NuxtLink :to="`/recipes/${recipe.id}`" class="block truncate font-display text-lg leading-snug font-semibold text-highlighted outline-none after:absolute after:inset-0 after:rounded-xl">
            {{ recipe.name }}
          </NuxtLink>
          <div class="flex items-center gap-1 text-sm text-muted">
            <UIcon v-if="recipe.mine && recipe.visibility === 'public'" name="i-lucide-globe" class="size-3.5 shrink-0" aria-label="Опубликован" />
            <span class="truncate">{{ styleLabel(recipe.style) }}</span>
          </div>
        </div>
        <UBadge v-if="inDevice" color="success" variant="subtle" size="sm" label="в пивоварне" class="shrink-0" />
        <!-- кнопка поверх ссылки-карточки (z-10): отметить, не открывая рецепт -->
        <UButton
          v-if="auth.user"
          :icon="recipe.favorite ? 'i-lucide-bookmark-check' : 'i-lucide-bookmark'"
          :color="recipe.favorite ? 'primary' : 'neutral'"
          variant="ghost"
          size="sm"
          square
          class="relative z-10 -me-1.5 -mt-1 shrink-0"
          :class="!recipe.favorite && 'text-dimmed'"
          :aria-label="recipe.favorite ? 'Убрать из избранного' : 'В избранное'"
          :aria-pressed="recipe.favorite"
          @click="favorite.toggle(recipe.id, !recipe.favorite)"
        />
      </div>

      <p class="mt-1.5 line-clamp-2 h-10 font-serif text-sm text-toned">{{ recipe.about }}</p>

      <div class="num mt-2 flex h-6 flex-nowrap items-baseline gap-x-3 overflow-hidden text-sm">
        <span v-for="s in stats" :key="s.unit" class="whitespace-nowrap">
          <span class="text-base font-semibold text-highlighted">{{ s.value }}</span>
          <span class="ms-1 text-muted">{{ s.unit }}</span>
        </span>
        <span v-if="!stats.length" class="text-dimmed">Только программа пивоварни</span>
      </div>

      <p class="truncate text-xs text-muted">
        Автор:
        <!-- поверх ссылки-карточки (z-10): ведёт на страницу автора -->
        <NuxtLink v-if="recipe.author.name" :to="brewerPath(recipe.author.name)" class="relative z-10 text-toned hover:text-highlighted hover:underline">{{ recipe.author.name }}</NuxtLink>
        <span v-else class="text-toned">{{ UNKNOWN_BREWER }}</span>
      </p>

      <div class="mt-auto flex items-end justify-between gap-3 pt-1.5">
        <!-- отклик пивоваров: нравится, не нравится, комментарии, сколько раз сварили все -->
        <div class="flex items-center gap-3 pb-1 text-sm text-muted tabular-nums @max-xs:gap-2">
          <span v-for="c in counts" :key="c.label" class="flex items-center gap-1" :title="c.label">
            <UIcon :name="c.icon" class="size-4 shrink-0" />{{ c.value }}<span class="sr-only">{{ c.label }}</span>
          </span>
        </div>
        <div v-if="thumbs.length" class="relative z-10 hidden shrink-0 -space-x-2.5 @sm:flex">
          <button
            v-for="(pid, i) in thumbs"
            :key="pid"
            type="button"
            class="relative size-10 overflow-hidden rounded-md ring-2 ring-(--ui-bg) transition hover:z-10 hover:-translate-y-0.5 focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-primary"
            :aria-label="`Фото ${i + 1}`"
            @click="openPhoto(i)"
          >
            <img :src="photoUrl(pid, true)" alt="" loading="lazy" class="size-full object-cover">
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
        <button
          v-if="thumbs.length"
          type="button"
          class="relative z-10 size-10 shrink-0 rounded-md ring-2 ring-(--ui-bg) transition hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-primary @sm:hidden"
          :aria-label="`Фото пива: ${recipe.photos.length}`"
          @click="openPhoto(0)"
        >
          <img :src="photoUrl(thumbs[0]!, true)" alt="" loading="lazy" class="size-full rounded-md object-cover">
          <span v-if="recipe.photos.length > 1" class="absolute -end-2 -top-2 rounded-full bg-elevated px-1.5 text-xs leading-5 text-highlighted ring-2 ring-(--ui-bg)">
            +{{ recipe.photos.length - 1 }}
          </span>
        </button>
      </div>
    </div>

    <RecipePhotoViewer v-model:index="viewing" :photos="viewer" :title="recipe.name" :to="`/recipes/${recipe.id}`" />
  </div>
</template>
