// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import StageBar from '../src/components/StageBar.vue'
import { DISTRICTS, regularSchedule, scheduleText } from '../src/lib/mentee'
import { courseName, curriculumCell, curriculumLines, curriculumRow, handoverForDraft, handoverNote, handoverText, parseHandoverText, plannedRow, previousHomework, termSummary, termSummaryText, plannedWeek } from '../src/lib/reports'
import { dateLine, endTime, fillNames, monthDates, monthlyText, nextMonth, scheduleDue, thisMonth, weeklyDates } from '../src/lib/schedule'
import { strFromU8, strToU8, unzipSync, zipSync } from 'fflate'
import curriculum from '../public/data/curriculum.json'
import { fillPlanFile, mentorCode, planFileName } from '../src/lib/planFile'
import { absentText, applyLines, assignedLines, boxText, contentAuto, fromLines, halvesOf, progressLines, statusesOf, syncLines, toLines } from '../src/lib/report'
import { CURRICULUM_SUBJECTS, GRADES, FIRST_WEEK, LAST_WEEK, findUnits, genericHints, gradeKey, hasExams, spreadUnits, weekFrame } from '../src/lib/curriculum'
import { DIAG_SLOTS, GOAL_SLOTS, composeSlots, lectureRange, onlineText, parseSlots, platformSafe, toCircled, changedLines } from '../src/lib/plan'
import { PROFILE_FIELDS, menteeFacts } from '../src/lib/mentee'
import { afterReport, flow, nextStage, nextTerm, prevStage, stageBadge, totalRounds, withState } from '../src/lib/stage'
import { loadSettings, saveSettings } from '../src/stores/settings'
import { isSeniorCourse, monthRows, payInfo, reportMonths } from '../src/lib/allowance'
import { validChannels } from '../src/lib/channels'
import channels from '../public/data/eumdan_channels.json'
import TEMPLATE from '../src/templates/monthly_schedule.md?raw'


const item = (over) => ({ id: Math.random().toString(36), alias: 'A', savedAt: '2026-10-01T00:00:00.000Z', inputs: {}, extra: {}, draft: {}, ...over })
const report = (no, over = {}) => item({ formId: 'activity_report', sessionNo: no, ...over })

describe('단계 흐름', () => {
  it('사전 연락 → 종합계획서 → 활동보고서 → 완료보고서 순서다', () => {
    expect(flow().map((s) => s.id)).toEqual(['PRE_CONTACT', 'PLAN', 'ACTIVITY', 'COMPLETION'])
    expect(nextStage({ stage: 'PRE_CONTACT' })).toBe('PLAN')
    expect(nextStage({ stage: 'PLAN' })).toBe('ACTIVITY')
    expect(prevStage({ stage: 'PLAN' })).toBe('PRE_CONTACT')
    expect(prevStage({ stage: 'PRE_CONTACT' })).toBe('PRE_CONTACT')
    expect(nextStage({ stage: 'COMPLETION' })).toBe('COMPLETION')
  })

  it('사전 연락은 멘티를 처음 만나는 1회기에만 있다', () => {
    expect(flow({ term: 1 })[0].id).toBe('PRE_CONTACT')
    expect(flow({ term: 2 }).map((s) => s.id)).toEqual(['PLAN', 'ACTIVITY', 'COMPLETION'])
    expect(prevStage({ term: 2, stage: 'PLAN' })).toBe('PLAN')                     // 2회기부터는 사전 연락으로 돌아가지 않는다
    expect(withState({ term: 2, stage: 'PRE_CONTACT' }, []).stage).toBe('PLAN')
  })

  it('회차 수는 회당 학습시간으로 정해진다: 60분 16회차, 120분 8회차', () => {
    expect(totalRounds({ duration: '60' })).toBe(16)
    expect(totalRounds({ duration: '120' })).toBe(8)
    expect(totalRounds({ duration: '120', totalRounds: '16' })).toBe(8)   // 예전에 따로 적어 둔 값은 쓰지 않는다
  })

  it('활동보고서를 저장하면 다음 회차로, 마지막 회차면 완료보고서로 넘어간다', () => {
    const p = { stage: 'ACTIVITY', currentRound: 5, duration: '60' }
    expect(afterReport(p, 5)).toEqual({ currentRound: 6 })
    expect(afterReport(p, 3)).toEqual({})                       // 지난 회차를 고쳐 저장한 것은 단계를 바꾸지 않는다
    expect(afterReport({ ...p, currentRound: 16 }, 16)).toEqual({ stage: 'COMPLETION' })
    expect(afterReport({ stage: 'ACTIVITY', currentRound: 8, duration: '120' }, 8)).toEqual({ stage: 'COMPLETION' })
    expect(afterReport({ stage: 'PLAN', currentRound: 1 }, 1)).toEqual({})
    expect(stageBadge({ stage: 'ACTIVITY', currentRound: 5 })).toBe('활동보고서 5회차')
    expect(stageBadge({ stage: 'PLAN' })).toBe('종합계획서')
  })

  it('단계 정보가 없는 예전 자료는 저장된 문서로 단계를 짐작한다', () => {
    expect(withState({}, [])).toMatchObject({ stage: 'PRE_CONTACT', term: 1, currentRound: 1 })
    expect(withState({}, [item({ formId: 'plan_initial' })]).stage).toBe('PLAN')
    expect(withState({}, [report(1), report(2)])).toMatchObject({ stage: 'ACTIVITY', currentRound: 3 })
    expect(withState({}, Array.from({ length: 16 }, (_, i) => report(i + 1))).stage).toBe('COMPLETION')
    for (const old of ['VENUE', 'PRE_PLAN', 'FIRST_SESSION']) expect(withState({ stage: old }, []).stage).toBe('PLAN')   // 예전에 따로 있던 단계
    expect(withState({ stage: 'ACTIVITY', currentRound: 7, term: 2 }, [])).toMatchObject({ stage: 'ACTIVITY', currentRound: 7, term: 2 })   // 진행 중 등록
  })

  it('다음 회기는 회차를 1로 되돌리고 종합계획서부터 다시 시작한다', () => {
    // 지난 회기의 목표·진단·1회차 일시는 넘기지 않는다 (새 종합계획서①이 지난 글로 채워지지 않게)
    expect(nextTerm({ term: 1, currentRound: 16, stage: 'COMPLETION', duration: '60', name: '김OO', goal: '(1) 수1 완강', level: '(과목역량) 보통', start_datetime: '2026-03-09T17:00' }, '120'))
      .toMatchObject({ term: 2, currentRound: 1, stage: 'PLAN', duration: '120', name: '김OO', goal: '', level: '', start_datetime: '' })
  })

  it('진행바는 지금 단계를 표시하고 누른 단계를 알린다', async () => {
    const w = mount(StageBar, { props: { stages: flow(), current: 'ACTIVITY', viewing: 'ACTIVITY' } })
    expect(w.find('[aria-current="step"]').text()).toContain('활동보고서')
    expect(w.findAll('li.done')).toHaveLength(2)
    await w.find('[data-stage="PLAN"]').trigger('click')
    expect(w.emitted('view')[0]).toEqual(['PLAN'])
  })
})

