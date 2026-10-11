import { describe, expect, it } from 'vitest'
import { maskBody, rulesFor, unmask } from '../src/lib/nameMask'

describe('보내기 전에 등록한 이름 가리기', () => {
  const rules = rulesFor([['김민수', '[멘티명]'], ['지수', '[멘티명]'], ['이멘토', '[멘토명]'], ['김OO', '[멘티명]'], ['멘티 1', '[멘티명]']])
  const mask = (t) => maskBody({ a: [t] }, rules).body.a[0]

  it('이름 전체, 성을 뗀 이름을 맥락 규칙으로 가린다', () => {
    expect(mask('김민수가 결석했고 김민수 멘티는 내일 옴. 김민수')).toBe('[멘티명]가 결석했고 [멘티명] 멘티는 내일 옴. [멘티명]')
    expect(mask('민수가 예제를 품. 민수는 질문함. 민수 학생')).toBe('[멘티 이름]가 예제를 품. [멘티 이름]는 질문함. [멘티 이름] 학생')
    expect(mask('이멘토입니다')).toBe('이멘토입니다')   // 뒤에 다른 말이 붙은 것은 건드리지 않는다
  })

  it('흔한 낱말과 같은 이름은 사람에게 붙는 말이 올 때만 가린다', () => {
    expect(mask('지수와 로그, 지수함수, 지수 법칙')).toBe('지수와 로그, 지수함수, 지수 법칙')
    expect(mask('지수는 오늘 지각. 지수한테 과제를 냄')).toBe('[멘티명]는 오늘 지각. [멘티명]한테 과제를 냄')
    expect(mask('학습지원센터, 멘티 1명, 김OO')).toBe('학습지원센터, 멘티 1명, 김OO')
    // 멘토가 이름이 아니라고 푼 말은 가리지 않는다
    expect(maskBody('지수는 어렵다', rulesFor([['지수', '[멘티명]']], new Set(['지수']))).body).toBe('지수는 어렵다')
  })

  it('응답에서 자리표시를 가린 말로 되돌리고, 가린 것이 없으면 그대로 둔다', () => {
    const { body, found } = maskBody({ q: '민수가 결석' }, rules)
    expect(body.q).toBe('[멘티 이름]가 결석')
    expect(unmask({ draft: { x: ['[멘티 이름]가 결석함'] } }, found)).toEqual({ draft: { x: ['민수가 결석함'] } })
    const both = maskBody('민수가 품. 김민수 멘티', rules)
    expect(unmask(both.body, both.found)).toBe('민수가 품. 김민수 멘티')   // 줄인 이름과 이름 전체가 섞이지 않는다
    expect(unmask({ name: '[멘티명]' }, {})).toEqual({ name: '[멘티명]' })
  })
})
