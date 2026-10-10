import { describe, expect, it } from 'vitest'
import { draftValueText, goalsFromVault, handoverFromVault, reportsFromVault } from '../src/lib/reports'

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

  it('강의 목록을 한 줄씩 글로 바꾼다', () => {
    const lectures = [{ no: 1, title: '문학 감상의 관점' }, { no: 2, title: '시적 화자와 정서' }]
    expect(draftValueText(lectures)).toBe('1강 문학 감상의 관점\n2강 시적 화자와 정서')
    expect(draftValueText([{ no: null, title: '오리엔테이션' }])).toBe('오리엔테이션')
    expect(draftValueText(['a', 'b'])).toBe('a\nb')
    expect(draftValueText(null)).toBe('')
  })

  it('가장 최근 인계 요약을 돌려준다', () => {
    expect(handoverFromVault([])).toBeNull()
    const a = item({ formId: 'handover_summary', savedAt: '2026-10-01T00:00:00.000Z', draft: { attitude: '옛것' } })
    const b = item({ formId: 'handover_summary', savedAt: '2026-10-03T00:00:00.000Z', draft: { attitude: '성실함' } })
    expect(handoverFromVault([a, b]).attitude).toBe('성실함')
  })
})
