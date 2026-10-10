// 종합계획서②를 서식 파일(종합활동계획서 docx, hwpx)에 채워 넣는다.
// 빈 서식은 서버의 폴더에 둔 것을 받아 오고(저장소에 올리지 않는 자료다), 이 브라우저 안에서 칸을 찾아 글을 바꿔 넣는다. 내용과 이름은 서버로 보내지 않는다.
// 칸은 왼쪽의 칸 이름(멘토링기간, 학생진단 …)으로 찾는다.
// docx와 hwpx는 XML을 압축한 파일이다. hwp(예전 형식)는 다루지 못한다.
import { strFromU8, strToU8, unzipSync, zipSync } from 'fflate'

const TITLE = '「서울런 멘토단」 멘토링 종합 계획서'
const squeeze = (s) => String(s || '').replace(/\s/g, '')
const kids = (el, name) => [...el.childNodes].filter((n) => n.nodeName === name)
const all = (el, name) => [...el.getElementsByTagName(name)]
const textOf = (el, t) => all(el, t).map((n) => n.textContent).join('')

/** 칸 이름 → 채울 줄들. 서식의 칸 이름에서 공백을 뺀 글로 찾는다. 진단 칸은 docx가 '학생진단', hwpx가 '멘티진단'이다. */
function plan(data) {
  return { 멘토링기간: [data.period], 멘토링과목및시간: [data.subject_time], 멘티학습목표: data.goal, 학생진단: data.diagnosis, 멘티진단: data.diagnosis, 멘토링구성: data.structure, 활동규칙: data.rules }
}

function parse(xml) {
  const doc = new DOMParser().parseFromString(xml, 'application/xml')
  if (doc.getElementsByTagName('parsererror').length) throw new Error('서식 파일을 읽지 못했습니다. 파일이 손상됐을 수 있습니다.')
  return doc
}
// XMLSerializer는 맨 앞의 XML 선언을 빼므로 원래 선언을 다시 붙인다
const serialize = (doc, xml) => (xml.match(/^<\?xml[^>]*\?>/)?.[0] || '') + new XMLSerializer().serializeToString(doc.documentElement)

// ---- docx: w:tbl > w:tr > w:tc > w:p > w:r > w:t. 세로로 합친 칸(커리큘럼 이름)은 줄마다 빈 칸이 있다
function setDocxCell(tc, lines) {
  const ps = kids(tc, 'w:p')
  const run = all(tc, 'w:r').find((r) => kids(r, 'w:t').length)
  if (!ps.length || !run) return
  const rPr = kids(run, 'w:rPr')[0]?.cloneNode(true)
  // 서식의 예시 글은 파란색이다: 채운 글은 검은색으로
  if (rPr) for (const c of kids(rPr, 'w:color')) c.setAttribute('w:val', '000000')
  const made = (lines.length ? lines : ['']).map((line) => {
    const p = ps[0].cloneNode(false)
    const pPr = kids(ps[0], 'w:pPr')[0]
    if (pPr) p.appendChild(pPr.cloneNode(true))
    const r = run.cloneNode(false)
    if (rPr) r.appendChild(rPr.cloneNode(true))
    const t = kids(run, 'w:t')[0].cloneNode(false)
    t.setAttribute('xml:space', 'preserve')
    t.textContent = line
    r.appendChild(t)
    p.appendChild(r)
    return p
  })
  for (const p of ps) tc.removeChild(p)
  for (const p of made) tc.appendChild(p)
}

