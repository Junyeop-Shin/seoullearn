import { describe, expect, it } from 'vitest'
import { maskBody, rulesFor, unmask } from '../src/lib/nameMask'

describe('보내기 전에 등록한 이름 가리기', () => {
  const rules = rulesFor([['김민수', '[멘티명1]'], ['지수', '[멘티명2]'], ['이멘토', '[멘토명]'], ['김OO', '[멘티명3]'], ['멘티 1', '[멘티명4]'], ['박서연', '[멘티명5]'], ['남궁민아', '[멘티명6]'], ['Kim Minsu', '[멘티명7]']])
  const mask = (t) => maskBody({ a: [t] }, rules).body.a[0]

  it('이름 전체, 성을 뗀 이름을 맥락 규칙으로 가린다', () => {
    expect(mask('김민수가 결석했고 김민수 멘티는 내일 옴. 김민수')).toBe('[멘티명1]가 결석했고 [멘티명1] 멘티는 내일 옴. [멘티명1]')
    expect(mask('민수가 예제를 품. 민수는 질문함. 민수 학생')).toBe('[멘티 이름1]가 예제를 품. [멘티 이름1]는 질문함. [멘티 이름1] 학생')
    // 이름 전체는 뒤에 무엇이 붙든 가린다
    expect(mask('이멘토입니다. 박서연이 같이 옴. 김민수에게는 김민수님, 김민수처럼')).toBe('[멘토명]입니다. [멘티명5]이 같이 옴. [멘티명1]에게는 [멘티명1]님, [멘티명1]처럼')
    expect(maskBody({ image: 'data:image/jpeg;base64,/9Kim/+kim4', t: 'Kim Minsu 학생' }, rulesFor([['Kim', '[멘티명1]']])).body).toEqual({ image: 'data:image/jpeg;base64,/9Kim/+kim4', t: '[멘티명1] Minsu 학생' })
    expect(mask('민수에게는 서연이를 민아가 Kim Minsu가 kim minsu')).toBe('[멘티 이름1]에게는 [멘티 이름5]이를 [멘티 이름6]가 [멘티명7]가 [멘티명7]')
  })

  it('흔한 낱말과 같은 이름은 사람에게 붙는 말이 올 때만 가린다', () => {
    expect(mask('지수와 로그, 지수함수, 지수 법칙')).toBe('지수와 로그, 지수함수, 지수 법칙')
    expect(mask('지수는 오늘 지각. 지수한테 과제를 냄')).toBe('[멘티명2]는 오늘 지각. [멘티명2]한테 과제를 냄')
    expect(mask('학습지원센터, 멘티 1명, 김OO')).toBe('학습지원센터, 멘티 1명, 김OO')
    // 멘토가 이름이 아니라고 푼 말은 가리지 않는다
    expect(maskBody('지수는 어렵다', rulesFor([['지수', '[멘티명]']], new Set(['지수']))).body).toBe('지수는 어렵다')
  })

  it('응답에서 자리표시를 가린 말로 되돌리고, 가린 것이 없으면 그대로 둔다', () => {
    const { body, found } = maskBody({ q: '민수가 결석' }, rules)
    expect(body.q).toBe('[멘티 이름1]가 결석')
    expect(unmask({ draft: { x: ['[멘티 이름1]가 결석함'] } }, found)).toEqual({ draft: { x: ['민수가 결석함'] } })
    const both = maskBody('민수가 품. 김민수 멘티', rules)
    expect(unmask(both.body, both.found)).toBe('민수가 품. 김민수 멘티')   // 줄인 이름과 이름 전체가 섞이지 않는다
    const two = maskBody('김민수와 박서연은 지각. 지수는 정시. 서연이는 숙제 안 함', rules)
    expect(unmask(two.body, two.found)).toBe('김민수와 박서연은 지각. 지수는 정시. 서연이는 숙제 안 함')   // 멘티 둘의 이름이 섞이지 않는다
    expect(unmask({ name: '[멘티명]' }, two.found)).toEqual({ name: '[멘티명]' })   // 서버가 둔 자리는 화면이 채운다
  })
})
