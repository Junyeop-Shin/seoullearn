// 활동비 계산에 넣을 한 달치 입력을 저장된 자료에서 만든다 (규칙). 금액 계산은 서버의 규칙 함수가 한다 (ai-server/app/allowance.py).
// 멘티 이름은 화면에서만 쓰고, 서버에는 회차 수와 조건만 보낸다.

// 고학년지도 가산금: 멘티가 수강하는 학습사이트가 고등학생용 사이트일 때 (활동가이드 p.43). 학년이 아니라 사이트가 기준이고, 검정고시 과정은 들어가지 않는다 (p.42)
const SENIOR_SITES = ['이투스', '메가스터디', '밀크T고등', '대성마이맥']
/** 수강 강좌 이름으로 고학년지도 가산금 대상인지 짐작한다. 이름만으로 알 수 없으면 false (멘토가 화면에서 고친다). */
export function isSeniorCourse(course) {
  const c = String(course || '').replace(/\s/g, '')
  return !c.includes('검정고시') && SENIOR_SITES.some((s) => c.includes(s))
}

/** 저장된 활동보고서가 있는 달 ('2026-10') 목록. 최근 달이 먼저. mentees: [{reports: [{session_date}]}] */
export function reportMonths(mentees) {
  const months = new Set(mentees.flatMap((m) => m.reports.map((r) => String(r.session_date || '').slice(0, 7))).filter((x) => /^\d{4}-\d{2}$/.test(x)))
  return [...months].sort().reverse()
}

/** 그 달의 멘티별 회차 수 (활동보고서의 진행일과 회차 상태로 센다). 그 달에 보고서가 없는 멘티는 빠진다.
 * 정상 진행 = 출석·지각 (진행해서 승인받을 회차). 무단결석은 기본수당만, 임박취소는 준비수당만(온라인), 인정결석은 지급이 없다.
 * mentees: [{alias, profile: {name, mode, duration, course}, reports: [{session_date, status}]}] */
export function monthRows(mentees, month) {
  return mentees.map((m) => {
    const mine = m.reports.filter((r) => String(r.session_date || '').startsWith(month))
    const count = (...statuses) => mine.filter((r) => statuses.includes(r.status || '출석')).length
    return { alias: m.alias, name: m.profile.name || m.alias, mode: m.profile.mode === '오프라인' ? '오프라인' : '온라인', hours: String(m.profile.duration) === '120' ? 2 : 1,
      normal: count('출석', '지각'), no_show: count('무단결석'), late_cancel: count('임박취소'), excused: count('인정결석'), senior: isSeniorCourse(m.profile.course), sessions: mine.length }
  }).filter((r) => r.sessions > 0)
}

/** '2026-10' → 지급 안내에 쓸 {month: 10, payMonth: 11}. 활동비는 다음 달 20일에 지급된다 (활동가이드 p.46). */
export function payInfo(month) {
  const m = Number(String(month).slice(5, 7))
  return { month: m, payMonth: (m % 12) + 1 }
}
