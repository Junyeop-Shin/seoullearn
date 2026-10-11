import { beforeEach, describe, expect, it } from 'vitest'
import { PROFILE_FIELDS, displayName, fillValues, profileFromVault, suggestDate } from '../src/lib/mentee'

const item = (over) => ({ id: Math.random().toString(36), alias: '수학 고2 A', savedAt: '2026-10-01T00:00:00.000Z', inputs: {}, draft: {}, ...over })

describe('멘티 정보', () => {
  beforeEach(() => localStorage.clear())

  it('학교·연락처 칸은 없다 (이름과 학년은 이 브라우저에서만 쓴다)', () => {
    const text = PROFILE_FIELDS.map((f) => f.key + f.label).join(' ')
    for (const banned of ['학교', '연락처', '전화', 'school', 'phone']) expect(text).not.toContain(banned)
  })

  it('메뉴 이름과 개인정보 칸에 채울 값을 만든다', () => {
    const p = { name: '김OO', grade: '고1', subject: '수학', district: '성동구', mode: '오프라인' }
    expect(displayName(p)).toBe('김OO (고1, 수학, 성동구, 오프라인)')
    expect(displayName({ subject: '기타', subjectEtc: '검정고시' }, '멘티 1')).toBe('멘티 1 (검정고시)')
    expect(displayName({}, '멘티 2')).toBe('멘티 2')
    expect(fillValues(p, { name: '이멘토', university: '가상대', major: '수학교육', phone: '010-0000-0000' }))
      .toEqual({ mentee_name: '김OO', mentee_grade: '고1', mentee: '김OO (고1)', mentor: '이멘토 (가상대 수학교육)', mentor_phone: '010-0000-0000' })
    expect(fillValues({ name: '김OO' }, {})).toEqual({ mentee_name: '김OO', mentee: '김OO' })   // 없는 값은 자리표시로 남긴다
  })

  it('가장 최근에 저장한 정보를 돌려준다', () => {
    expect(profileFromVault([])).toBeNull()
    const old = item({ formId: 'mentee_profile', savedAt: '2026-10-01T00:00:00.000Z', draft: { subject: '국어' } })
    const now = item({ id: 'p2', formId: 'mentee_profile', savedAt: '2026-10-05T00:00:00.000Z', draft: { subject: '수학', weekday: '월' } })
    const p = profileFromVault([old, now, item({ formId: 'activity_report' })])
    expect(p).toMatchObject({ subject: '수학', weekday: '월', course: '', _id: 'p2', stage: 'PRE_CONTACT', currentRound: 1 })   // 회차 번호 없는 보고서는 세지 않는다
  })

  it('1회차 일시로 회차별 예상 날짜를 계산한다', () => {
    expect(suggestDate('2026-10-12T20:00', 1)).toBe('2026-10-12')
    expect(suggestDate('2026-10-12T20:00', 4)).toBe('2026-11-02')
    expect(suggestDate('2026-12-28T20:00', 2)).toBe('2027-01-04') // 해가 넘어가도
    expect(suggestDate('', 3)).toBe('')
  })
})

import 'fake-indexeddb/auto'
import { KEEP_AFTER_TERM, docStatus, menteePath, menteesFromVault, sessionRows } from '../src/lib/mentee'
import { clearAll, exportAll, importAll, listItems, removeAlias, saveItem } from '../src/stores/vault'

describe('멘티 작업 공간', () => {
  const report = (no, over = {}) => item({ formId: 'activity_report', sessionNo: no, inputs: { session_no: String(no), session_date: `2026-10-${String(5 + 7 * no).padStart(2, '0')}`, status: '출석' }, ...over })
  const profile = { subject: '수학', start_datetime: '2026-10-12T17:00' }

  it('회차 목록은 그 회기의 회차 수까지, 저장한 회차에는 날짜와 상태가 붙는다', () => {
    const rows = sessionRows([report(1), report(2, { inputs: { session_no: '2', session_date: '2026-10-19', status: '무단결석' } })], profile)
    expect(rows).toHaveLength(16)
    expect(rows[0]).toMatchObject({ no: 1, saved: true, date: '2026-10-12', expected: '2026-10-12' })
    expect(rows[1]).toMatchObject({ saved: true, status: '무단결석' })
    expect(rows[2]).toMatchObject({ no: 3, saved: false, expected: '2026-10-26' })
    expect(sessionRows([report(18)], null)).toHaveLength(18)
    expect(sessionRows([], { duration: '120' })).toHaveLength(8)   // 시간확대(120분)는 한 회기가 8회차다
  })

  it('문서 저장 여부와 멘티 주소', () => {
    const plan = item({ formId: 'plan_initial' })
    expect(docStatus([plan, report(1), report(1), report(2)]).reports).toBe(2)   // 같은 회차를 두 번 저장해도 한 번으로 센다
    expect(menteePath('수학 고2 A', '/report/3')).toBe('/mentees/%EC%88%98%ED%95%99%20%EA%B3%A02%20A/report/3')
  })

  it('회기 정리는 기본 정보·완료보고서·인계 요약만 남기고, 다른 멘티는 건드리지 않는다', async () => {
    await clearAll()
    const A = '수학 고2 A'
    for (const formId of ['mentee_profile', 'plan_initial', 'plan_file', 'completion_report', 'handover_summary']) await saveItem({ alias: A, formId, title: formId })
    await saveItem({ alias: A, formId: 'activity_report', title: '1회차', sessionNo: 1 })
    await saveItem({ alias: '영어 중2 B', formId: 'activity_report', title: '1회차', sessionNo: 1 })
    const file = JSON.parse(JSON.stringify(await exportAll(A)))
    expect(file.items).toHaveLength(6)
    expect(await removeAlias(A, KEEP_AFTER_TERM)).toBe(3)
    expect((await listItems(A)).map((x) => x.formId).sort()).toEqual(['completion_report', 'handover_summary', 'mentee_profile'])
    expect(await listItems('영어 중2 B')).toHaveLength(1)
    expect(await removeAlias(A)).toBe(3)
    expect(await listItems(A)).toHaveLength(0)
    expect(await importAll(file)).toBe(6)                     // 내보낸 파일로 되살릴 수 있다
    expect(await listItems(A)).toHaveLength(6)
    expect(await importAll({ ...file, items: [{ id: 'x', alias: A, formId: 'activity_report' }] })).toBe(0)   // savedAt 없는 항목은 받지 않는다 (화면이 깨진다)
  })

  it('멘티 목록은 멘티 정보가 있는 별칭만, 종료한 멘티는 뒤로', async () => {
    await clearAll()
    await saveItem({ alias: '나', formId: 'mentee_profile', title: '멘티 정보', draft: { name: '나' } })
    await saveItem({ alias: '가', formId: 'mentee_profile', title: '멘티 정보', draft: { name: '가', archived: true } })
    await saveItem({ alias: '나', formId: 'activity_report', title: '1회차', sessionNo: 1 })
    await saveItem({ alias: '내 강좌', formId: 'course_outline', title: '강좌' })   // 멘티 정보가 없는 별칭은 멘티가 아니다
    const list = await menteesFromVault()
    expect(list.map((m) => [m.alias, m.items.length, m.profile.name])).toEqual([['나', 2, '나'], ['가', 1, '가']])
  })
})