describe('일정 계산과 문구 (규칙만 사용)', () => {
  it('주차별 날짜와 끝나는 시각', () => {
    expect(weeklyDates('2026-12-21', 3)).toEqual(['2026-12-21', '2026-12-28', '2027-01-04'])
    expect(weeklyDates('', 2)).toEqual(['', ''])
    expect(endTime('17:30', '120')).toBe('19:30')
    expect(dateLine({ date: '2026-11-04', start: '19:00' }, '60')).toBe('11/4(수) 19:00~20:00')
  })

  it('정규 일정으로 다음달 날짜를 나열한다', () => {
    expect(thisMonth('2026-10-20')).toEqual({ year: 2026, month: 10 })
    expect(nextMonth('2026-10-20')).toEqual({ year: 2026, month: 11 })
    expect(nextMonth('2026-12-20')).toEqual({ year: 2027, month: 1 })
    const rows = monthDates([{ weekday: '수', startTime: '19:00' }, { weekday: '토', startTime: '10:00' }], 2026, 11)
    expect(rows.map((r) => r.date)).toEqual(['2026-11-04', '2026-11-07', '2026-11-11', '2026-11-14', '2026-11-18', '2026-11-21', '2026-11-25', '2026-11-28'])
    expect(rows[1]).toEqual({ date: '2026-11-07', start: '10:00' })
    expect(monthDates([], 2026, 11)).toEqual([])
    expect([scheduleDue('2026-10-16'), scheduleDue('2026-10-20'), scheduleDue('2026-10-24')]).toEqual([false, true, false])
  })

  it('정규 일정이 없으면 1회차 일시의 요일과 시각을 쓴다', () => {
    expect(regularSchedule({ start_datetime: '2026-10-12T17:00' })).toEqual([{ weekday: '월', startTime: '17:00' }])
    expect(regularSchedule({ regularSchedule: [{ weekday: '수', startTime: '19:00' }], start_datetime: '2026-10-12T17:00' })[0].weekday).toBe('수')
    expect(scheduleText({ start_datetime: '2026-10-12T17:00', duration: '120' })).toBe('매주 월 17:00~19:00')
  })

  it('이음단에 보낼 일정 문구: 인사말이 붙고, 몇 년인지는 쓰지 않는다', () => {
    const text = monthlyText(TEMPLATE, { month: 11, mentorName: '이멘토', menteeName: '김OO', venue: '가상 스터디카페',
      rows: [{ date: '2026-11-04', start: '19:00' }, { date: '', start: '' }, { date: '2026-11-11', start: '19:00' }], minutes: '60' })
    expect(text).toBe(['안녕하세요, 서울런 멘토 이멘토입니다.', '11월 오프라인 멘토링 일정과 장소를 공유드립니다.', '',
      '[11월 멘토링 일정]', '멘토: 이멘토', '멘티: 김OO', '장소: 가상 스터디카페', '일정:', '- 11/4(수) 19:00~20:00', '- 11/11(수) 19:00~20:00', '',
      '확인 부탁드립니다. 감사합니다.'].join('\n'))
    expect(text).not.toContain('2026')
    const blank = monthlyText(TEMPLATE, { month: 11, rows: [] })
    expect(blank).toContain('멘토: [멘토명]')                         // 이름이 없으면 자리표시로 남긴다
    expect(blank).toContain('장소: (미정) 가능한 장소 안내 부탁드립니다')   // 장소가 없으면 이음단에 안내를 부탁한다
  })

  it('서버가 만든 글의 자리표시를 이 브라우저의 이름으로 바꾼다', () => {
    const sms = '서울런 멘토 [멘토명]입니다. [멘티명] 학생 … [멘토 연락처]로 문자 남겨 주세요. [멘티명]'
    expect(fillNames(sms, { mentee: '김OO', mentor: '이멘토', phone: '010-0000-0000' })).toBe('서울런 멘토 이멘토입니다. 김OO 학생 … 010-0000-0000로 문자 남겨 주세요. 김OO')
    expect(fillNames(sms, {})).toBe(sms)
  })
})

describe('계획서와 보고서 연결', () => {
  it('커리큘럼 표를 계획서 줄로 바꾼다', () => {
    const rows = [{ week: 1, date: '2026-10-12', content: '지수' }, { week: 2, date: '2026-10-19', content: ' ' }, { week: 3, date: '', content: '로그' }]
    expect(curriculumLines(rows)).toEqual(['1주차(10/12) 지수', '3주차 로그'])
    // 종합계획서②: '(온라인강의) 강좌명(강사명), n강' 줄바꿈 '(멘토링 내용) 학습 내용'. 상담은 넣지 않는다
    const course = { lecture: '시발점 수1', instructor: '가상 강사' }
    expect(curriculumLines([{ week: 1, date: '2026-10-12', time: '17:00', online: '1~2강', mentoring: 'OT', counsel: '진로 상담', extras: ['입시·진학 상담'] }, { week: 2, date: '' }], true, course))
      .toEqual(['1주차(10/12 17:00)\n(온라인강의) 시발점 수1(가상 강사), 1~2강\n(멘토링 내용) OT'])
    expect(curriculumCell({ online: '', mentoring: '앞 회차 복습' }, course)).toBe('(온라인강의) 시발점 수1(가상 강사)\n(멘토링 내용) 앞 회차 복습')
    expect(curriculumCell({ online: '3강', mentoring: '' }, {})).toBe('(온라인강의) 3강\n(멘토링 내용) -')
  })

  it('회차마다 고친 일시가 커리큘럼 줄과 보고서 기본값에 쓰인다', () => {
    expect(curriculumLines([{ week: 2, date: '2026-11-12', time: '18:00', content: '로그' }])).toEqual(['2주차(11/12 18:00) 로그'])
    const pre = item({ formId: 'plan_initial', extra: { rows: [{ week: 2, date: '2026-11-12', time: '18:00', content: '' }] } })
    expect(plannedRow([pre], 2)).toMatchObject({ date: '2026-11-12', time: '18:00' })   // 내용이 없어도 일시는 쓴다
    expect(curriculumRow([pre], 2)).toBeNull()
  })

  it('지난 회기 요약에는 목표·진도·성취만 남기고 감성케어는 넣지 않는다', () => {
    const items = [
      item({ formId: 'plan_initial', draft: { learning_goal: '수1 완강' } }),
      report(15, { inputs: { session_no: '15', status: '출석' }, draft: { scope: '29강' } }),
      report(16, { inputs: { session_no: '16', status: '출석' }, draft: { scope: '30강 총정리' }, extra: { assignedHomework: { lecture: '수2 1강', task: '' } } }),
      item({ formId: 'completion_report', draft: { content: ['지수와 로그 단원을 마침.'], achievement: ['완강함.'], emotional_care: '부모님과 갈등 상담' } }),
    ]
    const s = termSummary(items, { term: 1, course: '시발점 수1' })
    expect(s).toMatchObject({ term: 1, rounds: 2, course: '시발점 수1', goal: ['수1 완강'], last_scope: '30강 총정리', next_homework: { lecture: '수2 1강', task: '' } })
    expect(JSON.stringify(s)).not.toContain('갈등')
    expect(termSummaryText(s)).toContain('마지막 회차 학습 범위: 30강 총정리')
    expect(termSummaryText(null)).toBe('')
    // 지금 화면으로 저장한 보고서: 내 준 과제는 학습 이해도의 문장으로만 남는다
    const now = [report(16, { inputs: { session_no: '16', status: '출석' }, extra: { sheet: { understanding: ['개념 설명을 잘 이해함\n3강 예제 풀기를 다음 회차까지 과제로 냄'] } } })]
    expect(termSummary(now, { term: 1 }).next_homework).toBeNull()   // '과제:' 줄로 적지 않은 것은 불러오지 않는다
  })

  it('이번 회차의 계획과 지난 회차에 낸 과제를 찾는다', () => {
    const pre = item({ formId: 'plan_initial', extra: { rows: [{ week: 3, content: '로그' }] } })
    const file = item({ formId: 'plan_file', extra: { rows: [{ week: 3, online: '5~6강', mentoring: '로그 성질' }] } })
    expect(curriculumRow([pre], 3).content).toBe('로그')
    expect(curriculumRow([pre, file], 3).online).toBe('5~6강')        // 종합계획서②가 먼저다
    expect(curriculumRow([pre], 4)).toBeNull()
    const r2 = report(2, { extra: { assignedHomework: { lecture: '5~6강', task: '예제 풀기' } } })
    expect(previousHomework([r2], 3, {})).toEqual({ lecture: '5~6강', task: '예제 풀기' })
    expect(previousHomework([report(2)], 3, { lastHomework: { lecture: '1강' } })).toBeNull()       // 직전 보고서가 있으면 등록 때 적은 것은 쓰지 않는다
    expect(previousHomework([], 7, { lastHomework: { lecture: '11강', task: '' } })).toEqual({ lecture: '11강', task: '' })   // 진행 중 등록
  })

})

