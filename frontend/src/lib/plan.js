// 종합계획서의 항목 형식. 서식의 작성 예시를 따른다: 학습 목표는 ①~④, 학생 진단은 (과목역량) 같은 머리말을 줄마다 붙인다.
// 종합계획서①은 플랫폼이 특수문자에서 오류를 낼 수 있어 ① 대신 (1)을 쓴다 (활동가이드 p.29).
export const GOAL_SLOTS = [
  { mark: '①', plain: '(1)', label: '온라인 학습사이트 수강 목표', example: '메가스터디 수학의 시작, 시발점(현우진) 수학1 완강' },
  { mark: '②', plain: '(2)', label: '학습 목표 (진도, 교재, 점수 등)', example: '수학1 1회독 완료, 기말고사 수학 3등급' },
  { mark: '③', plain: '(3)', label: '역량 목표 (학습 태도, 습관 등)', example: '매일 학습플래너 작성하기, 인강은 하루 2강씩 규칙적으로 듣기' },
  { mark: '④', plain: '(4)', label: '진로·진학 관련 목표', example: '목표 대학 입시 정보 찾아보기' },
]
export const DIAG_SLOTS = [
  { mark: '(과목역량)', label: '과목역량', example: '수학의 기본기는 갖추고 있으나 고득점 문제의 해결 능력은 낮음' },
  { mark: '(학습수준 및 희망진로)', label: '학습수준 및 희망진로', example: '내신은 평균 4등급이며 희망 전공은 경찰행정학과' },
  { mark: '(입시준비)', label: '입시준비', example: '대학별 입학 전형과 입시 정보가 거의 없음' },
  { mark: '(학습습관 및 태도)', label: '학습습관 및 태도', example: '학원과 인강 의존도가 높고 자율학습 수준은 낮은 편임' },
]
const marks = (slot) => [slot.mark, slot.plain].filter(Boolean)
const squeeze = (t) => t.replace(/\s/g, '')

/** 항목별로 적은 글 → 한 덩어리 ('① …' 줄들). 비운 항목의 줄은 빼고, 머리말 없는 글(rest)은 끝에 붙인다. plain이면 (1) 형식. */
export function composeSlots(slots, parts, rest = '', plain = false) {
  const lines = slots.map((s, i) => [(plain && s.plain) || s.mark, (parts[i] || '').replace(/\s*\n\s*/g, ' ').trim()]).filter(([, v]) => v).map(([m, v]) => `${m} ${v}`)
  return [...lines, rest.trim()].filter(Boolean).join('\n')
}

/** 한 덩어리 글 → {parts: 항목별 글, rest: 머리말이 없는 줄}. 머리말은 ①과 (1) 둘 다 읽는다. */
export function parseSlots(slots, text) {
  const parts = slots.map(() => '')
  const rest = []
  for (const raw of String(text || '').split('\n')) {
    const line = raw.trim()
    if (!line) continue
    const i = slots.findIndex((s) => marks(s).some((m) => squeeze(line).startsWith(squeeze(m))))
    if (i >= 0) {
      // 머리말(공백 차이는 무시)을 떼고 내용만 남긴다
      let n = 0, k = 0
      const m = squeeze(marks(slots[i]).find((x) => squeeze(line).startsWith(squeeze(x))))
      while (k < m.length && n < line.length) { if (!/\s/.test(line[n])) k += 1; n += 1 }
      parts[i] = [parts[i], line.slice(n).trim()].filter(Boolean).join(' ')
    } else rest.push(line)   // 머리말이 없는 줄은 어느 항목에도 넣지 않는다
  }
  return { parts, rest: rest.join('\n') }
}

/** (1) → ① : 종합계획서①의 글을 종합계획서② 서식 형식으로. */
export function toCircled(text) {
  return String(text || '').split('\n').map((line) => {
    const s = GOAL_SLOTS.find((x) => line.trim().startsWith(x.plain))
    return s ? line.trim().replace(s.plain, s.mark) : line
  }).join('\n')
}

