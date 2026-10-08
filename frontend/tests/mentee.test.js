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

import 'fake-indexeddb/auto'
import { KEEP_AFTER_TERM, docStatus, menteePath, nextStep, sessionRows } from '../src/lib/mentee'
import { clearAll, exportAlias, importAll, listItems, removeAlias, saveItem } from '../src/stores/vault'

describe('멘티 작업 공간', () => {
  const report = (no, over = {}) => item({ formId: 'activity_report', sessionNo: no, inputs: { session_no: String(no), session_date: `2026-10-${String(5 + 7 * no).padStart(2, '0')}`, status: '출석' }, ...over })
  const profile = { subject: '수학', start_datetime: '2026-10-12T17:00' }

  it('회차 목록은 16회차까지, 저장한 회차에는 날짜와 상태가 붙는다', () => {
    const rows = sessionRows([report(1), report(2, { inputs: { session_no: '2', session_date: '2026-10-19', status: '무단결석' } })], profile)
    expect(rows).toHaveLength(16)
    expect(rows[0]).toMatchObject({ no: 1, saved: true, date: '2026-10-12', expected: '2026-10-12' })
    expect(rows[1]).toMatchObject({ saved: true, status: '무단결석' })
    expect(rows[2]).toMatchObject({ no: 3, saved: false, expected: '2026-10-26' })
    expect(sessionRows([report(18)], null)).toHaveLength(18)
  })

  it('다음 할 일을 순서대로 안내한다', () => {
    expect(nextStep([], null)).toContain('기본 정보')
    expect(nextStep([], profile)).toContain('종합계획서①')
    const plan = item({ formId: 'plan_initial' })
    expect(nextStep([plan], profile)).toContain('1회차 활동보고서')
    expect(nextStep([plan, report(1)], profile)).toContain('종합계획서②')
    const file = item({ formId: 'plan_file' })
    expect(nextStep([plan, file, report(1), report(2)], profile)).toContain('3회차 활동보고서')
    const all = Array.from({ length: 16 }, (_, i) => report(i + 1))
    expect(nextStep([plan, file, ...all], profile)).toContain('완료보고서')
    expect(nextStep([plan, file, ...all, item({ formId: 'completion_report' })], profile)).toContain('회기 정리')
    expect(docStatus([plan, report(1), report(1), report(2)]).reports).toBe(2)   // 같은 회차를 두 번 저장해도 한 번으로 센다
    expect(menteePath('수학 고2 A', '/report/3')).toBe('/mentees/%EC%88%98%ED%95%99%20%EA%B3%A02%20A/report/3')
  })

  it('회기 정리는 기본 정보·완료보고서·인계 요약만 남기고, 다른 멘티는 건드리지 않는다', async () => {
    await clearAll()
    const A = '수학 고2 A'
    for (const formId of ['mentee_profile', 'plan_initial', 'plan_file', 'completion_report', 'handover_summary']) await saveItem({ alias: A, formId, title: formId })
    await saveItem({ alias: A, formId: 'activity_report', title: '1회차', sessionNo: 1 })
    await saveItem({ alias: '영어 중2 B', formId: 'activity_report', title: '1회차', sessionNo: 1 })
    const file = JSON.parse(JSON.stringify(await exportAlias(A)))
    expect(file.items).toHaveLength(6)
    expect(await removeAlias(A, KEEP_AFTER_TERM)).toBe(3)
    expect((await listItems(A)).map((x) => x.formId).sort()).toEqual(['completion_report', 'handover_summary', 'mentee_profile'])
    expect(await listItems('영어 중2 B')).toHaveLength(1)
    expect(await removeAlias(A)).toBe(3)
    expect(await listItems(A)).toHaveLength(0)
    expect(await importAll(file)).toBe(6)                     // 내보낸 파일로 되살릴 수 있다
    expect(await listItems(A)).toHaveLength(6)
  })
})
