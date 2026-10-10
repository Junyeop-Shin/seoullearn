import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { missingRounds, splitReports } from '../src/lib/reportSplit'

// 붙여 넣은 활동보고서 나누기 (규칙, 이 브라우저 안에서만 한다). 항목 이름은 활동보고서 양식에서 온다
const read = (path) => JSON.parse(readFileSync(resolve(process.cwd(), '..', path), 'utf-8'))
const fields = read('forms/activity_report.json').fields
const sessions = read('synthetic/sessions_M1.json').sessions.map((s) => ({ session_date: s.date, session_no: s.session_no, subject: '수학', course: '가상 강좌',
  ...Object.fromEntries(Object.entries(s.mentor_input).filter(([k]) => k !== 'notes')), session_content: s.mentor_input.notes || '' }))
// 플랫폼에서 복사해 붙여 넣은 모양: '항목 이름: 값'이 보고서마다 이어진다
const NAMES = { mentee_name: '김민지', mentee_grade: '고2', mentor: '홍길동(가람대 수학과)' }
const asPasted = (reports) => reports.map((r) => fields.map((f) => `${f.label}: ${NAMES[f.key] ?? r[f.key] ?? ''}`).join('\n')).join('\n\n')

describe('붙여 넣은 활동보고서 나누기', () => {
  it('16회차를 회차별로 나누고 이름 칸은 버린다', () => {
    const r = splitReports(asPasted(sessions), fields)
    expect(r.sessions.map((s) => s.session_no)).toEqual(Array.from({ length: 16 }, (_, i) => i + 1))
    expect(r.warnings).toEqual([])
    r.sessions.forEach((got, i) => {
      for (const key of ['session_date', 'actual_time', 'scope', 'attendance', 'homework', 'progress_scale']) expect(got[key] ?? '', `${i + 1}회차 ${key}`).toBe(sessions[i][key])
      for (const pii of Object.keys(NAMES)) expect(got).not.toHaveProperty(pii)
    })
    expect(JSON.stringify(r.sessions.map(({ session_content: _c, ...rest }) => rest))).not.toContain('김민지')
  })

  it('순서가 섞이고 빠지고 겹쳐도 회차 순으로 모으고 알린다', () => {
    const r = splitReports(asPasted([sessions[2], sessions[0], sessions[4], sessions[4]]), fields)
    expect(r.sessions.map((s) => s.session_no)).toEqual([1, 3, 5])
    expect(r.warnings.some((w) => w.includes('두 번'))).toBe(true)
    expect(missingRounds(r.sessions)).toEqual([2, 4])
    expect(missingRounds([])).toEqual([])
  })

  it('이름 표기가 조금 달라도 읽고, 항목이 없는 글은 받지 않는다', () => {
    const r = splitReports('멘토링 일자\n2026-03-09\n진행 회차 : 1회차\n진행시간: 17:03~18:05\n학습진도 - 출결: 정시 입장\n', fields)
    expect(r.sessions[0]).toEqual({ session_date: '2026-03-09', session_no: 1, actual_time: '17:03~18:05', attendance: '정시 입장' })
    expect(splitReports('아무 글이나 붙여 넣음', fields).sessions).toEqual([])
  })

  it('플랫폼 입력 칸 구성(학습 진도, 학습 이해도)도 읽고, 본문 줄을 항목 이름으로 잘못 읽지 않는다', () => {
    const text = ['멘티 성명: 김민지', '멘토링 일자: 2026-10-12', '진행 회차: 3회차', '이번 주차 학습 내용', '학습범위: 지수 5~6강', '학습 진도', '출결: 정시 출석 (17:02~18:04)',
      '인강: 5~6강 수강함', '과제: 5강 예제 풀기 수행하지 않음', '학습 이해도', '예제는 혼자 풂', '기타 문제집도 조금 풀어 봄', '기타', '화면이 자주 끊김', '건의사항', '다음 주는 쉽니다'].join('\n')
    const [s] = splitReports(text, fields).sessions
    expect(s).toMatchObject({ session_no: 3, session_date: '2026-10-12', scope: '학습범위: 지수 5~6강', attendance: '정시 출석 (17:02~18:04)', lecture_progress: '인강: 5~6강 수강함',
      homework: '과제: 5강 예제 풀기 수행하지 않음', session_content: '예제는 혼자 풂\n기타 문제집도 조금 풀어 봄', etc: '화면이 자주 끊김', requests: '다음 주는 쉽니다' })
    expect(s).not.toHaveProperty('mentee_name')
    // 시간확대(120분): 전반·후반 칸은 한 보고서 안에서 이어 붙인다
    const long = splitReports('멘토링 일자: 2026-10-12\n진행 회차: 2\n전반 1시간 학습 진도\n출결: 정시 출석\n전반 1시간 학습 이해도\n개념 설명\n후반 1시간 학습 진도\n문제 풀이 10문항\n후반 1시간 학습 이해도\n오답 정리', fields)
    expect(long.sessions).toHaveLength(1)
    expect(long.sessions[0]).toMatchObject({ progress_note: '출결: 정시 출석\n문제 풀이 10문항', session_content: '개념 설명\n오답 정리', attendance: '정시 출석' })
  })
})
