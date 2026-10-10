// 멘티 한 명의 업무 단계: 사전 연락 → 종합계획서 → 회차별 활동보고서 → 완료보고서. 단계는 멘티 정보(profile.stage)에 저장한다.
// 종합계획서 단계 안에서 1회차 전의 종합계획서①, 1회차 후의 종합계획서②를 차례로 한다. 오프라인 장소와 일정은 '오프라인 일정·장소' 화면에서 따로 한다.
export const STAGES = [
  { id: 'PRE_CONTACT', label: '사전 연락' },
  { id: 'PLAN', label: '종합계획서' },
  { id: 'ACTIVITY', label: '활동보고서' },
  { id: 'COMPLETION', label: '완료보고서' },
]
const IDS = STAGES.map((s) => s.id)
// 예전에 따로 있던 단계(장소 확보, 종합계획서①, 1회차)는 종합계획서 단계로 읽는다
const MERGED = ['VENUE', 'PRE_PLAN', 'FIRST_SESSION']

/** 이 멘티가 거치는 단계 목록. 사전 연락은 멘티를 처음 만나는 1회기에만 한다. */
export function flow(profile) {
  return Number(profile?.term) > 1 ? STAGES.filter((s) => s.id !== 'PRE_CONTACT') : STAGES
}

function step(profile, by) {
  const list = flow(profile)
  const i = list.findIndex((s) => s.id === profile.stage)
  return list[Math.min(list.length - 1, Math.max(0, (i < 0 ? 0 : i) + by))].id
}
export const nextStage = (profile) => step(profile, 1)
export const prevStage = (profile) => step(profile, -1)

/** 한 회기의 회차 수. 회당 학습시간으로 정해진다: 60분은 16회차, 120분(시간확대)은 8회차. */
export function totalRounds(profile) {
  return String(profile?.duration) === '120' ? 8 : 16
}

/** 왼쪽 메뉴에 붙이는 단계 표시. */
export function stageBadge(profile) {
  if (profile.archived) return '종료'
  if (profile.stage === 'ACTIVITY') return `활동보고서 ${profile.currentRound}회차`
  return STAGES.find((s) => s.id === profile.stage)?.label || ''
}

/** 단계 정보가 없는 멘티(예전 자료)는 저장된 문서로 단계를 짐작해 채운다. */
export function withState(profile, items = []) {
  const p = { ...profile }
  p.term = Number(p.term) >= 1 ? Number(p.term) : 1
  const has = (formId) => items.some((x) => x.formId === formId)
  const rounds = items.filter((x) => x.formId === 'activity_report').map((x) => Number(x.sessionNo ?? x.inputs?.session_no)).filter(Boolean)
  const last = rounds.length ? Math.max(...rounds) : 0
  if (!(Number(p.currentRound) >= 1)) p.currentRound = Math.min(last + 1, totalRounds(p))
  p.currentRound = Number(p.currentRound)
  if (MERGED.includes(p.stage) || (p.stage === 'PRE_CONTACT' && p.term > 1)) p.stage = 'PLAN'
  if (!IDS.includes(p.stage)) {
    if (last >= totalRounds(p)) p.stage = 'COMPLETION'
    else if (last >= 1) p.stage = 'ACTIVITY'
    else if (has('plan_file')) p.stage = 'ACTIVITY'
    else if (has('plan_initial')) p.stage = 'PLAN'
    else p.stage = 'PRE_CONTACT'
  }
  return p
}

/** 활동보고서를 저장한 뒤의 회차와 단계. 지금 회차를 저장했을 때만 다음으로 넘어간다. */
export function afterReport(profile, savedRound) {
  if (profile.stage !== 'ACTIVITY' || savedRound !== profile.currentRound) return {}
  return savedRound >= totalRounds(profile) ? { stage: 'COMPLETION' } : { currentRound: savedRound + 1 }
}

/** 다음 회기를 시작할 때의 멘티 정보. 시간확대(60↔120분)는 회기마다 다시 정한다.
 * 지난 회기의 목표·진단·1회차 일시는 넘기지 않는다: 남겨 두면 새 종합계획서①이 지난 글로 채워져 '지난 회기에 이어 초안 채우기'가 할 일이 없다 (지난 목표는 회기 요약에 남는다). */
export function nextTerm(profile, duration) {
  return { ...profile, term: (Number(profile.term) || 1) + 1, currentRound: 1, stage: 'PLAN', duration: String(duration || profile.duration || '60'),
    lastHomework: null, goal: '', level: '', start_datetime: '' }
}