function fillDocx(xml, data) {
  const doc = parse(xml)
  const cells = plan(data)
  let found = 0, week = -1
  for (const tr of all(doc, 'w:tr')) {
    const tcs = kids(tr, 'w:tc')
    const label = squeeze(textOf(tcs[0], 'w:t'))
    const merged = all(tcs[0], 'w:vMerge').length > 0
    if (label.startsWith('커리큘럼')) week = 0
    else if (week >= 0 && !(merged && !label)) week = -1   // 합친 칸이 끝나면 커리큘럼도 끝난다
    if (week >= 0) {
      if (week === 0) { setDocxCell(tcs[0], ['커리큘럼', data.course].filter(Boolean)); found += 1 }
      if (week >= data.weeks.length) tr.parentNode.removeChild(tr)   // 8회차 회기는 남는 줄을 지운다
      else setDocxCell(tcs.at(-1), data.weeks[week])
      week += 1
    } else if (label.includes('종합계획서')) setDocxCell(tcs[0], [TITLE])   // 제목의 '작성예시'를 뺀다
    else if (label === '멘티' && tcs.length >= 4) { setDocxCell(tcs[1], [data.mentee]); setDocxCell(tcs[3], [data.mentor]); found += 1 }
    else if (cells[label]) { setDocxCell(tcs.at(-1), cells[label]); found += 1 }
  }
  if (found < 8) throw new Error('종합활동계획서 서식이 아닌 것 같습니다. 공지사항에서 받은 서식 파일을 골라 주세요.')
  return serialize(doc, xml)
}

// ---- hwpx: hp:tbl > hp:tr > hp:tc > hp:subList > hp:p > hp:run > hp:t. 세로로 합친 칸은 첫 줄에만 있고 rowSpan으로 높이를 잡는다
function setHwpxCell(tc, lines, black) {
  const sub = kids(tc, 'hp:subList')[0]
  const ps = sub ? kids(sub, 'hp:p') : []
  const run = all(tc, 'hp:run').find((r) => kids(r, 'hp:t').length)
  if (!ps.length || !run) return
  const made = (lines.length ? lines : ['']).map((line) => {
    const p = ps[0].cloneNode(false)   // 줄 배치 정보(linesegarray)는 넣지 않는다: 한글이 열 때 다시 계산한다
    const r = run.cloneNode(false)
    r.setAttribute('charPrIDRef', black(run.getAttribute('charPrIDRef')))
    const t = kids(run, 'hp:t')[0].cloneNode(false)
    t.textContent = line
    r.appendChild(t)
    p.appendChild(r)
    return p
  })
  for (const p of ps) sub.removeChild(p)
  for (const p of made) sub.appendChild(p)
}

function fillHwpx(xml, header, data) {
  const doc = parse(xml)
  const cells = plan(data)
  // 서식의 예시 글은 파란 글자 모양이다: 같은 크기의 검은 글자 모양으로 바꾼다
  const shapes = {}
  for (const m of header.matchAll(/<hh:charPr id="(\d+)" height="(\d+)" textColor="([^"]+)"/g)) shapes[m[1]] = { height: m[2], dark: m[3] === '#000000' }
  const used = [...new Set(all(all(doc, 'hp:tbl')[0] || doc, 'hp:run').map((r) => r.getAttribute('charPrIDRef')))]   // 표 안에서 쓰는 글자 모양 가운데 고른다
  const black = (id) => (!shapes[id] || shapes[id].dark ? id : used.find((x) => shapes[x]?.dark && shapes[x].height === shapes[id].height) ?? id)
  const addr = (tc, key) => Number(kids(tc, 'hp:cellAddr')[0]?.getAttribute(key))
  const height = (tc) => Number(kids(tc, 'hp:cellSz')[0]?.getAttribute('height')) || 0
  let found = 0, head = null, first = -1, span = 0, cut = 0, removed = 0
  for (const tr of all(doc, 'hp:tr')) {
    const tcs = kids(tr, 'hp:tc')
    const label = squeeze(textOf(tcs[0], 'hp:t'))
    const row = addr(tcs[0], 'rowAddr')
    if (label.startsWith('커리큘럼')) {
      head = tcs[0]; first = row
      span = Number(kids(head, 'hp:cellSpan')[0].getAttribute('rowSpan'))
      setHwpxCell(head, ['커리큘럼', data.course].filter(Boolean), black)
      found += 1
    }
    if (head && row >= first && row < first + span) {
      const week = row - first
      if (week >= data.weeks.length) { cut += height(tcs.at(-1)); removed += 1; tr.parentNode.removeChild(tr) }   // 8회차 회기는 남는 줄을 지운다
      else setHwpxCell(tcs.at(-1), data.weeks[week], black)
      continue
    }
    // 지운 줄만큼 아래 줄의 번호를 당긴다
    if (removed) for (const tc of tcs) kids(tc, 'hp:cellAddr')[0].setAttribute('rowAddr', String(addr(tc, 'rowAddr') - removed))
    if (label.includes('종합계획서')) setHwpxCell(tcs[0], [TITLE], black)   // 제목의 '작성예시'를 뺀다
    else if (label === '멘티' && tcs.length >= 4) { setHwpxCell(tcs[1], [data.mentee], black); setHwpxCell(tcs[3], [data.mentor], black); found += 1 }
    else if (cells[label]) { setHwpxCell(tcs.at(-1), cells[label], black); found += 1 }
  }
  if (found < 8) throw new Error('종합활동계획서 서식이 아닌 것 같습니다. 공지사항에서 받은 서식 파일을 골라 주세요.')
  if (removed) {
    // 줄을 지웠으면 표의 줄 수와 합친 칸의 높이도 맞춘다
    const tbl = all(doc, 'hp:tbl')[0]
    tbl.setAttribute('rowCnt', String(Number(tbl.getAttribute('rowCnt')) - removed))
    kids(head, 'hp:cellSpan')[0].setAttribute('rowSpan', String(span - removed))
    for (const sz of [kids(head, 'hp:cellSz')[0], kids(tbl, 'hp:sz')[0]]) sz.setAttribute('height', String(Math.max(0, Number(sz.getAttribute('height')) - cut)))
  }
  return serialize(doc, xml)
}

