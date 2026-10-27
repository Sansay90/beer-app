<script setup lang="ts">
// Аватар пивовара: своё фото или, пока его нет, бокал — стиль, цвет пива и фон выбираются по id: у каждого свой
// и не меняется. Размер задаёт родитель (size-8).
const props = defineProps<{ user: { id: string; name?: string | null; avatar?: string | null } }>()
const { $apiBase } = useNuxtApp()

// бокал и пиво — пары, какие бывают в жизни: пилснер светлый, стаут в пинте тёмный
const GLASSES = [
  { code: '5D', ebc: 6 }, { code: '5B', ebc: 8 }, { code: '10A', ebc: 9 }, { code: '10B', ebc: 32 },
  { code: '21A', ebc: 14 }, { code: '19A', ebc: 26 }, { code: '26B', ebc: 38 }, { code: '26C', ebc: 11 },
  { code: '15B', ebc: 75 }, { code: '17D', ebc: 45 },
]
const BACKS = ['bg-amber-500/15', 'bg-lime-600/15', 'bg-orange-700/15', 'bg-stone-500/20']

function hash(s: string) {
  let h = 0
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0
  return h
}
const look = computed(() => {
  const h = hash(props.user.id)
  return { glass: GLASSES[h % GLASSES.length]!, back: BACKS[(h >>> 8) % BACKS.length]! }
})
</script>

<template>
  <span
    class="relative inline-grid shrink-0 place-items-center overflow-hidden rounded-full ring ring-default"
    :class="!user.avatar && look.back"
    :title="brewerName(user)"
  >
    <img v-if="user.avatar" :src="`${$apiBase}${user.avatar}`" :alt="brewerName(user)" class="size-full object-cover" loading="lazy">
    <RecipeGlass v-else :ebc="look.glass.ebc" :style-code="look.glass.code" class="h-[72%]" />
  </span>
</template>
