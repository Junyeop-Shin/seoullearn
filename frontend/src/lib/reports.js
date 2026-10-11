// 보관함 항목 → 완료보고서·인계 요약의 입력(활동보고서 목록). 형식은 docs/vault_format.md 참고.
import { assignedLines, boxText } from './report'

/** 회차 → 그 회차의 활동보고서 항목. 같은 회차가 여러 번 저장돼 있으면 가장 늦게 저장한 것을 쓴다. */
export function latestReports(items) {
  const latest = new Map()
  for (const x of items) {
    if (x.formId !== 'activity_report') continue
    const no = Number(x.sessionNo ?? x.inputs?.session_no)
    if (!no) continue
    const prev = latest.get(no)
    if (!prev || prev.savedAt < x.savedAt) latest.set(no, x)
  }
  return latest
}

/** 같은 멘티의 활동보고서를 회차 순으로. */
export function reportsFromVault(items) {
  return [...latestReports(items).entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([no, x]) => {
      const r = { ...x.inputs, ...x.draft, session_no: no, status: x.inputs?.status || '출석' }
      // 개인정보 칸(자리표시)은 넘기지 않는다
      for (const k of ['mentee_name', 'mentee_grade', 'mentor']) delete r[k]
      return r
    })
}

/** 종합계획서에 적은 학습목표. 종합계획서②가 있으면 그것을, 없으면 ①을 쓴다. */
export function goalsFromVault(items) {
  const pick = (formId) => latestOf(items, formId)?.draft?.learning_goal
  const goal = pick('plan_file') ?? pick('plan_initial')
  if (Array.isArray(goal)) return goal.map((g) => String(g).trim()).filter(Boolean)
  return goal ? String(goal).split('\n').map((g) => g.trim()).filter(Boolean) : []
}

// 같은 양식(handover_summary)에 두 가지를 저장한다. 붙여 넣은 원문(draft.text)이 있으면 이전 멘토에게 인계받은 글이고, 없으면 내가 다음 멘토에게 넘기려고 만든 요약이다.
// 두 화면이 이 기준 하나로 가른다 (지운 글은 text가 빈 글로 남는다: 그래도 인계받은 쪽이다).
const handovers = (items, received) => items.filter((x) => x.formId === 'handover_summary' && (x.draft?.text !== undefined) === received)
  .sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))
/** 이전 멘토에게 인계받아 붙여 넣은 글의 보관함 항목 (없으면 undefined). */
export const receivedHandover = (items) => handovers(items, true)[0]
/** 내가 만든 인계 요약의 보관함 항목 (없으면 undefined). */
export const myHandover = (items) => handovers(items, false)[0]

/** 인계받은 내용 (없으면 null). */
export function handoverFromVault(items) {
  return receivedHandover(items)?.draft ?? null
}

/** 그 양식으로 가장 최근에 저장한 항목 (없으면 undefined). */
export function latestOf(items, formId) {
  return items.filter((x) => x.formId === formId).sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]
}

/** 저장한 계획서의 그 주차 줄 ({week, date, time, content, online, mentoring}). 종합계획서②를 먼저, 없으면 ①을 본다. 없으면 null. */
export function plannedRow(items, round, needContent = false) {
  for (const formId of ['plan_file', 'plan_initial']) {
    const row = (latestOf(items, formId)?.extra?.rows || []).find((r) => Number(r.week) === Number(round))
    if (row && (!needContent || row.content || row.online || row.mentoring)) return row
  }
  return null
}

/** 그 주차에 적어 둔 학습 계획. 내용이 없으면 null. */
export const curriculumRow = (items, round) => plannedRow(items, round, true)

/** 그 주차의 계획 {row, course(그 주차 강좌 이름)}. 종합계획서②에 적은 것이 있으면 그것을, 없으면 ①의 학습 내용을 쓴다. 없으면 null. */
export function plannedWeek(items, round) {
  const file = latestOf(items, 'plan_file')
  const row = (file?.extra?.rows || []).find((r) => Number(r.week) === Number(round))
  if (row && ((row.online || '').trim() || (row.mentoring || '').trim())) {
    const courses = file.extra.courses || []
    const c = courses[row.course || 0] || courses[0]
    return { row, course: courseName(c), platform: (c?.platform || '').trim() }
  }
  const pre = curriculumRow(items, round)
  return pre ? { row: pre, course: '', platform: '' } : null
}

/** 직전 회차에 낸 인강·과제 {lecture, task}. 아무것도 없으면 null.
 * 직전 보고서의 학습 이해도에 '과제: …', '인강: …' 줄로 적어 둔 것을 읽는다 (적는 것은 선택이다).
 * 예전 화면으로 저장한 보고서(extra.assignedHomework)와 진행 중인 멘티를 등록할 때 적은 것(profile.lastHomework)도 읽는다. */
