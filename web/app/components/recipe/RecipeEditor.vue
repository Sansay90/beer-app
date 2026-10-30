<script setup lang="ts">
// Создание и правка рецепта. id = null — новый (from — копия существующего). Разделы формы — editor/.
import type { RecipeDraft } from '~/types/recipe'

const props = defineProps<{ id: string | null; from?: string | null }>()

const { $api } = useNuxtApp()
const { exec, pending } = useCommand()
const confirm = useConfirm()
const toast = useToast()

// исходные данные: рецепт (свой — правка, from — копия), ограничения пивоварни и профиль оборудования
const sourceId = computed(() => props.id ?? props.from ?? null)
const { data: source, status, error } = useRecipe(sourceId)
const { data: limits, error: limitsError } = useLimits()
const { data: equipment, status: equipmentStatus, error: equipmentError } = useEquipment()
useErrorToast(error, limitsError, equipmentError)

const draft = ref<RecipeDraft | null>(null)
const saved = ref('')                    // сохранённая версия — чтобы знать, есть ли правки

const dirty = computed(() => !!draft.value && JSON.stringify(draft.value) !== saved.value)
const errors = computed(() => (draft.value && limits.value ? validateRecipe(draft.value, limits.value) : []))
const back = computed(() => (props.id ? `/recipes/${props.id}` : '/recipes'))

const calc = computed(() => (draft.value ? calcRecipe(draft.value) : null))
const volumes = computed(() => waterVolumes(draft.value ?? {}, equipment.value?.evaporation))

// форма — один раз, когда всё загружено (без профиля оборудования — со средними цифрами); дальше её правит человек
const settled = (s: string) => s === 'success' || s === 'error'
const ready = computed(() => !!limits.value && settled(status.value) && settled(equipmentStatus.value))

function init() {
  const base = source.value
  if (!props.id) {
    draft.value = base ? { ...toDraft(base), name: `${base.name} (копия)` } : blankRecipe(limits.value!, equipment.value ?? null)
    saved.value = ''
    return
  }
  if (!base) return navigateTo('/recipes', { replace: true })
  if (!base.meta.canEdit) {                                // чужой рецепт — правится своя копия
    toast.add({ title: 'Это чужой рецепт', description: 'Правки сохранятся в вашу копию.', icon: 'i-lucide-copy' })
    return navigateTo({ path: '/recipes/new', query: { from: props.id } }, { replace: true })
  }
  draft.value = toDraft(base)
  saved.value = JSON.stringify(draft.value)
}
watch(sourceId, () => { draft.value = null })            // другой рецепт — форма заново
watch([ready, sourceId], () => ready.value && !draft.value && init(), { immediate: true })

async function canLeave() {
  return !dirty.value || await confirm({
    title: 'Есть несохранённые изменения',
    description: 'Если уйти, правки в рецепте пропадут.',
    confirmLabel: 'Отбросить изменения',
    color: 'warning',
  })
}
onBeforeRouteLeave(canLeave)

async function save() {
  if (!draft.value || errors.value.length) return
  const body = toRecipe(draft.value)
  const res = await exec(() => (props.id
    ? $api('/api/recipes/{rid}', { method: 'PUT', path: { rid: props.id }, body })
    : $api('/api/recipes', { method: 'POST', body })), 'Рецепт сохранён')
  if (!res) return
  saved.value = JSON.stringify(draft.value)
  await refreshNuxtData(recipeKey(res.id))               // страница рецепта читает его по тому же ключу
  await navigateTo(`/recipes/${res.id}`, { replace: !props.id })
}
</script>

<template>
  <UDashboardPanel id="recipe-editor">
    <template #header>
      <UDashboardNavbar :title="id ? 'Правка рецепта' : 'Новый рецепт'">
        <template #leading>
          <UButton icon="i-lucide-arrow-left" color="neutral" variant="ghost" :to="back" aria-label="Назад" />
        </template>
        <template v-if="draft" #right>
          <UBadge v-if="dirty" color="warning" variant="subtle" label="не сохранён" class="hidden sm:inline-flex" />
          <UButton color="neutral" variant="ghost" label="Отмена" :to="back" />
          <UButton icon="i-lucide-save" label="Сохранить" :loading="pending" :disabled="!!errors.length || (!!id && !dirty)" @click="save" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="!draft || !limits" class="m-auto">
        <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin text-muted" />
      </div>

      <div v-else class="mx-auto grid w-full max-w-7xl gap-6 pb-6 xl:grid-cols-[minmax(0,1fr)_19rem]">
        <div class="min-w-0 space-y-6">
          <RecipeEditorGeneral v-model="draft" :calc="calc" />

          <!-- из чего пиво: вода, солод, хмель, дрожжи — потом всё остальное -->
          <RecipeEditorWater v-model="draft.water" :volumes="volumes" :evaporation="equipment?.evaporation ?? undefined" :boil-minutes="draft.boil?.minutes ?? 0" />
          <RecipeEditorFermentables v-model="draft.fermentables" />
          <RecipeEditorHops v-model="draft.hops" :boil-minutes="draft.boil?.minutes ?? null" :volume="draft.batch.volume" />
          <RecipeEditorYeasts v-model="draft.yeasts" />
          <RecipeEditorMiscs v-model="draft.miscs" />
          <RecipeEditorProgram v-model="draft" :limits="limits" />
          <RecipeEditorFermentation v-model="draft.fermentation" />
        </div>

        <aside class="space-y-4 xl:sticky xl:top-0 xl:self-start">
          <RecipeEditorSummary v-model="draft" :calc="calc" />

          <UAlert v-if="errors.length" color="error" variant="subtle" icon="i-lucide-circle-alert" title="Пока нельзя сохранить">
            <template #description>
              <ul class="mt-1 list-disc space-y-0.5 pl-4">
                <li v-for="e in errors" :key="e">{{ e }}</li>
              </ul>
            </template>
          </UAlert>
        </aside>
      </div>
    </template>
  </UDashboardPanel>
</template>
