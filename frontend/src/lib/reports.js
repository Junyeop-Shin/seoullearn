// 보관함 항목 → 완료보고서·인계 요약의 입력(활동보고서 목록). 형식은 docs/vault_format.md 참고.

/** 같은 멘티의 활동보고서를 회차 순으로. 같은 회차가 여러 번 저장돼 있으면 가장 늦게 저장한 것을 쓴다. */
export function reportsFromVault(items) {
  const latest = new Map()
  for (const x of items) {
    if (x.formId !== 'activity_report') continue
    const no = Number(x.sessionNo ?? x.inputs?.session_no)
    if (!no) continue
    const prev = latest.get(no)
    if (!prev || prev.savedAt < x.savedAt) latest.set(no, x)
  }
  return [...latest.entries()]
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
  const pick = (formId) =>
    items.filter((x) => x.formId === formId).sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]?.draft?.learning_goal
  const goal = pick('plan_file') ?? pick('plan_initial')
  if (Array.isArray(goal)) return goal.map((g) => String(g).trim()).filter(Boolean)
  return goal ? String(goal).split('\n').map((g) => g.trim()).filter(Boolean) : []
}

/** 가장 최근에 저장한 인계 요약 (없으면 null). */
export function handoverFromVault(items) {
  return items.filter((x) => x.formId === 'handover_summary').sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]?.draft ?? null
}

// 내 강좌: 예전에 강의 목차를 저장해 두던 별칭. 이제 저장하지 않지만(2026-10-11), 보관함에 남아 있는 예전 자료가 멘티 목록에 섞이지 않게 거른다.
export const COURSE_ALIAS = '내 강좌'

/** 보관함 화면에 보여 줄 초안 한 칸의 글. 강의 목록은 '1강 제목'으로 풀어 쓴다. */
export function draftValueText(value) {
  if (Array.isArray(value)) {
    return value.map((v) => (v && typeof v === 'object' ? `${v.no != null ? `${v.no}강 ` : ''}${v.title ?? ''}`.trim() : String(v))).join('\n')
  }
  return value === null || value === undefined ? '' : String(value)
}

const latestOf = (items, formId) => items.filter((x) => x.formId === formId).sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]

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

/** 직전 회차에 낸 과제 ({lecture, task}). 직전 활동보고서에 없으면 멘티 등록 때 적은 것을 쓴다. */
export function previousHomework(items, round, profile) {
  const prev = items.filter((x) => x.formId === 'activity_report' && Number(x.sessionNo ?? x.inputs?.session_no) === Number(round) - 1)
    .sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]
  const hw = prev?.extra?.assignedHomework || (prev ? null : profile?.lastHomework)
  return hw && (hw.lecture || hw.task) ? hw : null
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
  const parts = String(text || '').split(/\[([^\]\n]{1,20})\]/)   // [앞글, 이름1, 내용1, 이름2, 내용2, …]
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

// ---- 지난 회기 요약: 다음 회기를 시작할 때 지난 회기의 계획서·활동보고서·완료보고서에서 추려 남긴다 (나머지는 지운다).
// 새 회기의 종합계획서를 쓸 때 참고로 보여 주고, AI로 다듬을 때 이어지게 쓰는 재료로 넘긴다. 감성케어·정서 내용은 넣지 않는다.
export const TERM_SUMMARY_FORM = 'term_summary'

export function termSummary(items, profile, nextCourse = '') {
  const reports = reportsFromVault(items)
  const last = reports[reports.length - 1]
  const lastItem = items.filter((x) => x.formId === 'activity_report').sort((a, b) => Number(b.sessionNo) - Number(a.sessionNo))[0]
  const completion = latestOf(items, 'completion_report')?.draft || {}
  const list = (v) => (Array.isArray(v) ? v : v ? [v] : []).map((x) => String(x).trim()).filter(Boolean)
  return { term: Number(profile?.term) || 1, rounds: reports.length, course: profile?.course || '', goal: goalsFromVault(items),
    last_scope: last?.scope || '', next_homework: lastItem?.extra?.assignedHomework || null,
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
    s.content?.length && `멘토링 내용: ${s.content.join(' ')}`, s.achievement?.length && `성취도: ${s.achievement.join(' ')}`].filter(Boolean).join('\n')
}