describe('종합계획서의 항목 형식', () => {
  it('학습 목표는 ①~④(플랫폼용은 (1)~(4)), 학생 진단은 머리말을 붙여 한 줄씩 묶는다', () => {
    const parts = ['시발점 수1 완강', '', '오답노트 작성하기', '']
    expect(composeSlots(GOAL_SLOTS, parts)).toBe('① 시발점 수1 완강\n③ 오답노트 작성하기')
    expect(composeSlots(GOAL_SLOTS, parts, '', true)).toBe('(1) 시발점 수1 완강\n(3) 오답노트 작성하기')
    expect(composeSlots(DIAG_SLOTS, ['기본기는 갖춤', '', '', '인강 의존도가 높음'], '1회차에 자세한 상담 예정'))
      .toBe('(과목역량) 기본기는 갖춤\n(학습습관 및 태도) 인강 의존도가 높음\n1회차에 자세한 상담 예정')
  })

  it('묶은 글을 다시 항목별로 나눈다', () => {
    expect(parseSlots(GOAL_SLOTS, '(1) 시발점 수1 완강\n③오답노트 작성하기')).toEqual({ parts: ['시발점 수1 완강', '', '오답노트 작성하기', ''], rest: '' })
    expect(parseSlots(DIAG_SLOTS, '(과목역량) 기본기는 갖춤\n(학습습관 및 태도) 인강 의존도가 높음\n1회차에 자세한 상담 예정'))
      .toEqual({ parts: ['기본기는 갖춤', '', '', '인강 의존도가 높음'], rest: '1회차에 자세한 상담 예정' })
    expect(parseSlots(GOAL_SLOTS, '수1 완강, 오답노트 습관')).toEqual({ parts: ['', '', '', ''], rest: '수1 완강, 오답노트 습관' })   // 머리말 없는 예전 글
    expect(toCircled('(1) 완강\n(2) 1회독\n그 밖의 글')).toBe('① 완강\n② 1회독\n그 밖의 글')
  })

  it('배분한 강의를 온라인 강의 칸의 글로 쓴다', () => {
    const courses = [{ lecture: '새기분', instructor: '가상 강사' }, { lecture: '문학 개념', instructor: '' }]
    // 번호가 있는 목차는 몇 강인지만
    // 강의 제목 뒤에 목차에서 몇 번째 강인지를 괄호로. 제목에 적힌 번호가 아니라 순서(order)다
    expect(onlineText([{ no: 3, title: '로그' }, { no: 4, title: '삼각함수' }], courses, courseName)).toEqual({ online: '로그, 삼각함수 (3~4강)', course: 0 })
    expect(onlineText([{ no: 1, title: '지수', order: 1 }, { no: 1, title: '지수2', order: 2 }], courses, courseName).online).toBe('지수, 지수2 (1~2강)')
    // 제목이 제각각인 목차는 제목 뒤에 몇 강인지 괄호로
    expect(onlineText([{ no: 2, title: 'Hard Core.1ㅣ057', auto_no: true }, { no: 3, title: 'Hard Core.1ㅣ058', auto_no: true }], courses, courseName).online)
      .toBe('Hard Core.1ㅣ057, Hard Core.1ㅣ058 (2~3강)')
    // 한 주에 강좌가 바뀌면 둘째 강좌는 이름을 붙인다
    expect(onlineText([{ no: 30, title: 'a', course: 0 }, { no: 1, title: 'b', course: 1 }], courses, courseName)).toEqual({ online: 'a (30강) / 문학 개념, b (1강)', course: 0 })
    expect(onlineText([], courses, courseName)).toEqual({ online: '', course: 0 })
    // 주차마다 그 주의 강좌 이름이 붙는다
    expect(curriculumCell({ course: 1, online: '1~2강', mentoring: '시의 화자' }, courses)).toBe('(온라인강의) 문학 개념, 1~2강\n(멘토링 내용) 시의 화자')
    expect(curriculumCell({ online: '3강', mentoring: '로그' }, courses)).toBe('(온라인강의) 새기분(가상 강사), 3강\n(멘토링 내용) 로그')
  })

  it('멘티 설정에는 회차 수·목표·학습 상황 칸이 없고, 메뉴에는 이름 아래 줄에 상세 정보가 나온다', () => {
    const keys = PROFILE_FIELDS.map((f) => f.key)
    for (const k of ['totalRounds', 'goal', 'level']) expect(keys).not.toContain(k)
    expect(menteeFacts({ grade: '고1', subject: '수학', district: '성동구', mode: '오프라인' })).toBe('고1 · 수학 · 성동구 · 오프라인')
    expect(menteeFacts({ subject: '기타', subjectEtc: '검정고시' })).toBe('검정고시')
  })

  it('추천받은 강 번호를 범위로 쓴다', () => {
    expect(lectureRange([{ no: 3 }, { no: 4 }])).toBe('3~4강')
    expect(lectureRange([{ no: 7 }])).toBe('7강')
    expect(lectureRange([{ no: null }])).toBe('')
  })
})

