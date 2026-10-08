import { beforeEach, describe, expect, it } from 'vitest'
import { PROFILE_FIELDS, getCurrentAlias, nextSessionNo, preContactFromProfile, profileFromVault, setCurrentAlias, subjectTimeText, suggestDate } from '../src/lib/mentee'

const item = (over) => ({ id: Math.random().toString(36), alias: '수학 고2 A', savedAt: '2026-10-01T00:00:00.000Z', inputs: {}, draft: {}, ...over })

describe('멘티 정보', () => {
  beforeEach(() => localStorage.clear())

  it('이름·학년·학교·연락처 칸이 없다', () => {
    const text = PROFILE_FIELDS.map((f) => f.key + f.label).join(' ')
    for (const banned of ['이름', '성명', '학년', '학교', '연락처', '전화', 'name', 'grade', 'school', 'phone']) expect(text).not.toContain(banned)
  })

  it('가장 최근에 저장한 정보를 돌려준다', () => {
    expect(profileFromVault([])).toBeNull()
    const old = item({ formId: 'mentee_profile', savedAt: '2026-10-01T00:00:00.000Z', draft: { subject: '국어' } })
    const now = item({ id: 'p2', formId: 'mentee_profile', savedAt: '2026-10-05T00:00:00.000Z', draft: { subject: '수학', weekday: '월' } })
    const p = profileFromVault([old, now, item({ formId: 'activity_report' })])
    expect(p).toMatchObject({ subject: '수학', weekday: '월', course: '', _id: 'p2' })
  })

  it('다음 회차는 저장된 회차 중 가장 큰 값 + 1', () => {
    expect(nextSessionNo([])).toBe(1)
    expect(nextSessionNo([item({ formId: 'activity_report', sessionNo: 1 }), item({ formId: 'activity_report', sessionNo: 3 }),
      item({ formId: 'plan_initial' })])).toBe(4)
  })

  it('1회차 일시로 회차별 예상 날짜를 계산한다', () => {
    expect(suggestDate('2026-10-12T20:00', 1)).toBe('2026-10-12')
    expect(suggestDate('2026-10-12T20:00', 4)).toBe('2026-11-02')
    expect(suggestDate('2026-12-28T20:00', 2)).toBe('2027-01-04') // 해가 넘어가도
    expect(suggestDate('', 3)).toBe('')
  })

  it('과목 및 시간 글과 사전 정보를 만든다', () => {
    const p = { subject: '수학', course: '시발점 수1', weekday: '월', start_datetime: '2026-10-12T17:00', duration: '60', mode: '온라인', goal: '수1 완강', level: '' }
    expect(subjectTimeText(p)).toBe('수학 / 시발점 수1 / 매주(월) 17:00~18:00')
    expect(subjectTimeText({ ...p, duration: '120' })).toBe('수학 / 시발점 수1 / 매주(월) 17:00~19:00')
    expect(subjectTimeText({ subject: '수학' })).toBe('수학')
    expect(preContactFromProfile(p)).toEqual({ subject_confirm: '수학, 온라인', site_course: '시발점 수1', goal: '수1 완강' })
    expect(preContactFromProfile({})).toEqual({})
  })

  it('고른 멘티를 화면을 옮겨도 기억한다', () => {
    expect(getCurrentAlias()).toBe('')
    setCurrentAlias(' 수학 고2 A ')
    expect(getCurrentAlias()).toBe('수학 고2 A')
  })
})
