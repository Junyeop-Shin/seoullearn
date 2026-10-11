import { reactive } from 'vue'
import { loadSettings } from '../stores/settings'
import { listItems } from '../stores/vault'

// 서버로 보내기 직전에, 이 브라우저에 등록한 멘티·멘토 이름을 자리표시로 바꾼다 (서버의 가드는 '○○ 학생' 꼴만 잡는다).
// 응답이 돌아오면 자리표시를 다시 이름으로 채우므로 화면의 글은 바뀌지 않는다. 이름을 가리는 판단은 규칙으로 한다 (AI에 물으려면 이름을 보내야 한다):
// 등록한 이름 전체('김민수')는 낱말 머리에 있으면 뒤에 무엇이 붙든 가리고, 성을 뗀 이름이나 두 글자 이름('민수', '지수')은 뒤에 사람에게 붙는 말이 올 때만 가린다.
// 자리표시는 이름마다 다르다('[멘티명1]', '[멘티명2]'): 한 글에 두 멘티가 나와도 되돌릴 때 섞이지 않는다.
// '지수와 로그', '지수함수'는 그대로 둔다. '지수가 어렵다'처럼 규칙이 틀릴 수 있어, 가린 말을 알리고 멘토가 풀 수 있게 한다.
// words: 방금 가린 말, loose: 그 가운데 맥락으로 가린 줄인 이름(틀릴 수 있어 멘토가 풀 수 있다), off: 멘토가 가리지 않기로 한 말 (이 탭을 연 동안)
export const nameMask = reactive({ words: [], loose: [], released: [], off: new Set() })   // released: 방금 푼 말 (되돌릴 수 있다)
/** 맥락으로 가린 말을 이름이 아니라고 푼다. 등록한 이름 전체는 풀지 않는다. */
export function release() {
  nameMask.loose.forEach((w) => nameMask.off.add(w))
  Object.assign(nameMask, { words: [], released: nameMask.loose, loose: [] })
}
/** 방금 푼 말을 다시 이름으로 가린다. */
export function restore() {
  nameMask.released.forEach((w) => nameMask.off.delete(w))
  nameMask.released = []
}
/** 푼 말을 모두 다시 가린다 (화면을 옮길 때). all이면 알림도 지운다 (로그아웃, 탈퇴). */
export function resetMask(all) {
  nameMask.off.clear()
  Object.assign(nameMask, all ? { words: [], loose: [], released: [] } : { released: [] })
}

// '이'가 붙은 꼴('지훈이를', '지훈이 오늘')은 이름에만 있어 넓게 받는다. '를·의·와·만'만 붙은 꼴('지수와 로그')은 낱말일 수 있어 받지 않는다
const PERSON = '(?:이?(?:가|는|도|한테|에게|랑)(?:는|도|만)?|이(?:를|의|와|만)?|은|야|아|[ \\t]?(?:학생|멘티|어머니|아버지|어머님|아버님|군|양))'
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const hangul = (s) => /^[가-힣]+$/.test(s)

/** [{name, mark, re}] 긴 이름부터. names: [[이름, 자리표시]] */
export function rulesFor(names, off = new Set()) {
  const out = []
  for (const [raw, mark] of names) {
    const name = String(raw || '').trim()
    if (name.length < 2 || /[0-9○*]|OO|XX/.test(name)) continue   // '김OO', '멘티 1' 같은 이름은 실명이 아니다
    // 한글이 아닌 이름(영문, 띄어 쓴 이름)은 이름 전체만 가린다
    if (!hangul(name)) { out.push({ name, mark, re: new RegExp(`(?<![A-Za-z가-힣])${esc(name).replace(/\s+/g, '\\s*')}(?![A-Za-z])`, 'gi') }); continue }
    if (name.length >= 3) out.push({ name, mark, re: new RegExp(`(?<![가-힣])${esc(name)}`, 'g') })
    const short = name.length <= 4 ? name.slice(-2) : ''
    // 줄인 이름은 자리표시를 달리한다: 응답에서 되돌릴 때 '김민수'와 '민수'가 섞이지 않게
    if (short) out.push({ name: short, loose: true, mark: name.length >= 3 ? mark.replace('명', ' 이름') : mark, re: new RegExp(`(?<![가-힣])${esc(short)}(?=${PERSON}(?![가-힣]))`, 'g') })
  }
  return out.filter((r) => !off.has(r.name)).sort((a, b) => b.name.length - a.name.length)
}

/** 값 안의 모든 글에 fn을 적용한다. */
const walk = (v, fn) => (typeof v === 'string' ? (v.startsWith('data:') ? v : fn(v)) :   // 사진(base64) 안의 우연한 글자는 건드리지 않는다
  Array.isArray(v) ? v.map((x) => walk(x, fn))
  : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, walk(x, fn)])) : v)

/** {body: 가린 것, found: {자리표시: 처음 가린 말}}. */
export function maskBody(body, rules) {
  const found = {}, loose = new Set()
  const masked = walk(body, (t) => rules.reduce((s, r) => s.replace(r.re, (m) => { found[r.mark] ||= m; if (r.loose) loose.add(m); return r.mark }), t))
  return { body: masked, found, loose: [...loose] }
}

/** 응답의 자리표시를 가린 말로 되돌린다. 가린 것이 없던 자리표시는 그대로 둔다 (화면이 채운다). */
export const unmask = (data, found) => (Object.keys(found).length ? walk(data, (t) => Object.entries(found).reduce((s, [mark, word]) => s.replaceAll(mark, word), t)) : data)

/** 이 브라우저가 아는 이름으로 규칙을 만든다. 보관함을 못 읽으면 가리지 않고 보낸다 (서버의 가드는 그대로 돈다). */
export async function currentRules() {
  const items = await listItems().catch(() => [])
  const mentees = [...new Set(items.filter((x) => x.formId === 'mentee_profile').map((x) => x.draft?.name))].map((n, i) => [n, `[멘티명${i + 1}]`])
  return rulesFor([...mentees, [loadSettings().name, '[멘토명]']], nameMask.off)
}