describe('인계 요약을 글로 주고받기', () => {
  const summary = { attendance_pattern: '대체로 정시에 출석함.', homework_pattern: '단어 과제를 자주 덜 해 옴.', attitude: '', course_progress: '8강까지 수강함. 다음은 9강.' }

  it('복사한 글을 붙여 넣으면 같은 내용으로 되돌아온다', () => {
    const text = handoverText({ ...summary, weak_units: '관계대명사', memo: '성적 3등급' })   // 허용 항목이 아닌 것은 글에 넣지 않는다
    expect(text).toBe('[출석 패턴] 대체로 정시에 출석함.\n[과제 수행] 단어 과제를 자주 덜 해 옴.\n[수강 강의와 진도] 8강까지 수강함. 다음은 9강.')
    expect(parseHandoverText(text)).toEqual({ found: { attendance_pattern: summary.attendance_pattern, homework_pattern: summary.homework_pattern, course_progress: summary.course_progress }, dropped: 0 })
  })

  it('허용된 네 항목만 받고 나머지는 버린다', () => {
    const r = parseHandoverText('안녕하세요, 인계 내용입니다.\n[출석패턴] 정시 출석\n[학업 수준] 수학 4등급\n[학습 태도] 질문을\n많이 함\n[상담 내용] 가정 사정이 있음')
    expect(r.found).toEqual({ attendance_pattern: '정시 출석', attitude: '질문을 많이 함' })
    expect(r.dropped).toBe(3)
    // 서버가 개인정보를 가리며 넣은 표시에서는 글이 잘리지 않는다. 한 줄에 이어 쓴 허용되지 않은 항목은 그래도 버린다
    expect(parseHandoverText('[출석 패턴] 대체로 정시 출석함. [학교명] 시험 기간에 지각 2회.').found.attendance_pattern).toBe('대체로 정시 출석함. [학교명] 시험 기간에 지각 2회.')
    expect(parseHandoverText('[출석 패턴] 정시 출석 [학업 수준] 수학 4등급 [상담 내용] 가정 사정이 있음')).toEqual({ found: { attendance_pattern: '정시 출석' }, dropped: 2 })
    expect(parseHandoverText('항목 이름 없이 쓴 글')).toEqual({ found: {}, dropped: 1 })
    expect(parseHandoverText('')).toEqual({ found: {}, dropped: 0 })
  })
})

describe('바뀐 줄 찾기와 서버가 거른 글 되넣기', () => {
  it('서로 다른 줄만 전·후로 찾고, 돌아온 줄을 칸에 다시 넣는다', () => {
    expect(changedLines('가\n나', '가\n다')).toEqual([['나', '다']])
    expect(changedLines('', '새 글')).toEqual([['', '새 글']])
    expect(changedLines('같음', '같음')).toEqual([])
  })
  it('지난 회기 요약에 다음 회기 강좌를 남긴다', () => {
    expect(termSummary([], { term: 1, course: '가 강좌' }, ' 나 강좌 ').next_course).toBe('나 강좌')
    expect(termSummaryText({ term: 1, rounds: 0, next_course: '나 강좌' })).toContain('이번 회기에 들을 강좌: 나 강좌')
  })
})

