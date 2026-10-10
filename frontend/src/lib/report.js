// 활동보고서 화면의 칸과 규칙. 플랫폼 입력 칸과 같은 구성이다:
// 이번 주차 학습 내용 / 학습 진도 / 학습 이해도 / 기타 / 건의사항. 항목마다 글상자 하나다 (잘한 점·부족한 점·개선 방향을 한 칸에 쓴다).
// 시간확대(120분) 회차는 학습 진도와 학습 이해도가 전반 1시간·후반 1시간으로 나뉜다.
// 칸에 무엇을 쓰는지는 활동가이드 p.30의 항목별 작성 방법을 따른다:
//   이번 회차 학습 내용 = 학습범위(혹은 목차), 학습목표 / 학습진도 = 출결, 인강 수강 여부, 과제 수행 여부 / 학습이해도 = 멘토링 학습 내용.
export const halvesOf = (duration) => (String(duration) === '120' ? ['전반 1시간 ', '후반 1시간 '] : [''])
const rowsOf = (t) => String(t || '').split('\n').map((x) => x.trim()).filter(Boolean)

/** 예전 화면(잘한 점·부족한 점·개선 방향을 세 칸으로 받던 때)에 저장한 값을 한 칸의 글로. 글이면 그대로. */
export function boxText(box) {
  if (typeof box === 'string') return box
  const parts = [['good', '잘한 점'], ['lacking', '부족한 점'], ['improve', '개선 방향']]
  return parts.filter(([k]) => (box?.[k] || '').trim()).map(([k, label]) => `${label}: ${box[k].replace(/\s*\n\s*/g, ' ').trim()}`).join('\n')
}

/** 이번 주차 학습 내용의 기본 글: 종합계획서의 그 주차 계획을 '학습범위: … / 학습목표: …' 두 줄로 (활동가이드의 필수 기재 사항).
 * row: 커리큘럼 표의 그 주차 {online, mentoring, content, course}. courseName: 그 주차 강좌 이름(강사명 포함). 계획이 없으면 빈 글. */
export function contentAuto(row, courseName = '') {
  if (!row) return ''
  const online = (row.online || '').trim(), mentoring = (row.mentoring || '').trim(), content = (row.content || '').trim()
  const scope = online ? [courseName, online].filter(Boolean).join(', ') : content
  const goal = online ? mentoring : mentoring && mentoring !== content ? mentoring : ''
  return [scope && `학습범위: ${scope}`, goal && `학습목표: ${goal}`].filter(Boolean).join('\n')
}

/** 학습 진도의 기본 줄 [출결, 인강, 과제]: 출석 상태·진행시간, 인강을 들었는지, 과제를 했는지로 만든다 (규칙, AI 미사용).
 * 활동가이드가 필수로 쓰라고 한 세 가지다. 개선 방향은 만들지 않는다 (멘토가 덧붙인다).
 * done: {lecture, task} 각각 '함' | '안 함' | ''. what: {lecture, task} 무엇을 듣고 하기로 했는지 (없으면 빈 글). 해당 없는 줄은 빈 글. */
export function progressLines({ status, time, lecture, task, what = {} }) {
  const tail = (v) => (v ? ` (${v})` : '')
  const named = (v, done, missed) => [(v || '').trim(), done === '함' ? missed[0] : missed[1]].filter(Boolean).join(' ')
  return [
    status === '출석' ? `출결: 정시 출석${tail(time)}` : status === '지각' ? `출결: 지각${tail(time)}` : '',
    lecture ? `인강: ${named(what.lecture, lecture, ['수강함', '수강하지 않음'])}` : '',
    task ? `과제: ${named(what.task, task, ['수행함', '수행하지 않음'])}` : '',
  ]
}

/** 규칙으로 넣어 둔 줄(before)을 새 줄(after)로 바꾼다. 멘토가 고친 줄과 덧붙인 줄은 건드리지 않는다.
 * before/after는 같은 자리끼리 짝이다. 새로 생긴 줄은 앞선 자동 줄 바로 뒤(없으면 맨 앞)에 넣는다. */
export function syncLines(text, before, after) {
  const lines = String(text || '').split('\n')
  if (lines.length === 1 && !lines[0].trim()) lines.length = 0
  after.forEach((next, i) => {
    const prev = before[i]
    const at = prev ? lines.findIndex((l) => l.trim() === prev) : -1
    if (at >= 0) {
      if (next) lines[at] = next
      else lines.splice(at, 1)
    } else if (!prev && next) {
      // 앞선 자리의 줄 뒤에 넣는다. 멘토가 그 줄을 고쳤어도 같은 머리말('인강:')로 시작하면 그 줄로 본다
      const heads = after.slice(0, i).map((x, j) => (x || before[j] || '').split(':')[0]).filter(Boolean)
      const anchor = Math.max(-1, ...heads.map((h) => lines.findIndex((l) => l.trim().startsWith(`${h}:`))))
      lines.splice(anchor + 1, 0, next)
    }
  })
  return lines.join('\n')
}

