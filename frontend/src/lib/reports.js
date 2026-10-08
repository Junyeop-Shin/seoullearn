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

// 내 강좌: 한 번 정리한 강의 목차를 보관함에 두고 다음 회기나 다른 멘티 때 다시 쓴다. 멘티별 자료가 아니라서 별칭을 고정한다.
export const COURSE_ALIAS = '내 강좌'
export const COURSE_FORM = 'course_outline'

/** 보관함의 강좌 목록 (이름순). 같은 이름이 여러 번 저장돼 있으면 가장 늦게 저장한 것만. */
export function coursesFromVault(items) {
  const latest = new Map()
  for (const x of items) {
    if (x.formId !== COURSE_FORM || !Array.isArray(x.draft?.lectures) || !x.draft.lectures.length) continue
    const prev = latest.get(x.title)
    if (!prev || prev.savedAt < x.savedAt) latest.set(x.title, x)
  }
  return [...latest.values()]
    .map((x) => ({ id: x.id, title: x.title, lectures: x.draft.lectures, savedAt: x.savedAt }))
    .sort((a, b) => a.title.localeCompare(b.title, 'ko'))
}

/** 보관함 화면에 보여 줄 초안 한 칸의 글. 강의 목록은 '1강 제목'으로 풀어 쓴다. */
export function draftValueText(value) {
  if (Array.isArray(value)) {
    return value.map((v) => (v && typeof v === 'object' ? `${v.no != null ? `${v.no}강 ` : ''}${v.title ?? ''}`.trim() : String(v))).join('\n')
  }
  return value === null || value === undefined ? '' : String(value)
}
