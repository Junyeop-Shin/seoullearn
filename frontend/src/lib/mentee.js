// 멘티 정보: 한 번 적어 두면 보고서와 계획서에 다시 입력하지 않게 하는 자료. 이 브라우저 보관함에만 저장한다.
// 이름과 학년도 받지만 서버와 AI로는 보내지 않는다: 초안의 [멘티명] 같은 자리표시를 이 브라우저에서 채우는 데만 쓴다.
// 학교, 연락처, 가정 사정은 칸이 없다.
import { endTime, weekdayOf } from './schedule'
import { totalRounds, withState } from './stage'
import { listItems } from '../stores/vault'

export const PROFILE_FORM = 'mentee_profile'
const CURRENT_KEY = 'seoullearn.currentMentee.v1'
export const DISTRICTS = ['강남구', '강동구', '강북구', '강서구', '관악구', '광진구', '구로구', '금천구', '노원구', '도봉구', '동대문구', '동작구', '마포구',
  '서대문구', '서초구', '성동구', '성북구', '송파구', '양천구', '영등포구', '용산구', '은평구', '종로구', '중구', '중랑구']
export const SUBJECTS = ['국어', '영어', '수학', '사회', '과학', '기타']

export const PROFILE_FIELDS = [
  { key: 'name', label: '멘티 이름', control: 'text', example: '김OO', help: '메뉴와 보고서의 멘티 성명 칸에 씁니다. 실명 대신 별칭이나 이니셜을 권합니다. 이 브라우저에만 저장됩니다.' },
  { key: 'grade', label: '학년', control: 'text', example: '고1' },
  { key: 'subject', label: '신청 과목', control: 'select', options: SUBJECTS },
  { key: 'subjectEtc', label: '신청 과목 기타', control: 'text', example: '검정고시 수학', help: "과목이 '기타'이거나 덧붙일 말이 있을 때만 적습니다." },
  { key: 'district', label: '자치구', control: 'select', options: DISTRICTS, help: '협약 장소와 이음단 채널을 찾는 기준입니다.' },
  { key: 'mode', label: '멘토링 방식', control: 'select', options: ['온라인', '오프라인'], help: "오프라인이면 메뉴의 '오프라인 일정·장소'에서 장소와 일정을 이음단에 요청합니다." },
  { key: 'duration', label: '회당 학습시간(분)', control: 'select', options: ['60', '120'], help: '기본은 60분입니다. 120분(시간확대)은 보통 고등 과정 멘티가 1회기를 마친 뒤 신청하고, 승인을 받아야 합니다.' },
  { key: 'course', label: '학습사이트와 수강 강좌', control: 'text', example: '메가스터디 수학의 시작, 시발점 - 수1', wide: true },
  { key: 'start_datetime', label: '1회차 일시', control: 'datetime-local', help: '회차 번호와 날짜를 자동으로 채우는 기준입니다.' },
  { key: 'venue', label: '멘토링 장소', control: 'text', help: "오프라인만 적습니다. '오프라인 일정·장소'에서 정한 장소가 여기에 저장됩니다." },
]

export function emptyProfile() {
  // goal(학습 목표)과 level(학생 진단)은 종합계획서에서 적는다. 멘티 설정에는 칸이 없다
  return { ...Object.fromEntries(PROFILE_FIELDS.map((f) => [f.key, ''])), goal: '', level: '', weekday: '', regularSchedule: [], term: 1, currentRound: 1, stage: '',
    archived: false, lastHomework: null }
}

/** 멘티의 상세 정보 [학년, 과목, 자치구, 방식]. 적지 않은 항목은 뺀다. */
export function facts(profile) {
  const subject = profile?.subject === '기타' ? profile.subjectEtc || '기타' : profile?.subject
  return [profile?.grade, subject, profile?.district, profile?.mode].filter((x) => x && String(x).trim())
}
/** 상세 정보 한 줄: 고1 · 수학 · 성동구 · 오프라인 */
export const menteeFacts = (profile) => facts(profile).join(' · ')

