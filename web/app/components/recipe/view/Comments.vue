<script setup lang="ts">
// Обсуждение рецепта: написать — вошедшему (гостю — «Войти»); ветки — комментарий и ответы под ним, старые первыми.
// Ответ на ответ встаёт в ту же ветку — так решает и сервис. Пришли из уведомления (#c-<id>) — комментарий
// прокручивается на виду и подсвечен.
import type { Comment } from '~/types'

const props = defineProps<{ recipeId: string }>()
const auth = useAuthStore()
const drawer = useAuthDrawer()
const confirm = useConfirm()
const showError = useErrorToast()
const { comments, status, add, edit, remove, vote } = useComments(() => props.recipeId)

const threads = computed(() => comments.value
  .filter(c => !c.parentId)
  .map(c => ({ comment: c, replies: comments.value.filter(r => r.parentId === c.id) })))
const count = computed(() => comments.value.filter(c => !c.deleted).length)

// якорь — только в браузере: на сервер адрес приходит без #, подсветка не должна расходиться с его разметкой
const route = useRoute()
const target = ref<string | null>(null)
onMounted(() => {
  watch([() => route.hash, () => comments.value.length], async ([hash]) => {
    target.value = hash.startsWith('#c-') ? hash.slice(3) : null
    if (!target.value) return
    await nextTick()
    document.getElementById(`c-${target.value}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, { immediate: true })
})
// подсветка — подложкой под комментарием: раскладка не сдвигается
const HIGHLIGHT = 'before:pointer-events-none before:absolute before:-inset-2 before:-z-10 before:rounded-lg before:bg-primary/10 before:ring-1 before:ring-primary/40'
const mark = (id: string) => ({ id: `c-${id}`, class: ['relative isolate', target.value === id && HIGHLIGHT] })

const text = ref('')
const sending = ref(false)
const replyTo = ref<string | null>(null)          // в какой ветке открыт ответ
const replyText = ref('')

async function send(body: string, parentId?: string) {
  sending.value = true
  try {
    await add(body, parentId)
    return true
  } catch (e) {
    showError(e)
    return false
  } finally {
    sending.value = false
  }
}

async function submit() {
  if (await send(text.value.trim())) text.value = ''
}

async function submitReply(threadId: string) {
  if (!await send(replyText.value.trim(), threadId)) return
  replyText.value = ''
  replyTo.value = null
}

function reply(threadId: string) {
  if (!auth.user) return drawer.show('login')
  replyTo.value = threadId
  replyText.value = ''
}

async function save(c: Comment, body: string) {
  try {
    await edit(c.id, body)
  } catch (e) {
    showError(e)
  }
}

async function del(c: Comment) {
  if (!await confirm({ title: 'Удалить комментарий?', confirmLabel: 'Удалить', confirmIcon: 'i-lucide-trash-2', color: 'error' })) return
  try {
    await remove(c.id)
  } catch (e) {
    showError(e)
  }
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-baseline gap-2">
        <h2 class="text-2xl font-semibold text-highlighted">Обсуждение</h2>
        <span v-if="count" class="text-lg text-muted">{{ count }}</span>
      </div>
    </template>

    <form v-if="auth.user" class="space-y-2" @submit.prevent="submit">
      <UTextarea
        v-model="text"
        autoresize
        :rows="2"
        :maxrows="12"
        size="lg"
        placeholder="Спросите автора или расскажите, как сварили"
        class="w-full"
      />
      <div class="flex justify-end">
        <UButton type="submit" label="Отправить" icon="i-lucide-send" size="lg" :loading="sending && !replyTo" :disabled="!text.trim()" />
      </div>
    </form>
    <div v-else class="flex flex-wrap items-center gap-3">
      <span class="text-base text-muted">Чтобы написать, войдите.</span>
      <UButton label="Войти" icon="i-lucide-log-in" variant="soft" size="lg" @click="drawer.show('login')" />
    </div>

    <div v-if="threads.length" class="mt-6 divide-y divide-default">
      <div v-for="t in threads" :key="t.comment.id" class="py-5 first:pt-0 last:pb-0">
        <RecipeViewComment
          v-bind="mark(t.comment.id)"
          :comment="t.comment"
          @reply="reply(t.comment.id)"
          @vote="v => vote(t.comment, v)"
          @save="body => save(t.comment, body)"
          @remove="del(t.comment)"
        />
        <div v-if="t.replies.length || replyTo === t.comment.id" class="mt-4 ms-12 space-y-4 border-s-2 border-default ps-4">
          <RecipeViewComment
            v-for="r in t.replies"
            :key="r.id"
            v-bind="mark(r.id)"
            :comment="r"
            @reply="reply(t.comment.id)"
            @vote="v => vote(r, v)"
            @save="body => save(r, body)"
            @remove="del(r)"
          />
          <form v-if="replyTo === t.comment.id" class="space-y-2" @submit.prevent="submitReply(t.comment.id)">
            <UTextarea v-model="replyText" autoresize :rows="2" :maxrows="12" size="lg" placeholder="Ваш ответ" class="w-full" autofocus />
            <div class="flex gap-2">
              <UButton type="submit" label="Ответить" icon="i-lucide-send" :loading="sending" :disabled="!replyText.trim()" />
              <UButton label="Отмена" color="neutral" variant="ghost" @click="replyTo = null" />
            </div>
          </form>
        </div>
      </div>
    </div>
    <p v-else-if="status === 'success'" class="mt-5 text-base text-muted">Пока никто не написал.</p>
  </UCard>
</template>
