/** Голос за рецепт или комментарий: 1 — нравится, −1 — не нравится, 0 — нет голоса. */
export interface VoteState { likes: number; dislikes: number; vote: number }

/** Что будет после нажатия: тот же голос ещё раз — снять, другой — переключить. Счётчики — сразу, до ответа сервиса. */
export function nextVote(current: VoteState, pressed: 1 | -1): VoteState {
  const vote = current.vote === pressed ? 0 : pressed
  return {
    likes: current.likes - (current.vote === 1 ? 1 : 0) + (vote === 1 ? 1 : 0),
    dislikes: current.dislikes - (current.vote === -1 ? 1 : 0) + (vote === -1 ? 1 : 0),
    vote,
  }
}
