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
