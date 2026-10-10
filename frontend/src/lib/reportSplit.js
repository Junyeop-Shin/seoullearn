// 서울런 플랫폼에서 복사한 활동보고서 여러 개를 회차별로 나눈다 (규칙, AI 미사용).
// 붙여 넣은 글에는 멘티·멘토 이름 칸이 들어 있으므로 서버로 보내지 않고 이 브라우저에서 나눈다. 이름 칸의 값은 읽지 않고 버린다.
// 항목 이름은 활동보고서 양식(forms/activity_report.json)의 이름과, 플랫폼 입력 칸 이름(이 서비스의 활동보고서 화면과 같다)을 함께 본다.
const HALVES = ['', '전반 1시간 ', '후반 1시간 ']
// [항목 이름, key, 같은 보고서 안에서 다시 나오면 이어 붙일지]. 시간확대(120분) 보고서는 학습 진도·학습 이해도가 두 번 나온다
const SCREEN_LABELS = [['이번 주차 학습 내용', 'scope'], ['이번 회차 학습 내용', 'scope'],
  ...HALVES.flatMap((h) => [[`${h}학습 진도`, 'progress_note', !!h], [`${h}학습 이해도`, 'session_content', !!h]])]
// 본문 줄의 첫 낱말로도 흔한 이름: 이름 뒤가 쌍점·탭·닫는 대괄호이거나 줄 끝일 때만 항목 이름으로 본다 ('기타 문제집도 풂'은 본문이다)
const STRICT = new Set(['기타', '건의사항', ...SCREEN_LABELS.map((x) => x[0])])
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** 긴 이름부터 찾는다 ('학습진도 - 출결'이 '학습 진도'보다 먼저). fields: 양식의 fields [{label, key, pii}] */
function labelsOf(fields) {
  const out = SCREEN_LABELS.map(([label, key, append]) => ({ label, key, append }))
  for (const f of fields) {
    out.push({ label: f.label, key: f.key, pii: !!f.pii })
    const short = f.label.replace(/\s*\(.*?\)/g, '').trim()   // '진행시간 (실제 접속시간)' → '진행시간'
    if (short !== f.label) out.push({ label: short, key: f.key, pii: !!f.pii })
  }
  return out.sort((a, b) => b.label.length - a.label.length)
}

/** 글에서 줄 머리에 항목 이름이 나오는 자리. */
function findLabels(text, fields) {
  const found = []
  for (const l of labelsOf(fields)) {
    const tail = STRICT.has(l.label) ? '(?:[\\]\\s]*[:：\\t][ \\t]*|\\]|[ \\t]*$)' : '[\\]\\s]*[:：]?[ \\t]*'
    const pat = new RegExp(`^[ \\t\\-•·\\[]*${l.label.split(/\s+/).map(esc).join('\\s*')}${tail}`, 'gm')
    for (const m of text.matchAll(pat)) {
      if (!found.some((x) => x.start <= m.index && m.index < x.end)) found.push({ ...l, start: m.index, end: m.index + m[0].length })
    }
  }
  return found.sort((a, b) => a.start - b.start)
}

const lineOf = (text, head) => String(text || '').split('\n').map((x) => x.trim()).find((x) => x.startsWith(`${head}:`)) || ''

/** {sessions: [{session_no, …필드 key별 값}], warnings}. 회차 번호 순으로 정렬한다. */
export function splitReports(text, fields) {
  text = String(text || '')
  const marks = findLabels(text, fields)
  if (!marks.length) return { sessions: [], warnings: ['활동보고서 항목을 찾지 못했습니다. 플랫폼의 보고서 내용을 항목 이름과 함께 복사해 붙여 넣어 주세요.'] }
  // 보고서 하나의 시작: 같은 항목이 다시 나오면 새 보고서로 본다
  const blocks = []
  let cur = {}
  marks.forEach((m, n) => {
    const value = text.slice(m.end, n + 1 < marks.length ? marks[n + 1].start : text.length).trim()
    if (m.append && m.key in cur) return (cur[m.key] = [cur[m.key], value].filter(Boolean).join('\n'))
    if (m.key in cur || (m.key === 'session_date' && Object.keys(cur).length)) { blocks.push(cur); cur = {} }
    cur[m.key] = m.pii ? '' : value
  })
  blocks.push(cur)
  const warnings = []
  const byNo = new Map()
  for (const b of blocks.filter((x) => Object.values(x).some(Boolean))) {
    const no = /(\d{1,2})/.exec(b.session_no || '')
    if (!no) { warnings.push('진행 회차를 읽지 못한 보고서가 있어 뺐습니다.'); continue }
    b.session_no = Number(no[1])
    // 플랫폼의 '학습 진도' 칸: 그 안의 출결·인강·과제 줄을 완료보고서와 인계 요약이 읽는 칸으로 옮긴다 (활동보고서 화면의 저장과 같은 규칙)
    if (b.progress_note) {
      b.attendance ||= lineOf(b.progress_note, '출결').replace(/^출결:\s*/, '')
      b.lecture_progress ||= lineOf(b.progress_note, '인강')
      b.homework ||= lineOf(b.progress_note, '과제')
    }
    if (byNo.has(b.session_no)) warnings.push(`같은 회차가 두 번 들어 있습니다: ${b.session_no}회차. 나중 것을 썼습니다.`)
    byNo.set(b.session_no, Object.fromEntries(Object.entries(b).filter(([k, v]) => v !== '' || k === 'session_no')))
  }
  return { sessions: [...byNo.values()].sort((a, b) => a.session_no - b.session_no), warnings: [...new Set(warnings)] }
}

/** 1회차부터 가장 큰 회차까지에서 빠진 회차 번호. */
export function missingRounds(sessions) {
  const nos = new Set(sessions.map((s) => Number(s.session_no)))
  return Array.from({ length: Math.max(0, ...nos) }, (_, i) => i + 1).filter((n) => !nos.has(n))
}