export function previousHomework(items, round, profile) {
  const prev = items.filter((x) => x.formId === 'activity_report' && Number(x.sessionNo ?? x.inputs?.session_no) === Number(round) - 1)
    .sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]
  const old = prev?.extra?.assignedHomework || (prev ? null : profile?.lastHomework)
  const now = assignedLines([].concat(prev?.extra?.sheet?.understanding || []).map(boxText).join('\n'))
  const out = { lecture: now.lecture || (old?.lecture || '').trim(), task: now.task || (old?.task || '').trim() }
  return out.lecture || out.task ? out : null
}

/** 커리큘럼 표 → 계획서에 넣을 줄. 내용이 없는 주차는 뺀다.
 * 종합계획서①(full 아님): 'N주차(일시) 학습 내용' 한 줄.
 * 종합계획서②(full): 'N주차(일시)' 아래에 '(온라인강의) 강좌명(강사명), n강'과 '(멘토링 내용) 학습 내용' 두 줄. course: {lecture, instructor} */
export function curriculumLines(rows, full = false, course = {}) {
  const day = (r) => (r.date ? `(${Number(r.date.slice(5, 7))}/${Number(r.date.slice(8, 10))}${r.time ? ` ${r.time}` : ''})` : '')
  const out = []
  for (const r of rows || []) {
    if (full) {
      if (!(r.online || '').trim() && !(r.mentoring || '').trim()) continue
      out.push(`${r.week}주차${day(r)}\n${curriculumCell(r, course)}`)
    } else if ((r.content || '').trim()) out.push(`${r.week}주차${day(r)} ${r.content.trim()}`)
  }
  return out
}

/** 강좌 이름: '강좌명(강사명)' */
export function courseName(course) {
  return [(course?.lecture || '').trim(), (course?.instructor || '').trim() && `(${course.instructor.trim()})`].filter(Boolean).join('')
}

/** 종합계획서② 커리큘럼 한 칸: '(온라인강의) 강좌명(강사명), n강' 줄바꿈 '(멘토링 내용) 학습 내용'. 이 형식은 바꾸지 않는다.
 * course는 강좌 하나이거나 강좌 목록(그 주차의 row.course번째 강좌를 쓴다). */
export function curriculumCell(row, course = {}) {
  const c = Array.isArray(course) ? course[row.course || 0] || course[0] : course
  const online = [courseName(c), (row.online || '').trim()].filter(Boolean).join(', ')
  return `(온라인강의) ${online || '-'}\n(멘토링 내용) ${(row.mentoring || '').trim() || '-'}`
}

// 인계 요약은 이 네 가지만 주고받는다. 학업 수준(성적·이해도)과 정서·상담 내용은 칸이 없다 (forms/handover_summary.json의 허용 목록)
export const HANDOVER_ITEMS = [['attendance_pattern', '출석 패턴'], ['homework_pattern', '과제 수행'], ['attitude', '학습 태도'], ['course_progress', '수강 강의와 진도']]

/** 인계 요약 → 다음 멘토에게 보낼 글. '[출석 패턴] …' 한 줄씩. */
export function handoverText(summary) {
  return HANDOVER_ITEMS.filter(([k]) => (summary?.[k] || '').trim()).map(([k, label]) => `[${label}] ${summary[k].trim()}`).join('\n')
}

/** 받은 글 → {found: 항목별 글, dropped: 받지 않은 글 조각 수}. '[이름] 내용' 묶음 중 허용된 네 항목만 받고 나머지는 버린다. */
export function parseHandoverText(text) {
  const found = {}
  let dropped = 0
  // [앞글, 이름1, 내용1, 이름2, 내용2, …]. 서버가 개인정보를 가리며 넣은 표시([학교명] 등)는 항목 이름으로 보지 않는다
  const parts = String(text || '').split(/\[(?!(?:이름|학교명|전화번호|이메일|주민등록번호)\])([^\]\n]{1,20})\]/)
  if (parts[0].trim()) dropped += 1
  for (let i = 1; i < parts.length; i += 2) {
    const item = HANDOVER_ITEMS.find(([, label]) => label.replace(/\s/g, '') === parts[i].replace(/\s/g, ''))
    const body = (parts[i + 1] || '').replace(/\s+/g, ' ').trim()
    if (item && body) found[item[0]] = found[item[0]] ? `${found[item[0]]} ${body}` : body
    else if (body) dropped += 1
  }
  return { found, dropped }
}