/** 회차 상태. 임박취소(멘토링 시간 1시간 이내에 멘티가 취소·변경을 요청)는 온라인 멘토링에만 있다 (활동가이드 p.37). */
export const statusesOf = (mode) => (mode === '오프라인' ? ['출석', '지각', '무단결석', '인정결석'] : ['출석', '지각', '임박취소', '무단결석', '인정결석'])
/** 진행하지 못한 회차의 학습 내용 칸에 넣는 글 (서버의 규칙 문구와 같다). 진행한 회차면 빈 글. */
export const absentText = (status) => (status === '무단결석' ? '멘티 무단결석으로 멘토링을 진행하지 못함.'
  : status === '임박취소' ? '멘티의 임박취소로 멘토링을 진행하지 못함.'
  : status === '인정결석' ? '멘티의 불가항력 사유로 인한 결석(인정결석)으로 멘토링을 진행하지 못함.' : '')

/** 지난 회차 보고서에서 다음 회차까지 내 준 것을 적은 문장을 고른다 (규칙: '과제', '숙제', '다음 회차·멘토링·시간'이 든 문장).
 * 활동가이드의 예시처럼 내 준 과제는 학습 이해도(멘토링 학습 내용)에 적는다. 없으면 빈 목록. */
export function assignedSentences(text) {
  const sentences = rowsOf(text).flatMap((line) => line.replace(/^\d+[.)]\s*/, '').split(/(?<=[.!?。])\s+/)).map((s) => s.trim()).filter(Boolean)
  return sentences.filter((s) => /과제|숙제|다음\s*(회차|멘토링|시간|주)/.test(s))
}

// ---- 서버와 주고받을 때: 줄마다 줄 머리에 칸 이름표를 붙인다. 서버는 줄 머리를 그대로 두고 내용만 거르거나 다듬는다
/** 칸들 → '(u0) 글' 줄들. boxes: [[이름표, 칸의 글], …]. 빈 줄은 뺀다. */
export const toLines = (boxes) => boxes.flatMap(([tag, text]) => rowsOf(text).map((line) => `(${tag}) ${line}`)).join('\n')
/** '(u0) 글' 줄들 → {u0: ['글', …]}. 이름표가 없는 줄은 버린다 (서버가 붙인 문구일 수 있다). */
export function fromLines(text) {
  const out = {}
  for (const line of String(text || '').split('\n')) {
    const m = /^\s*\(([a-z]\d?)\)\s*(.*)$/.exec(line)
    if (m && m[2].trim()) (out[m[1]] ||= []).push(m[2].trim())
  }
  return out
}
// 다듬을 때: '출결:' 같은 머리말은 AI에 보내지 않고 나중에 다시 붙인다 (머리말을 문장에 녹여 '과제를 절반만 함'처럼 바꾸지 않게)
const LABELED = /^(\([a-z]\d?\)\s*)((?:출결|인강|과제|학습범위|학습목표|잘한 점|부족한 점|개선 방향)\s*:\s*)(.*)$/
/** 이름표가 붙은 줄 → [AI에 보낼 줄, 뗀 머리말]. 머리말뿐인 줄은 보낼 것이 없다(빈 글). */
export function splitLabel(line) {
  const m = LABELED.exec(line)
  return m ? [m[3].trim() ? m[1] + m[3] : '', m[2]] : [line, '']
}
/** 다듬어 돌아온 줄에 뗀 머리말을 다시 붙인다. */
export function joinLabel(line, label) {
  const m = /^(\([a-z]\d?\)\s*)(.*)$/.exec(line)
  return label && m ? m[1] + label + m[2] : line
}

/** 서버가 돌려준 줄(got)을 칸의 글(text)에 다시 넣는다. 줄 수가 같으면 빈 줄 같은 원래 모양을 지키고, 다르면(통째로 빠진 줄이 있으면) 돌아온 줄만 남긴다. */
export function applyLines(text, got = []) {
  const mine = rowsOf(text)
  if (mine.length !== got.length) return got.join('\n')
  let k = 0
  return String(text || '').split('\n').map((l) => (l.trim() ? got[k++] : l)).join('\n')
}
