// 교과과정으로 채우기: 학년·학기·과목의 교육과정 단원(public/data/curriculum.json)을 주차에 나눈다.
// 규칙만 쓴다 (AI 미사용). 자료를 브라우저에서 읽고 계산하므로 멘티의 학년과 과목이 서버로 나가지 않는다.
// 자료는 2026학년도 기준이고 출처는 그 파일의 sources에 있다. 학년도가 바뀌면 파일을 갱신한다.
import { platformSafe } from './plan'

export const GRADES = ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고1', '고2', '고3']
export const CURRICULUM_SUBJECTS = ['국어', '영어', '수학', '사회', '과학']
export const SEMESTERS = ['1학기', '2학기']
export const FIRST_WEEK = '오리엔테이션, 현재 수준 진단'
export const LAST_WEEK = '학습 내용 총정리'
const PHASES = ['개념', '문제 풀이', '정리']

let cache = null
/** 교육과정 자료를 한 번만 읽는다. 못 읽으면 null. */
export async function loadCurriculum() {
  if (cache) return cache
  try {
    const res = await fetch('/data/curriculum.json')
    cache = res.ok ? await res.json() : null
  } catch {
    cache = null
  }
  return cache
}

/** 멘티 정보에 적은 학년 글('고1', '중학교 2학년', '초등 5')을 자료의 학년 이름으로. 알 수 없으면 빈 글. */
export function gradeKey(text) {
  const m = /(초|중|고)\s*(?:등\s*학교|학교|등)?\s*(\d)/.exec(String(text || ''))
  const key = m ? `${m[1]}${m[2]}` : ''
  return GRADES.includes(key) ? key : ''
}

/** 시험이 있는 학교급인지 (중·고). 복습 주차의 이름에 쓴다. */
export const hasExams = (grade) => /^[중고]/.test(grade || '')

/** 그 학년·학기·과목의 단원.
 * 돌려주는 값: {units: 단원 목록, courses: 고를 수 있는 세부 과목 목록, basic: 고르지 않았을 때의 과목 이름(있으면 안 골라도 단원이 나온다), name: 그 학기의 과목 이름(예: 공통수학1), notes: 멘토에게 보여 줄 안내}
 * 단원이 없으면 units가 비고 notes에 까닭이 들어간다. */
export function findUnits(data, grade, semester, subject, course = '') {
  const g = data?.grades?.[grade]
  if (!g) return { units: [], courses: [], name: '', notes: [] }
  // 초1~2는 사회·과학 대신 통합교과로 배운다
  const key = !g.subjects[subject] && ['사회', '과학'].includes(subject) && g.subjects['통합교과'] ? '통합교과' : subject
  const s = g.subjects[key]
  if (!s) return { units: [], courses: [], name: '', notes: [`${g.label} ${subject}의 교육과정 자료가 없습니다. 교과서 목차를 보고 직접 적어 주세요.`] }
  if (s.none) return { units: [], courses: [], name: '', notes: [s.none] }
  const notes = [`${g.label}은 ${g.curriculum} 교육과정입니다.`, data.levels?.[s.level], s.note].filter(Boolean)
  const base = { courses: [], name: s.termNames?.[semester] || (key !== subject ? key : ''), notes }
  if (s.courses) {
    const courses = Object.keys(s.courses)
    if (s.others?.length) notes.push(`단원 자료가 없는 과목: ${s.others.join(', ')}. 이 과목을 듣는다면 교과서 목차를 보고 직접 적어 주세요.`)
    if (!courses.length) return { ...base, units: [] }
    return { ...base, courses, name: s.courses[course] ? course : '', units: s.courses[course] || [] }
  }
  if (s.others?.length) notes.push(`단원 자료가 없는 과목: ${s.others.join(', ')}.`)
  // 학기별 단원이 있는 과목에서 따로 고를 수 있는 세부 과목 (사회 아래의 역사·한국사). 고르지 않으면 원래 과목(basic)의 단원이다
  if (s.extra) Object.assign(base, { courses: Object.keys(s.extra), basic: base.name || subject })
  if (s.extra?.[course]) return { ...base, name: course, units: s.extra[course] }
  if (s.terms) return { ...base, units: s.terms[semester] || [] }
  // 한 해 단위로만 정리된 과목: 앞뒤 절반으로 나누거나(half) 통째로 쓴다(whole)
  const half = Math.ceil(s.year.length / 2)
  return { ...base, units: s.split === 'half' ? (semester === '2학기' ? s.year.slice(half) : s.year.slice(0, half)) : s.year }
}

/** 단원을 넣을 수 있는 주차 번호(0부터)와, 규칙으로 채우는 주차(첫 주, 중간 복습, 마지막 주)의 글.
 * 16주 회기는 진단 1주 + 복습 2주(가운데와 마지막)를 빼고 단원을 나눈다. 8주 회기는 첫 주와 마지막 주만 뺀다. */
export function weekFrame(rounds, exam = false) {
  const fixed = Array(rounds).fill('')
  if (rounds >= 1) fixed[0] = FIRST_WEEK
  if (rounds >= 3) fixed[rounds - 1] = exam ? `${LAST_WEEK}와 시험 대비` : LAST_WEEK
  if (rounds >= 12) fixed[Math.floor(rounds / 2)] = exam ? '앞 단원 복습과 시험 대비' : '앞 단원 복습'
  return { fixed, slots: fixed.map((x, i) => (x ? -1 : i)).filter((i) => i >= 0) }
}

/** 단원 목록 → 주차별 학습 내용(rounds개). 단원이 주차보다 적으면 한 단원을 여러 주에(개념 → 문제 풀이 → 정리), 많으면 한 주에 여러 단원을 넣는다.
 * 플랫폼에 그대로 옮길 수 있게 특수문자를 정리한다. 단원이 없으면 빈 목록. */
export function spreadUnits(units, rounds, exam = false) {
  if (!units?.length || rounds < 1) return []
  const { fixed, slots } = weekFrame(rounds, exam)
  const n = units.length, m = slots.length
  const out = [...fixed]
  if (!m) return out
  if (n <= m) {
    // 앞 단원부터 한 주씩 더 준다
    let at = 0
    units.forEach((u, i) => {
      const weeks = Math.floor(m / n) + (i < m % n ? 1 : 0)
      for (let j = 0; j < weeks; j += 1) out[slots[at++]] = weeks === 1 ? u : weeks <= PHASES.length ? `${u} - ${PHASES[j]}` : `${u} (${j + 1}/${weeks})`
    })
  } else {
    let at = 0
    slots.forEach((slot, i) => {
      const count = Math.floor(n / m) + (i < n % m ? 1 : 0)
      out[slot] = units.slice(at, at + count).join(' / ')
      at += count
    })
  }
  return out.map(platformSafe)
}

/** 단원 자료가 없을 때 칸에 보여 줄 예시 (주차의 자리에 맞춘 일반적인 흐름). */
export function genericHints(rounds, exam = false) {
  const { fixed, slots } = weekFrame(rounds, exam)
  const out = [...fixed]
  slots.forEach((slot, j) => { out[slot] = `${Math.floor(j / 2) + 1}단원 ${j % 2 ? '문제 풀이' : '개념 학습'}` })
  return out
}