describe('종합계획서②를 서식 파일에 채운다 (브라우저 안에서만)', () => {
  const data = (n) => ({ period: '2026.11.02.~2027.02.15.', mentee: '김가상 (고1)', mentor: '이멘토 (가상대)', subject_time: '수학 / 가 강좌 / 매주 월', course: '가 강좌',
    goal: ['① 완강', '② 3등급'], diagnosis: ['(과목역량) 기본 & 응용 <확인>'], structure: ['17:00~17:10 확인'], rules: ['시간 지키기'],
    weeks: Array.from({ length: n }, (_, i) => [`(온라인강의) 가 강좌, ${i + 1}강`, `(멘토링 내용) ${i + 1}주차`]) })
  // 서식과 같은 뼈대의 작은 파일: 제목, 기간, 멘티·멘토, 과목, 목표, 진단, 커리큘럼 3줄(세로로 합친 칸), 구성, 규칙
  const WP = (t, color = '0000FF') => `<w:p><w:pPr><w:jc w:val="left"/></w:pPr><w:r><w:rPr><w:color w:val="${color}"/></w:rPr><w:t>${t}</w:t></w:r></w:p>`
  const WC = (t, extra = '') => `<w:tc><w:tcPr>${extra}</w:tcPr>${t ? WP(t) : '<w:p/>'}</w:tc>`
  const docx = () => {
    const row = (label, ...cells) => `<w:tr>${WC(label)}${cells.map((c) => WC(c)).join('')}</w:tr>`
    const cur = [0, 1, 2].map((i) => `<w:tr>${WC(i ? '' : '커리큘럼', i ? '<w:vMerge/>' : '<w:vMerge w:val="restart"/>')}${WC(`예시 ${i}`)}</w:tr>`).join('')
    const body = row('멘토링 종합 계획서 작성예시') + row('멘토링기간', 'YYYY') + row('멘 티', '이○○', '멘 토', '김○○') + row('멘토링 과목 및 시간', '예시') + row('멘티 학습목표', '예시')
      + row('학생진단', '예시') + cur + row('멘토링 구성', '예시') + row('활동규칙', '예시')
    return zipSync({ 'word/document.xml': strToU8(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl>${body}</w:tbl></w:body></w:document>`) })
  }
  const hwpx = () => {
    const HC = (t, row, col, span = 1) => `<hp:tc><hp:subList><hp:p id="0"><hp:run charPrIDRef="${col ? 15 : 14}"><hp:t>${t}</hp:t></hp:run><hp:linesegarray><hp:lineseg textpos="0"/></hp:linesegarray></hp:p></hp:subList><hp:cellAddr colAddr="${col}" rowAddr="${row}"/><hp:cellSpan colSpan="1" rowSpan="${span}"/><hp:cellSz width="10" height="100"/></hp:tc>`
    const labels = ['멘토링 종합 계획서 작성예시', '멘토링기간', '멘 티', '멘토링 과목 및 시간', '멘티학습목표', '멘티진단']
    let body = labels.map((l, r) => `<hp:tr>${HC(l, r, 0)}${r === 2 ? HC('이○○', r, 1) + HC('멘 토', r, 2) + HC('김○○', r, 3) : r ? HC('예시', r, 1) : ''}</hp:tr>`).join('')
    body += `<hp:tr>${HC('커리큘럼', 6, 0, 3)}${HC('예시', 6, 1)}</hp:tr><hp:tr>${HC('예시', 7, 1)}</hp:tr><hp:tr>${HC('예시', 8, 1)}</hp:tr>`
    body += `<hp:tr>${HC('멘토링 구성', 9, 0)}${HC('예시', 9, 1)}</hp:tr><hp:tr>${HC('활동규칙', 10, 0)}${HC('예시', 10, 1)}</hp:tr>`
    const ns = 'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"'
    return zipSync({ mimetype: strToU8('application/hwp+zip'),
      'Contents/header.xml': strToU8('<hh:charPr id="14" height="1000" textColor="#000000"/><hh:charPr id="15" height="1000" textColor="#0000FF"/>'),
      'Contents/section0.xml': strToU8(`<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hs:sec ${ns}><hp:p id="1"><hp:run charPrIDRef="14"><hp:tbl rowCnt="11"><hp:sz width="10" height="1100"/>${body}</hp:tbl></hp:run></hp:p></hs:sec>`),
      'Preview/PrvText.txt': strToU8('예시 글') })
  }

  it('docx: 칸 이름으로 찾아 채우고, 예시의 파란 글자를 검게, 남는 커리큘럼 줄은 지운다', () => {
    const xml = strFromU8(unzipSync(fillPlanFile(docx(), data(2)))['word/document.xml'])
    expect(xml.startsWith('<?xml')).toBe(true)
    const texts = [...xml.matchAll(/<w:t[^>]*>([^<]*)<\/w:t>/g)].map((m) => m[1])
    expect(texts).toEqual(['「서울런 멘토단」 멘토링 종합 계획서', '멘토링기간', '2026.11.02.~2027.02.15.', '멘 티', '김가상 (고1)', '멘 토', '이멘토 (가상대)', '멘토링 과목 및 시간', '수학 / 가 강좌 / 매주 월',
      '멘티 학습목표', '① 완강', '② 3등급', '학생진단', '(과목역량) 기본 &amp; 응용 &lt;확인&gt;', '커리큘럼', '가 강좌', '(온라인강의) 가 강좌, 1강', '(멘토링 내용) 1주차', '(온라인강의) 가 강좌, 2강', '(멘토링 내용) 2주차',
      '멘토링 구성', '17:00~17:10 확인', '활동규칙', '시간 지키기'])
    expect(xml.match(/<w:tr>/g)).toHaveLength(10)   // 커리큘럼 3줄 가운데 한 줄을 지웠다
    expect(xml).not.toContain('예시')
    // 채운 글은 검은색, 손대지 않은 칸 이름은 그대로
    expect(xml).toContain('<w:color w:val="000000"/></w:rPr><w:t xml:space="preserve">① 완강</w:t>')
  })

  it('hwpx: 채우고, 줄을 지우면 줄 번호·줄 수·합친 칸을 맞추고, mimetype을 맨 앞에 압축 없이 둔다', () => {
    const out = fillPlanFile(hwpx(), data(2))
    const files = unzipSync(out)
    expect(Object.keys(files)[0]).toBe('mimetype')
    expect(strFromU8(out.slice(30, 38))).toBe('mimetype')   // 압축하지 않은 첫 항목
    expect(strFromU8(files['Preview/PrvText.txt'])).toBe('')
    const xml = strFromU8(files['Contents/section0.xml'])
    expect(xml).toContain('rowCnt="10"')
    expect(xml).toContain('rowSpan="2"')
    expect([...xml.matchAll(/<hp:tr>.*?rowAddr="(\d+)"/g)].map((m) => m[1])).toEqual(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'])
    expect(xml).toContain('<hp:run charPrIDRef="14"><hp:t>(멘토링 내용) 2주차</hp:t></hp:run></hp:p>')   // 검은 글자 모양, 줄 배치 정보 없음
    expect(xml).toContain('<hp:t>(과목역량) 기본 &amp; 응용 &lt;확인&gt;</hp:t>')
    expect(xml).not.toContain('예시')
    expect(xml).toContain('<hp:sz width="10" height="1000"/>')   // 지운 줄의 높이만큼 줄인다
  })

  it('다른 파일은 까닭을 알려 주고, 파일 이름은 서식 규칙을 따른다', () => {
    expect(() => fillPlanFile(strToU8('hwp 같은 다른 형식'), data(1))).toThrow('hwp 파일은 채울 수 없습니다')
    expect(() => fillPlanFile(zipSync({ 'a.txt': strToU8('x') }), data(1))).toThrow('docx 또는 hwpx')
    expect(() => fillPlanFile(zipSync({ 'word/document.xml': strToU8('<w:document xmlns:w="w"><w:tbl><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl></w:document>') }), data(1))).toThrow('종합활동계획서 서식이 아닌')
    expect(planFileName('hwpx', { code: 'M12', term: 2, mentee: '김가상' })).toBe('[M12]2회기_종합활동계획서_김가상.hwpx')
    expect(planFileName('docx', {})).toBe('[멘토코드]1회기_종합활동계획서_멘티이름.docx')
    // 멘토코드는 이름 + 전화번호 뒤 네 자리
    expect(mentorCode('이멘토', '010-1234-5678')).toBe('이멘토5678')
    expect(mentorCode('이멘토', '')).toBe('')
    expect(mentorCode('', '010-1234-5678')).toBe('')
  })
})

describe('활동보고서: 플랫폼 입력 칸과 규칙', () => {
  it('학습 진도는 출결·인강·과제 줄로 만든다 (활동가이드의 필수 기재 사항, AI 미사용)', () => {
    const what = { lecture: '지수 (5~6강)', task: '5강 예제 풀기' }
    expect(progressLines({ status: '출석', time: '17:02~18:04', lecture: '함', task: '안 함', what })).toEqual(
      ['출결: 정시 출석 (17:02~18:04)', '인강: 지수 (5~6강) 수강함', '과제: 5강 예제 풀기 - 수행하지 않음'])
    expect(progressLines({ status: '지각', time: '', lecture: '', task: '' })).toEqual(['출결: 지각', '', ''])
    expect(progressLines({ status: '출석', time: '', lecture: '안 함', task: '함' })).toEqual(['출결: 정시 출석', '인강: 수강하지 않음', '과제: 수행함'])
  })
  it('고른 것을 바꾸면 규칙으로 넣은 줄만 바뀌고, 멘토가 고치거나 덧붙인 줄은 그대로다', () => {
    const a = ['출결: 정시 출석', '', '']
    const b = ['출결: 정시 출석', '인강: 수강함', '']
    const c = ['출결: 정시 출석', '인강: 수강함', '과제: 수행하지 않음']
    expect(syncLines('', ['', '', ''], a)).toBe('출결: 정시 출석')
    expect(syncLines('출결: 정시 출석\n개선 방향: 복습 시간 늘리기', a, b)).toBe('출결: 정시 출석\n인강: 수강함\n개선 방향: 복습 시간 늘리기')
    // 멘토가 인강 줄을 고쳤다: 그 줄은 두고 과제 줄만 더한다
    expect(syncLines('출결: 정시 출석\n인강: 5강만 들음', b, c)).toBe('출결: 정시 출석\n인강: 5강만 들음\n과제: 수행하지 않음')
    // 고르지 않은 상태로 되돌리면 그 줄을 뺀다
    expect(syncLines('출결: 정시 출석\n인강: 수강함', b, a)).toBe('출결: 정시 출석')
  })
  it("'이번 주차 학습 내용'은 종합계획서의 그 주차 계획을 학습범위·학습목표 두 줄로 가져온다", () => {
    const pre = { formId: 'plan_initial', savedAt: '1', extra: { rows: [{ week: 2, content: '지수법칙' }] } }
    const file = { formId: 'plan_file', savedAt: '2', extra: { courses: [{ platform: '가상스터디', lecture: '가 강좌', instructor: '나' }], rows: [{ week: 2, online: '지수 (3~4강)', mentoring: '지수법칙 개념' }] } }
    expect(plannedWeek([pre], 2)).toEqual({ row: { week: 2, content: '지수법칙' }, course: '', platform: '' })
    expect(contentAuto(plannedWeek([pre], 2).row)).toBe('학습범위: 지수법칙')
    const w = plannedWeek([pre, file], 2)
    expect(contentAuto(w.row, w.course)).toBe('학습범위: 가 강좌(나), 지수 (3~4강)\n학습목표: 지수법칙 개념')
    expect(w.platform).toBe('가상스터디')   // 학습 진도의 인강 줄에 학습사이트와 강좌 이름을 함께 적는다
    expect(plannedWeek([pre, file], 5)).toBeNull()
    expect(contentAuto(null)).toBe('')
  })
  it("다음 회차까지 낸 과제는 학습 이해도에 '과제:' 줄로 적었을 때만 불러온다 (선택)", () => {
    const text = '1. 예습이 되어 개념 설명을 잘 이해함. 못 들은 강의는 과제로 냄.\n계산 실수가 잦음\n과제: 개념원리 중1 RPM 10~23p 풀기\n인강: 메가스터디, 수학의 시작 3~4강'
    expect(assignedLines(text)).toEqual({ lecture: '메가스터디, 수학의 시작 3~4강', task: '개념원리 중1 RPM 10~23p 풀기' })
    expect(assignedLines('개념을 잘 이해함. 숙제로 3강 예제를 냄')).toEqual({ lecture: '', task: '' })
    const prev = (t) => ({ formId: 'activity_report', sessionNo: 2, savedAt: '1', extra: { sheet: { understanding: [t] } } })
    expect(previousHomework([prev(text)], 3, {})).toEqual({ lecture: '메가스터디, 수학의 시작 3~4강', task: '개념원리 중1 RPM 10~23p 풀기' })
    expect(previousHomework([prev('개념을 잘 이해함')], 3, {})).toBeNull()
    expect(progressLines({ status: '출석', time: '', lecture: '함', task: '함', what: previousHomework([prev(text)], 3, {}) }).slice(1))
      .toEqual(['인강: 메가스터디, 수학의 시작 3~4강 수강함', '과제: 개념원리 중1 RPM 10~23p 풀기 - 수행함'])
  })
  it('서버와는 줄마다 칸 이름표를 붙여 주고받고, 돌아온 줄을 칸에 다시 넣는다', () => {
    const text = toLines([['u0', '예제는 혼자 품\n\n풀이 과정 건너뜀'], ['u1', ''], ['e', '화면 끊김']])
    expect(text).toBe('(u0) 예제는 혼자 품\n(u0) 풀이 과정 건너뜀\n(e) 화면 끊김')
    expect(fromLines('(u0) 예제를 혼자 풂\n(u0) 풀이 과정을 건너뜀\n이름표 없는 줄\n(e) ')).toEqual({ u0: ['예제를 혼자 풂', '풀이 과정을 건너뜀'] })
    // 줄 수가 같으면 빈 줄을 지키고, 통째로 빠진 줄이 있으면 돌아온 줄만 남긴다
    expect(applyLines('예제는 혼자 품\n\n풀이 과정 건너뜀', ['예제를 혼자 풂', '풀이 과정을 건너뜀'])).toBe('예제를 혼자 풂\n\n풀이 과정을 건너뜀')
    expect(applyLines('예제는 혼자 품\n부모님과 다퉈 속상해함', ['예제를 혼자 풂'])).toBe('예제를 혼자 풂')
    expect(applyLines('속상해함', undefined)).toBe('')
  })
  it('시간확대는 전반·후반으로 나누고, 예전 화면의 세 칸 값은 한 칸의 글로 읽는다', () => {
    expect(halvesOf('120')).toEqual(['전반 1시간 ', '후반 1시간 '])
    expect(halvesOf('60')).toEqual([''])
    expect(boxText({ good: '예제를 혼자 풂', lacking: '', improve: '풀이 과정\n끝까지 쓰기' })).toBe('잘한 점: 예제를 혼자 풂\n개선 방향: 풀이 과정 끝까지 쓰기')
    expect(boxText('그대로')).toBe('그대로')
    expect(boxText(undefined)).toBe('')
    expect(absentText('무단결석')).toContain('무단결석으로 멘토링을 진행하지 못함')
    expect(absentText('임박취소')).toContain('임박취소로 멘토링을 진행하지 못함')
    expect(absentText('출석')).toBe('')
    // 임박취소는 온라인 멘토링에만 있다
    expect(statusesOf('온라인')).toContain('임박취소')
    expect(statusesOf('오프라인')).not.toContain('임박취소')
  })
})

describe('활동비 계산: 저장한 활동보고서로 한 달치 입력을 만든다', () => {
  const mentees = [
    { alias: 'a', profile: { name: '김가상', mode: '온라인', duration: '120', course: '메가스터디 시발점 수1' },
      reports: [{ session_date: '2026-10-05', status: '출석' }, { session_date: '2026-10-12', status: '지각' }, { session_date: '2026-10-19', status: '무단결석' }, { session_date: '2026-10-26', status: '임박취소' }, { session_date: '2026-11-02' }] },
    { alias: 'b', profile: { name: '', mode: '오프라인', duration: '60', course: '밀크T 중3 영어' }, reports: [{ session_date: '2026-10-07', status: '인정결석' }, { session_date: '2026-10-14', status: '출석' }] },
    { alias: 'c', profile: { name: '박가상', mode: '온라인', duration: '60', course: '' }, reports: [{ session_date: '2026-09-30', status: '출석' }] },
  ]
  it('달마다 멘티별 회차 수를 상태로 나눠 센다', () => {
    expect(reportMonths(mentees)).toEqual(['2026-11', '2026-10', '2026-09'])
    expect(monthRows(mentees, '2026-10')).toEqual([
      { alias: 'a', name: '김가상', mode: '온라인', hours: 2, normal: 2, no_show: 1, late_cancel: 1, excused: 0, senior: true, sessions: 4 },
      { alias: 'b', name: 'b', mode: '오프라인', hours: 1, normal: 1, no_show: 0, late_cancel: 0, excused: 1, senior: false, sessions: 2 },
    ])
    expect(monthRows(mentees, '2026-12')).toEqual([])
  })
  it('고학년지도 가산금은 학습사이트로 짐작한다 (검정고시 과정과 중등 사이트는 아니다)', () => {
    for (const c of ['메가스터디 시발점', '이투스 수학', '대성마이맥 국어', '밀크T 고등 영어']) expect(isSeniorCourse(c), c).toBe(true)
    for (const c of ['밀크T 중3 영어', '에듀윌 검정고시 고등', '메가스터디 검정고시', '', undefined]) expect(isSeniorCourse(c), String(c)).toBe(false)
  })
  it('활동비는 다음 달 20일에 지급된다', () => {
    expect(payInfo('2026-10')).toEqual({ month: 10, payMonth: 11 })
    expect(payInfo('2026-12')).toEqual({ month: 12, payMonth: 1 })
  })
})

describe('교과과정으로 채우기 (자료와 규칙만 사용)', () => {
  it('자료 파일의 모양이 맞다: 12개 학년, 과목마다 단원을 찾을 방법이 하나씩 있다', () => {
    expect(Object.keys(curriculum.grades)).toEqual(GRADES)
    for (const [g, v] of Object.entries(curriculum.grades)) {
      expect(v.label && v.curriculum, g).toBeTruthy()
      for (const [name, s] of Object.entries(v.subjects)) {
        const kinds = ['none', 'terms', 'year', 'courses'].filter((k) => k in s)
        expect(kinds, `${g} ${name}`).toHaveLength(1)
        if (s.terms) expect(Object.keys(s.terms)).toEqual(['1학기', '2학기'])
        if (s.year) expect(['half', 'whole']).toContain(s.split)
        if (!s.none) expect(Object.keys(curriculum.levels)).toContain(s.level)
        const lists = s.terms ? Object.values(s.terms) : s.year ? [s.year] : s.courses ? Object.values(s.courses) : []
        lists.push(...Object.values(s.extra || {}))
        if (s.courses) for (const o of s.others || []) expect(Object.keys(s.courses), `${g} ${name}`).not.toContain(o)
        for (const list of lists) expect(list.every((u) => typeof u === 'string' && u.trim()), `${g} ${name}`).toBe(true)
      }
    }
    // 초3부터 고1까지는 다섯 과목 모두 무엇인가 채울 수 있다 (사회는 과목을 골라야 하는 학년이 있다)
    for (const g of GRADES.slice(2, 10)) for (const subject of CURRICULUM_SUBJECTS) {
      const f = findUnits(curriculum, g, '1학기', subject)
      expect(f.units.length || f.courses.length, `${g} ${subject}`).toBeGreaterThan(0)
    }
  })

  it('학년·학기·과목으로 단원을 찾는다', () => {
    expect(findUnits(curriculum, '초5', '2학기', '수학').units[0]).toBe('1. 수의 범위와 올림, 버림, 반올림')
    expect(findUnits(curriculum, '중2', '1학기', '수학').units).toEqual(['수와 식(유리수와 순환소수, 단항식·다항식의 계산)', '일차부등식', '연립일차방정식', '일차함수와 그래프, 일차함수와 일차방정식의 관계'])
    expect(findUnits(curriculum, '고1', '2학기', '수학')).toMatchObject({ name: '공통수학2', units: ['도형의 방정식(평면좌표, 직선, 원, 도형의 이동)', '집합과 명제', '함수와 그래프(함수, 유리함수와 무리함수)'] })
    // 한 해 단위로 정리된 영어는 앞뒤 절반으로 나눈다
    expect(findUnits(curriculum, '중1', '1학기', '영어').units).toHaveLength(5)
    expect(findUnits(curriculum, '중1', '2학기', '영어').units[0]).toBe('감탄문')
    // 영역별로 정리된 중등 국어는 학기 구분 없이 통째로
    expect(findUnits(curriculum, '중1', '2학기', '국어').units).toHaveLength(13)
    // 초1~2의 사회·과학은 통합교과, 영어는 없다
    expect(findUnits(curriculum, '초1', '1학기', '사회')).toMatchObject({ name: '통합교과', units: ['학교', '사람들', '우리나라', '탐험'] })
    expect(findUnits(curriculum, '초2', '1학기', '영어')).toMatchObject({ units: [], notes: ['영어는 초등학교 3학년부터 배웁니다.'] })
  })

  it('선택과목이 갈리는 학년은 배우는 과목을 골라야 단원이 나온다', () => {
    const ask = findUnits(curriculum, '고2', '1학기', '수학')
    expect(ask).toMatchObject({ units: [], courses: ['대수', '미적분Ⅰ', '확률과 통계', '미적분Ⅱ', '기하'] })
    expect(findUnits(curriculum, '고2', '1학기', '과학', '화학').units).toEqual(['화학의 언어', '물질의 구조와 성질', '화학 평형', '역동적인 화학 반응'])
    expect(findUnits(curriculum, '고3', '1학기', '사회', '한국지리').units).toHaveLength(7)
    // 역사는 사회 아래의 세부 과목이다. 학기별 단원이 있는 학년은 고르지 않으면 원래 과목이 나온다
    expect(findUnits(curriculum, '중2', '1학기', '사회', '역사①').units).toHaveLength(7)
    expect(findUnits(curriculum, '고1', '1학기', '사회')).toMatchObject({ name: '통합사회1', basic: '통합사회1', courses: ['한국사1', '한국사2'] })
    expect(findUnits(curriculum, '고1', '1학기', '사회').units.length).toBeGreaterThan(0)
    expect(findUnits(curriculum, '고1', '1학기', '사회', '한국사2')).toMatchObject({ name: '한국사2', units: ['일제 식민 통치와 민족운동', '대한민국의 발전', '오늘날의 대한민국'] })
    expect(findUnits(curriculum, '중3', '2학기', '사회', '역사②').units[0]).toBe('선사 문화와 고대 국가의 형성')
    expect(findUnits(curriculum, '고2', '1학기', '수학', '대수')).toMatchObject({ name: '대수', units: ['지수와 로그', '지수함수와 로그함수', '삼각함수', '수열'] })
    expect(findUnits(curriculum, '중1', '1학기', '사회', '지리').units).toHaveLength(6)
    // 단원 자료가 없는 과목은 채우지 않고 까닭을 알려 준다 (지어내지 않는다)
    expect(findUnits(curriculum, '고2', '1학기', '국어').courses).toEqual(['문학', '독서와 작문', '화법과 언어'])
    expect(findUnits(curriculum, '고2', '1학기', '영어', '영어Ⅰ').units).toHaveLength(7)
    expect(findUnits(curriculum, '고3', '1학기', '사회', '한국사').units).toHaveLength(4)
    expect(findUnits(curriculum, '고1', '1학기', '기타').notes.join(' ')).toContain('교육과정 자료가 없습니다')
    expect(findUnits(curriculum, '', '1학기', '수학').units).toEqual([])
    expect(findUnits(null, '중2', '1학기', '수학').units).toEqual([])
  })

  it('16주는 진단 1주와 복습 2주를 빼고, 8주는 첫 주와 마지막 주를 빼고 단원을 나눈다', () => {
    expect(weekFrame(16, true).slots).toEqual([1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14])
    expect(weekFrame(8).slots).toEqual([1, 2, 3, 4, 5, 6])
    const six = ['1. 가', '2. 나', '3. 다', '4. 라', '5. 마', '6. 바']
    const rows = spreadUnits(six, 16, true)
    expect(rows).toHaveLength(16)
    expect([rows[0], rows[8], rows[15]]).toEqual([FIRST_WEEK, '앞 단원 복습과 시험 대비', `${LAST_WEEK}와 시험 대비`])
    expect(rows.slice(1, 4)).toEqual(['1. 가 - 개념', '1. 가 - 문제 풀이', '1. 가 - 정리'])     // 13주에 6단원: 첫 단원만 3주
    expect(rows.slice(4, 6)).toEqual(['2. 나 - 개념', '2. 나 - 문제 풀이'])
    expect(rows[14]).toBe('6. 바 - 문제 풀이')
    expect(spreadUnits(six, 16, false)[8]).toBe('앞 단원 복습')                                   // 초등은 시험 대비라고 쓰지 않는다
    expect(spreadUnits(six, 8)).toEqual([FIRST_WEEK, ...six, LAST_WEEK])                          // 8주: 한 주에 한 단원
    // 단원이 주차보다 많으면 한 주에 여러 단원
    const many = spreadUnits(Array.from({ length: 13 }, (_, i) => `요소${i + 1}`), 8)
    expect(many[1]).toBe('요소1 / 요소2 / 요소3')
    expect(many[6]).toBe('요소12 / 요소13')
    // 단원이 아주 적으면 번호로
    expect(spreadUnits(['1. 우리가 사는 곳', '2. 일상에서 만나는 과거'], 16)[1]).toBe('1. 우리가 사는 곳 (1/7)')
    expect(spreadUnits([], 16)).toEqual([])
  })

  it('채운 글은 플랫폼에 그대로 옮길 수 있게 특수문자를 정리한다', () => {
    const rows = spreadUnits(findUnits(curriculum, '초4', '1학기', '영어').units, 8)
    expect(rows[1]).toBe('시각, 요일, 날씨 묻고 답하기 - 개념')     // 가운뎃점은 쉼표로 (6주에 4단원: 앞의 두 단원은 2주씩)
    expect(rows[5]).toBe('소유 묻기(Whose ~)')                     // 물음표는 뺀다
    expect(platformSafe('① 수학Ⅱ & 퀴즈! (일제강점기~6·25)\n만나서 반가워요!')).toBe('(1) 수학2 퀴즈 (일제강점기~6.25)\n만나서 반가워요')
    expect(platformSafe('17:00~17:10 온라인 강의 수강(필수) 확인 및 퀴즈')).toBe('17:00~17:10 온라인 강의 수강(필수) 확인 및 퀴즈')   // 이미 안전한 글은 그대로
    expect(platformSafe('• 시간 지키기\n• 과제 하기')).toBe('시간 지키기\n과제 하기')   // 줄 머리의 글머리 기호는 떼고 줄은 지킨다
  })

  it('학년 글을 알아듣고, 자료가 없을 때의 예시는 주차 자리에 맞춘다', () => {
    expect([gradeKey('고1'), gradeKey('중학교 2학년'), gradeKey('초등 5'), gradeKey('초등학교 6학년'), gradeKey('19세'), gradeKey('')]).toEqual(['고1', '중2', '초5', '초6', '', ''])
    expect([hasExams('중2'), hasExams('고3'), hasExams('초6'), hasExams('')]).toEqual([true, true, false, false])
    const hints = genericHints(16, true)
    expect([hints[0], hints[1], hints[2], hints[3], hints[8], hints[15]]).toEqual([FIRST_WEEK, '1단원 개념 학습', '1단원 문제 풀이', '2단원 개념 학습', '앞 단원 복습과 시험 대비', `${LAST_WEEK}와 시험 대비`])
  })
})

describe('인계받은 글', () => {
  it('멘토에게는 붙여 넣은 그대로 보여 주고, AI에는 허용된 네 항목만 넘긴다', () => {
    const text = '안녕하세요.\n[출석 패턴] 정시 출석\n[학업 수준] 수학 4등급'
    const draft = { ...parseHandoverText(text).found, text }
    expect(handoverNote(draft)).toBe(text)
    expect(handoverForDraft(draft)).toEqual({ attendance_pattern: '정시 출석' })
    expect(handoverForDraft({ text: '항목 이름 없이 쓴 글. 성적이 낮음' })).toBeNull()        // 나눌 수 없는 글은 AI에 넘기지 않는다
    expect(handoverNote({ attendance_pattern: '정시 출석', attitude: '성실함' })).toBe('[출석 패턴] 정시 출석\n[학습 태도] 성실함')   // 직접 만든 인계 요약
    expect(handoverNote(null)).toBe('')
  })
})

describe('멘토 설정 (이 브라우저에만 저장)', () => {
  beforeEach(() => localStorage.clear())

  it('바꾼 값만 저장한다', () => {
    saveSettings({ name: ' 이멘토 ', phone: '010-0000-0000', mentoringType: '시급형' })
    saveSettings({ university: '가상대학교' })
    expect(loadSettings()).toEqual({ name: '이멘토', phone: '010-0000-0000', mentoringType: '시급형', university: '가상대학교', major: '' })
  })

  it('자치구별 이음단 카카오톡 채널: 자료의 자치구 이름이 맞고, 카카오톡 채널 주소만 바로가기가 된다', () => {
    const listed = validChannels(channels)
    expect(Object.keys(listed)).toEqual(Object.keys(channels))            // 자료에 다른 주소가 섞여 있지 않다
    for (const d of Object.keys(listed)) expect(DISTRICTS, d).toContain(d)
    expect(Object.keys(listed).length).toBe(25)                           // 서울 25개 자치구 모두
    expect(new Set(Object.values(listed)).size).toBe(Object.keys(listed).length)   // 자치구마다 다른 채널
    expect(validChannels({ 마포구: 'https://pf.kakao.com/_hjmxgn', 가짜구: 'https://example.com/x', 성동구: 'http://pf.kakao.com/_Jihan', 중구: 5 })).toEqual({ 마포구: 'https://pf.kakao.com/_hjmxgn' })
  })
})

import { unzipSync } from 'fflate'
import { photoBase, photoNames, photoZip } from '../src/lib/photos'

describe('인증사진 이름 바꿔 압축하기', () => {
  it("이름은 '멘티이름 N회기 N회차 월.일', 둘째 장부터 (1)을 붙이고 확장자는 그대로 둔다", async () => {
    const base = photoBase('홍길동', 1, 1, '2026-10-11')
    expect(base).toBe('홍길동 1회기 1회차 10.11')
    expect(photoBase('홍길동', 2, 3, '2026-03-09')).toBe('홍길동 2회기 3회차 3.9')
    const files = [new File([new Uint8Array([1, 2])], 'IMG_0001.JPG'), new File([new Uint8Array([3])], 'photo.png'), new File([new Uint8Array([4])], '이름없음')]
    expect(photoNames(base, files)).toEqual(['홍길동 1회기 1회차 10.11.jpg', '홍길동 1회기 1회차 10.11 (1).png', '홍길동 1회기 1회차 10.11 (2).jpg'])
    const out = unzipSync(await photoZip(base, files.slice(0, 2)))
    expect(Object.keys(out)).toEqual(['홍길동 1회기 1회차 10.11.jpg', '홍길동 1회기 1회차 10.11 (1).png'])
    expect([...out['홍길동 1회기 1회차 10.11.jpg']]).toEqual([1, 2])   // 사진 내용은 그대로다
  })
})

import { activitiesFromVault } from '../src/lib/reports'
import { namedZip } from '../src/lib/photos'

describe('친화·성장활동 기록', () => {
  it('완료보고서에는 실제로 적어 둔 활동만, 적은 칸만 넘긴다', () => {
    const items = [{ formId: 'bonding_activity', draft: { type: '성장활동', date: '2026-11-14', goal: '전공 탐색', content: '캠퍼스 방문 계획', actual: '캠퍼스와 학과 건물을 둘러봄', mentor_note: '', mentee_note: '학과가 궁금해짐' } },
      { formId: 'bonding_activity', draft: { type: '친화활동', date: '', content: '', actual: '' } }]
    expect(activitiesFromVault(items)).toEqual([{ 유형: '성장활동', 일자: '2026-11-14', '활동 목표': '전공 탐색', '활동 내용': '캠퍼스와 학과 건물을 둘러봄', '멘티 소감': '학과가 궁금해짐' }])
    expect(activitiesFromVault([])).toEqual([])
  })
  it('증빙사진은 정해 준 이름으로 압축한다', async () => {
    const file = (n) => new File([new Uint8Array([1])], n)
    const out = unzipSync(await namedZip([['활동 시작 인증 사진', file('a.JPG')], ['활동 내용 확인 사진 (1)', file('b.png')], ['활동 내용 확인 사진 (2)', file('c.jpg')], ['활동 종료 인증 사진', file('d.jpg')]]))
    expect(Object.keys(out)).toEqual(['활동 시작 인증 사진.jpg', '활동 내용 확인 사진 (1).png', '활동 내용 확인 사진 (2).jpg', '활동 종료 인증 사진.jpg'])
  })
})
