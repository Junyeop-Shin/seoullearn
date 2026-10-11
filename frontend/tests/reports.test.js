import { describe, expect, it } from 'vitest'
import { currentCompletion, goalsFromVault, handoverFromVault, myHandover, receivedHandover, reportsFromVault, termSummary } from '../src/lib/reports'

const item = (over) => ({ id: Math.random().toString(36), alias: '수학 고2 A', formId: 'activity_report', savedAt: '2026-10-01T00:00:00.000Z', inputs: {}, draft: {}, ...over })

describe('보관함 → 완료보고서·인계 요약 입력', () => {
  it('회차 순으로, 같은 회차는 가장 늦게 저장한 것을 쓴다', () => {
    const items = [
      item({ sessionNo: 2, inputs: { session_no: '2', session_date: '2026-03-16', status: '지각' }, draft: { attendance: '10분 지각' } }),
      item({ sessionNo: 1, savedAt: '2026-10-01T00:00:00.000Z', draft: { attendance: '옛 초안' } }),
      item({ sessionNo: 1, savedAt: '2026-10-02T00:00:00.000Z', inputs: { session_date: '2026-03-09' }, draft: { attendance: '정시 입장', mentee_name: '[멘티명]' } }),
      item({ formId: 'plan_initial', draft: { learning_goal: '문학 감 잡기' } }),
    ]
    const reports = reportsFromVault(items)
    expect(reports.map((r) => r.session_no)).toEqual([1, 2])
    expect(reports[0]).toEqual({ session_date: '2026-03-09', attendance: '정시 입장', session_no: 1, status: '출석' })
    expect(reports[1].status).toBe('지각')
    expect(reports[0].mentee_name).toBeUndefined() // 자리표시 칸은 넘기지 않는다
  })

  it('학습목표는 종합계획서②를 먼저, 없으면 ①을 쓴다', () => {
    const first = item({ formId: 'plan_initial', draft: { learning_goal: '인강 완강\n문학 감 잡기' } })
    const file = item({ formId: 'plan_file', draft: { learning_goal: ['문학 강좌 완강', ' 매주 인강 듣기 '] } })
    expect(goalsFromVault([first])).toEqual(['인강 완강', '문학 감 잡기'])
    expect(goalsFromVault([first, file])).toEqual(['문학 강좌 완강', '매주 인강 듣기'])
    expect(goalsFromVault([])).toEqual([])
  })


  it('가장 최근 인계 요약을 돌려준다', () => {
    expect(handoverFromVault([])).toBeNull()
    // 인계받은 글은 붙여 넣은 원문(text)과 함께 저장한다
    const a = item({ formId: 'handover_summary', savedAt: '2026-10-01T00:00:00.000Z', draft: { attitude: '옛것', text: '[학습 태도] 옛것' } })
    const b = item({ formId: 'handover_summary', savedAt: '2026-10-03T00:00:00.000Z', draft: { attitude: '성실함', text: '[학습 태도] 성실함' } })
    expect(handoverFromVault([a, b]).attitude).toBe('성실함')
    // 내가 다음 멘토에게 넘기려고 만든 요약(원문이 없다)은 인계받은 내용이 아니다. 두 화면이 같은 기준으로 가른다
    const mine = item({ formId: 'handover_summary', savedAt: '2026-10-05T00:00:00.000Z', draft: { attitude: '내가 쓴 요약' } })
    expect(handoverFromVault([a, b, mine]).attitude).toBe('성실함')
    expect(handoverFromVault([mine])).toBeNull()
    expect(myHandover([a, b, mine])).toBe(mine)
    // 인계받은 글을 지우고 저장한 것(빈 글)은 내 요약으로 읽히지 않는다
    const cleared = item({ formId: 'handover_summary', savedAt: '2026-10-06T00:00:00.000Z', draft: { text: '' } })
    expect(myHandover([cleared])).toBeUndefined()
    expect(receivedHandover([cleared])).toBe(cleared)
  })

  it('회기 요약에는 이번 회기에 저장한 완료보고서만 쓴다', () => {
    const old = item({ formId: 'completion_report', savedAt: '2026-06-01T00:00:00.000Z', draft: { content: '- 1회기 내용', achievement: '- 1회기 성취' } })
    const summary = item({ formId: 'term_summary', savedAt: '2026-06-02T00:00:00.000Z', draft: { term: 1 } })
    expect(currentCompletion([old, summary])).toBeUndefined()
    expect(termSummary([old, summary], { term: 2 }).content).toEqual([])   // 2회기 완료보고서를 저장하지 않고 넘어가도 1회기 것을 2회기 요약에 넣지 않는다
    const now = item({ formId: 'completion_report', savedAt: '2026-10-01T00:00:00.000Z', draft: { content: '- 2회기 내용', achievement: '' } })
    expect(currentCompletion([old, summary, now])).toBe(now)
    expect(termSummary([old, summary, now], { term: 2 }).content).toEqual(['2회기 내용'])
  })
})