/** 메뉴에 보이는 이름: 김OO (고1, 수학, 성동구, 오프라인). 적지 않은 항목은 뺀다. */
export function displayName(profile, alias = '') {
  const name = (profile?.name || alias || '').trim()
  return facts(profile).length ? `${name} (${facts(profile).join(', ')})` : name
}

/** 정규 일정 [{weekday, startTime}]. 따로 적지 않았으면 1회차 일시의 요일과 시각을 쓴다. */
export function regularSchedule(profile) {
  const rows = (profile?.regularSchedule || []).filter((r) => r && r.weekday)
  if (rows.length) return rows
  const weekday = profile?.weekday || weekdayOf(profile?.start_datetime)
  const t = /T(\d{2}:\d{2})/.exec(profile?.start_datetime || '')
  return weekday ? [{ weekday, startTime: t ? t[1] : '' }] : []
}

/** '매주 수 19:00~20:00, 토 10:00~11:00' */
export function scheduleText(profile) {
  const rows = regularSchedule(profile)
  if (!rows.length) return ''
  return '매주 ' + rows.map((r) => `${r.weekday}${r.startTime ? ` ${r.startTime}~${endTime(r.startTime, profile.duration)}` : ''}`).join(', ')
}

/** 초안의 개인정보 칸(자리표시)에 이 브라우저에서 채울 값. 서버로는 보내지 않는다. 값이 없는 칸은 넣지 않는다. */
export function fillValues(profile, mentor = {}) {
  const affiliation = [mentor.university, mentor.major].filter(Boolean).join(' ')
  const out = {
    mentee_name: profile?.name, mentee_grade: profile?.grade,
    mentee: [profile?.name, profile?.grade && `(${profile.grade})`].filter(Boolean).join(' '),
    mentor: mentor.name ? `${mentor.name}${affiliation ? ` (${affiliation})` : ''}` : '', mentor_phone: mentor.phone,
  }
  return Object.fromEntries(Object.entries(out).filter(([, v]) => v && String(v).trim()))
}

/** 보관함 항목에서 가장 최근의 멘티 정보. 없으면 null. */
export function profileFromVault(items) {
  const found = items.filter((x) => x.formId === PROFILE_FORM).sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]
  return found ? withState({ ...emptyProfile(), ...found.draft, _id: found.id }, items) : null
}

/** 보관함의 멘티 목록 [{alias, items, profile}]: 멘티 정보가 있는 별칭만, 종료한 멘티는 뒤로. 보관함은 한 번만 읽는다. */
export async function menteesFromVault() {
  const by = {}
  for (const x of await listItems()) (by[x.alias] ||= []).push(x)
  return Object.entries(by).map(([alias, items]) => ({ alias, items, profile: profileFromVault(items) })).filter((m) => m.profile)
    .sort((a, b) => Number(a.profile.archived) - Number(b.profile.archived) || a.alias.localeCompare(b.alias, 'ko'))
}

/** 1회차 일시와 회차 번호로 예상 날짜(YYYY-MM-DD). 매주 같은 요일에 한다고 보고 계산한다. */
export function suggestDate(startDatetime, sessionNo) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(startDatetime || '')
  if (!m || !sessionNo) return ''
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + 7 * (sessionNo - 1)))
  return d.toISOString().slice(0, 10)
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

// 회기를 정리할 때 남기는 자료: 멘티 정보, 완료보고서, 인계 요약
export const KEEP_AFTER_TERM = [PROFILE_FORM, 'completion_report', 'handover_summary', 'term_summary']

/** 회차 목록: 1회차부터 그 회기의 회차 수까지(저장한 회차가 더 크면 거기까지). 저장한 회차에는 날짜와 상태를 붙인다. */
export function sessionRows(items, profile) {
  const latest = new Map()
  for (const x of items) {
    if (x.formId !== 'activity_report') continue
    const no = Number(x.sessionNo ?? x.inputs?.session_no)
    if (!no) continue
    const prev = latest.get(no)
    if (!prev || prev.savedAt < x.savedAt) latest.set(no, x)
  }
  const last = Math.max(totalRounds(profile), ...latest.keys())
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

export const menteePath = (alias, rest = '') => `/mentees/${encodeURIComponent(alias)}${rest}`