/** 주차별 계획의 강 번호 → '3~4강'. 번호가 없으면 빈 글. */
export function lectureRange(lectures) {
  const nos = (lectures || []).map((x) => Number(x.no)).filter((n) => Number.isFinite(n) && n > 0)
  if (!nos.length) return ''
  const a = Math.min(...nos), b = Math.max(...nos)
  return a === b ? `${a}강` : `${a}~${b}강`
}

/** 배분 결과 한 주차의 강의들 → 온라인 강의 칸의 글. 강좌별로 묶는다.
 * 번호가 있는 목차는 '3~4강', 제목이 제각각인 목차는 '제목, 제목 (3~4강)'. 둘째 강좌부터는 강좌 이름을 앞에 붙인다.
 * 돌려주는 값: {online, course(그 주차의 첫 강좌 번호)} */
export function onlineText(lectures, courses, nameOf) {
  const groups = []
  for (const l of lectures || []) {
    const last = groups[groups.length - 1]
    if (last && last.ci === (l.course || 0)) last.items.push(l)
    else groups.push({ ci: l.course || 0, items: [l] })
  }
  const texts = groups.map((g, gi) => {
    const range = lectureRange(g.items)
    const body = g.items.some((l) => l.auto_no) ? `${g.items.map((l) => l.title).join(', ')}${range ? ` (${range})` : ''}` : range || g.items.map((l) => l.title).join(', ')
    return gi === 0 ? body : `${nameOf(courses[g.ci])}, ${body}`
  })
  return { online: texts.join(' / '), course: groups[0]?.ci ?? 0 }
}

// 플랫폼(종합계획서①) 입력용 글자 정리. 서버의 checks.plain_text와 같은 규칙이다 (활동가이드 p.29: 특수문자가 있으면 등록 오류가 날 수 있다).
// 동그라미 숫자·로마 숫자는 일반 숫자로, 가운뎃점은 쉼표로, 그 밖의 특수문자는 뺀다. 줄바꿈은 그대로 둔다.
const CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
const ROMAN = 'ⅠⅡⅢⅣⅤ'
export function platformSafe(text) {
  return String(text ?? '')
    .replace(/(\d)[·ㆍ](\d)/g, '$1.$2')                                  // 6·25 → 6.25
    .replace(/[①-⑳]/g, (c) => `(${CIRCLED.indexOf(c) + 1})`)
    .replace(/[Ⅰ-Ⅴ]/g, (c) => String(ROMAN.indexOf(c) + 1))
    .replace(/\s*[·•ㆍ]\s*/g, ', ')
    .replace(/[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ\s.,()/~:\-]/g, ' ')
    .replace(/[ \t]+/g, ' ').replace(/ ,/g, ',').replace(/ +\)/g, ')').replace(/\( +/g, '(')
    .split('\n').map((x) => x.trim()).join('\n').trim()
}

const rowsOf = (t) => String(t || '').split('\n').map((x) => x.trim()).filter(Boolean)
/** 다듬을 줄: done(마지막으로 다듬은 글, 기본안)에 없는 줄만. 한 줄만 고쳤으면 그 줄만 AI에 보낸다. */
export function freshLines(text, ...done) {
  const seen = new Set(done.flatMap(rowsOf))
  return rowsOf(text).filter((l) => !seen.has(l))
}
/** 보낸 줄(sent)이 다듬어져 돌아온 줄(got)을 원래 글의 그 자리에 넣는다. 줄 수가 달라 짝을 지을 수 없으면 null. */
export function mergeLines(text, sent, got) {
  got = rowsOf(got)
  if (sent.length !== got.length) return null
  const map = new Map(sent.map((l, i) => [l, got[i]]))
  return String(text || '').split('\n').map((l) => map.get(l.trim()) ?? l).join('\n')
}
/** 두 글에서 서로 다른 줄만 [전, 후]로. 줄 수가 다르면 글 전체를 한 쌍으로. */
export function changedLines(before, after) {
  const a = rowsOf(before), b = rowsOf(after)
  if (a.length !== b.length) return before.trim() === after.trim() ? [] : [[before.trim(), after.trim()]]
  return a.map((l, i) => [l, b[i]]).filter(([x, y]) => x !== y)
}