/** 저장해 둔 인계 내용을 멘토가 읽을 글로. 붙여 넣은 글이 있으면 그대로, 없으면(직접 만든 인계 요약) 항목을 글로 푼다. */
export function handoverNote(draft) {
  return (draft?.text || '').trim() || handoverText(draft)
}

/** AI에 참고 자료로 넘길 인계 내용: 허용된 네 항목만. 붙여 넣은 글 전체는 넘기지 않는다. */
export function handoverForDraft(draft) {
  const out = Object.fromEntries(HANDOVER_ITEMS.map(([k]) => [k, (draft?.[k] || '').trim()]).filter(([, v]) => v))
  return Object.keys(out).length ? out : null
}

// ---- 친화·성장활동 기록: 신청과 결과보고서에 적은 내용을 적어 둔 것 (유형마다 회기에 한 번)
export const BONDING_FORM = 'bonding_activity'
export const BONDING_TYPES = ['친화활동', '성장활동']
/** 완료보고서 초안의 참고 자료로 넘길 활동 기록. 실제 활동 내용을 적은 것만 (신청만 하고 아직 하지 않은 활동은 한 일이 아니다). */
export function activitiesFromVault(items) {
  return BONDING_TYPES.map((t) => items.find((x) => x.formId === BONDING_FORM && x.draft?.type === t)?.draft)
    .filter((d) => d && (d.actual || '').trim())
    .map((d) => Object.fromEntries([['유형', d.type], ['일자', d.date], ['활동 목표', d.goal], ['활동 내용', d.actual], ['멘토 소감', d.mentor_note], ['멘티 소감', d.mentee_note]].filter(([, v]) => (v || '').trim())))
}

// ---- 지난 회기 요약: 다음 회기를 시작할 때 지난 회기의 계획서·활동보고서·완료보고서에서 추려 남긴다 (나머지는 지운다).
// 새 회기의 종합계획서를 쓸 때 참고로 보여 주고, AI로 초안을 채울 때 이어지게 쓰는 재료로 넘긴다. 감성케어·정서 내용은 넣지 않는다.
export const TERM_SUMMARY_FORM = 'term_summary'

/** 이번 회기에 저장한 완료보고서 (없으면 undefined). 지난 회기 것도 보관함에 남아 있다: 회기 요약보다 먼저 저장된 것이 지난 회기 것이다. */
export function currentCompletion(items) {
  const since = latestOf(items, TERM_SUMMARY_FORM)?.savedAt || ''
  return latestOf(items.filter((x) => x.savedAt > since), 'completion_report')
}

export function termSummary(items, profile, nextCourse = '') {
  const reports = reportsFromVault(items)
  const last = reports[reports.length - 1]
  const hw = previousHomework(items, (last?.session_no || 0) + 1, null)   // 마지막 회차에 낸 과제 (따로 적어 둔 것이나 학습 이해도의 과제 문장)
  const completion = currentCompletion(items)?.draft || {}   // 이번 회기에 저장하지 않았으면 비운다 (지난 회기의 완료보고서를 이번 회기 요약에 넣지 않는다)
  // 완료보고서의 칸은 '- 항목' 줄로 된 글이다 (예전 자료는 목록): 줄마다 한 항목으로 읽는다
  const list = (v) => (Array.isArray(v) ? v : String(v || '').split('\n')).map((x) => String(x).replace(/^[-·•]\s*/, '').trim()).filter(Boolean)
  return { term: Number(profile?.term) || 1, rounds: reports.length, course: profile?.course || '', goal: goalsFromVault(items),
    last_scope: last?.scope || '', next_homework: hw,
    content: list(completion.content), achievement: list(completion.achievement), next_course: String(nextCourse || '').trim() }
}

export function termSummaryFromVault(items) {
  return latestOf(items, TERM_SUMMARY_FORM)?.draft || null
}

/** 지난 회기 요약을 멘토가 읽을 글로. */
export function termSummaryText(s) {
  if (!s) return ''
  const hw = s.next_homework && [s.next_homework.lecture, s.next_homework.task].filter(Boolean).join(', ')
  return [`${s.term}회기 (활동보고서 ${s.rounds}건)`, s.course && `수강 강좌: ${s.course}`, s.goal?.length && `학습 목표: ${s.goal.join(' / ')}`,
    s.last_scope && `마지막 회차 학습 범위: ${s.last_scope}`, hw && `마지막에 낸 과제: ${hw}`, s.next_course && `이번 회기에 들을 강좌: ${s.next_course}`,
    s.content?.length && `멘토링 내용: ${s.content.join(' / ')}`, s.achievement?.length && `성취도: ${s.achievement.join(' / ')}`].filter(Boolean).join('\n')
}