/** 서식 파일(bytes)에 data를 채운 새 파일의 bytes를 돌려준다.
 * data: {period, mentee, mentor, subject_time, course, goal, diagnosis, structure, rules(줄 목록), weeks(주차마다 줄 목록)}
 * docx도 hwpx도 아니거나 종합활동계획서 서식이 아니면 사용자에게 보여 줄 글로 오류를 던진다. */
export function fillPlanFile(bytes, data) {
  let files
  try {
    files = unzipSync(bytes)
  } catch {
    throw new Error('docx 또는 hwpx 서식 파일을 골라 주세요. hwp 파일은 채울 수 없습니다.')
  }
  const put = (path, text) => { files[path] = strToU8(text) }
  if (files['word/document.xml']) put('word/document.xml', fillDocx(strFromU8(files['word/document.xml']), data))
  else if (files['Contents/section0.xml']) put('Contents/section0.xml', fillHwpx(strFromU8(files['Contents/section0.xml']), strFromU8(files['Contents/header.xml'] || new Uint8Array()), data))
  else throw new Error('docx 또는 hwpx 서식 파일을 골라 주세요.')
  if (files['Preview/PrvText.txt']) put('Preview/PrvText.txt', '')   // hwpx의 미리보기 글에는 서식의 예시가 들어 있다: 비운다
  // hwpx는 mimetype이 압축 없이 맨 앞에 있어야 한다
  const { mimetype, ...rest } = files
  return zipSync(mimetype ? { mimetype: [mimetype, { level: 0 }], ...rest } : rest)
}

/** 멘토코드: 멘토 이름 + 전화번호 뒤 네 자리 (예: 이멘토1234). 이름이나 번호가 없으면 빈 글. */
export function mentorCode(name, phone) {
  const digits = String(phone || '').replace(/\D/g, '')
  return name && digits.length >= 4 ? `${String(name).trim()}${digits.slice(-4)}` : ''
}

/** 서식의 파일 이름 규칙: [멘토코드]N회기_종합활동계획서_멘티이름.확장자 (ext: 'hwpx' | 'docx') */
export function planFileName(ext, { code, term, mentee }) {
  return `[${code || '멘토코드'}]${term || 1}회기_종합활동계획서_${mentee || '멘티이름'}.${ext}`
}
