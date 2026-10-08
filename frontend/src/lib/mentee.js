// 멘티 정보: 한 번 적어 두면 보고서와 계획서에 다시 입력하지 않게 하는 자료. 이 브라우저 보관함에만 저장한다.
// 이름, 학년, 학교, 연락처는 칸이 없다 (별칭으로만 구분한다).
export const PROFILE_FORM = 'mentee_profile'
const CURRENT_KEY = 'seoullearn.currentMentee.v1'

export const PROFILE_FIELDS = [
  { key: 'subject', label: '멘토링 과목', control: 'text', example: '수학' },
  { key: 'mode', label: '멘토링 유형', control: 'select', options: ['온라인', '오프라인'] },
  { key: 'course', label: '학습사이트와 수강 강좌', control: 'text', example: '메가스터디 수학의 시작, 시발점 - 수1', wide: true },
  { key: 'duration', label: '멘토링 시간(분)', control: 'select', options: ['60', '120'], help: '120분은 시간확대 승인을 받은 그룹만 해당합니다.' },
  { key: 'weekday', label: '학습 요일', control: 'select', options: ['월', '화', '수', '목', '금', '토', '일'] },
  { key: 'start_datetime', label: '1회차 일시', control: 'datetime-local', help: '회차 번호와 날짜를 자동으로 채우는 기준입니다.' },
  { key: 'goal', label: '이번 회기 목표', control: 'textarea', help: '멘티가 말한 목표를 적어 주세요. 종합계획서 초안의 재료가 됩니다.', wide: true },
  { key: 'level', label: '학습 상황', control: 'textarea', help: '멘토링에 필요한 범위에서만 적어 주세요 (예: 문학이 약하다고 함, 인강은 신청만 한 상태).', wide: true },
]

export function emptyProfile() {
  return Object.fromEntries(PROFILE_FIELDS.map((f) => [f.key, '']))
}

/** 보관함 항목에서 가장 최근의 멘티 정보. 없으면 null. */
export function profileFromVault(items) {
  const found = items.filter((x) => x.formId === PROFILE_FORM).sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]
  return found ? { ...emptyProfile(), ...found.draft, _id: found.id } : null
}

/** 다음에 쓸 활동보고서 회차: 저장된 회차 중 가장 큰 값 + 1. */
export function nextSessionNo(items) {
  const nos = items.filter((x) => x.formId === 'activity_report').map((x) => Number(x.sessionNo ?? x.inputs?.session_no)).filter(Boolean)
  return nos.length ? Math.max(...nos) + 1 : 1
}

/** 1회차 일시와 회차 번호로 예상 날짜(YYYY-MM-DD). 매주 같은 요일에 한다고 보고 계산한다. */
export function suggestDate(startDatetime, sessionNo) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(startDatetime || '')
  if (!m || !sessionNo) return ''
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + 7 * (sessionNo - 1)))
  return d.toISOString().slice(0, 10)
}

/** '수학 / 강좌명 / 매주(월) 17:00~18:00' (종합계획서②의 과목 및 시간 칸). 정보가 부족하면 있는 것만. */
export function subjectTimeText(p) {
  const parts = [p.subject, p.course].filter((x) => x && x.trim())
  const t = /T(\d{2}):(\d{2})/.exec(p.start_datetime || '')
  if (p.weekday && t) {
    const start = Number(t[1]) * 60 + Number(t[2])
    const end = start + (Number(p.duration) || 60)
    const hm = (n) => `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`
    parts.push(`매주(${p.weekday}) ${hm(start)}~${hm(end)}`)
  } else if (p.weekday) parts.push(`매주(${p.weekday})`)
  return parts.join(' / ')
}

/** 종합계획서① 초안에 넘길 사전 정보 (멘티 정보에서 만든다). */
export function preContactFromProfile(p) {
  const out = {}
  if (p.subject || p.mode) out.subject_confirm = [p.subject, p.mode].filter(Boolean).join(', ')
  if (p.course) out.site_course = p.course
  if (p.level) out.level = p.level
  if (p.goal) out.goal = p.goal
  return out
}

// 지금 보고 있는 멘티의 별칭. 화면을 옮겨 다녀도 유지한다 (별칭은 실명이 아니다).
export function getCurrentAlias() {
  try {
    return localStorage.getItem(CURRENT_KEY) || ''
  } catch {
    return ''
  }
}

export function setCurrentAlias(alias) {
  try {
    localStorage.setItem(CURRENT_KEY, (alias || '').trim())
  } catch {
    /* 저장하지 못해도 동작에는 지장이 없다 */
  }
}

export const TOTAL_SESSIONS = 16
// 회기를 정리할 때 남기는 자료: 멘티 정보, 완료보고서, 인계 요약
export const KEEP_AFTER_TERM = [PROFILE_FORM, 'completion_report', 'handover_summary']

/** 회차 목록: 1~16회차(저장한 회차가 더 크면 거기까지). 저장한 회차에는 날짜와 상태를 붙인다. */
export function sessionRows(items, profile) {
  const latest = new Map()
  for (const x of items) {
    if (x.formId !== 'activity_report') continue
    const no = Number(x.sessionNo ?? x.inputs?.session_no)
    if (!no) continue
    const prev = latest.get(no)
    if (!prev || prev.savedAt < x.savedAt) latest.set(no, x)
  }
  const last = Math.max(TOTAL_SESSIONS, ...latest.keys())
  const rows = []
  for (let no = 1; no <= last; no += 1) {
    const x = latest.get(no)
    rows.push({ no, saved: !!x, id: x?.id, date: x?.inputs?.session_date || '', status: x?.inputs?.status || '',
      expected: suggestDate(profile?.start_datetime, no) })
  }
  return rows
}

/** 멘티 작업 공간에 보여 줄 문서별 저장 여부. */
export function docStatus(items) {
  const latest = (formId) => items.filter((x) => x.formId === formId).sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]
  const at = (x) => (x ? x.savedAt.slice(0, 10) : '')
  return {
    plan_initial: at(latest('plan_initial')), plan_file: at(latest('plan_file')),
    completion_report: at(latest('completion_report')), handover_summary: at(latest('handover_summary')),
    reports: new Set(items.filter((x) => x.formId === 'activity_report').map((x) => Number(x.sessionNo ?? x.inputs?.session_no)).filter(Boolean)).size,
  }
}

/** 지금 할 일 한 줄. 일정 정보가 없으면 날짜 없이 순서만 안내한다. */
export function nextStep(items, profile) {
  const s = docStatus(items)
  if (!profile || !profile.subject) return '기본 정보를 먼저 적어 주세요.'
  if (!s.plan_initial) return '종합계획서①을 작성할 차례입니다 (매칭 후 7일 이내, 플랫폼 입력).'
  if (s.reports >= 1 && !s.plan_file) return '종합계획서②를 작성해 1회차 활동보고서에 첨부할 차례입니다.'
  if (s.reports < TOTAL_SESSIONS) return `${nextSessionNo(items)}회차 활동보고서를 작성할 차례입니다 (멘토링 후 7일 이내).`
  if (!s.completion_report) return '완료보고서를 작성할 차례입니다.'
  return '이번 회기 문서를 모두 작성했습니다. 플랫폼 제출과 승인을 확인한 뒤 회기 정리를 해 주세요.'
}

export const menteePath = (alias, rest = '') => `/mentees/${encodeURIComponent(alias)}${rest}`
