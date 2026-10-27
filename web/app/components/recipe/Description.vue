<script setup lang="ts">
// Описание рецепта: абзацы — через пустую строку. Длинное свёрнуто до нескольких строк с «Читать полностью».
const props = defineProps<{ text: string }>()

const paragraphs = computed(() => props.text.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean))
const box = ref<HTMLElement | null>(null)
const open = ref(false)
const overflowing = ref(false)

// свёрнутое — по высоте блока: line-clamp не работает через несколько абзацев
useResizeObserver(box, () => {
  if (!open.value && box.value) overflowing.value = box.value.scrollHeight > box.value.clientHeight + 1
})
watch(() => props.text, () => { open.value = false })
</script>

<template>
  <div>
    <div
      ref="box"
      class="space-y-3 overflow-hidden font-serif leading-relaxed text-toned"
      :class="{ 'max-h-36': !open, 'mask-b-from-50%': !open && overflowing }"
    >
      <p v-for="(p, i) in paragraphs" :key="i" class="whitespace-pre-line">{{ p }}</p>
    </div>
    <UButton
      v-if="overflowing"
      :label="open ? 'Свернуть' : 'Читать полностью'"
      :trailing-icon="open ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
      color="neutral"
      variant="link"
      size="sm"
      class="mt-1 px-0"
      @click="open = !open"
    />
  </div>
</template>
