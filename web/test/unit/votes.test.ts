import { describe, expect, it } from 'vitest'
import { nextVote } from '../../app/utils/votes'

describe('nextVote', () => {
  it('голос появляется', () => {
    expect(nextVote({ likes: 2, dislikes: 1, vote: 0 }, 1)).toEqual({ likes: 3, dislikes: 1, vote: 1 })
    expect(nextVote({ likes: 2, dislikes: 1, vote: 0 }, -1)).toEqual({ likes: 2, dislikes: 2, vote: -1 })
  })

  it('тот же ещё раз — снимается', () => {
    expect(nextVote({ likes: 3, dislikes: 1, vote: 1 }, 1)).toEqual({ likes: 2, dislikes: 1, vote: 0 })
  })

  it('другой — переключается', () => {
    expect(nextVote({ likes: 3, dislikes: 1, vote: 1 }, -1)).toEqual({ likes: 2, dislikes: 2, vote: -1 })
    expect(nextVote({ likes: 0, dislikes: 2, vote: -1 }, 1)).toEqual({ likes: 1, dislikes: 1, vote: 1 })
  })
})
