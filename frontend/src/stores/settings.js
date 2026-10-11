// 설정은 이 브라우저에만 저장한다 (localStorage). 서버로 보내지 않는다.
// 멘토 이름·연락처·소속을 두고, 초안의 [멘토명] 같은 자리표시를 이 브라우저에서 채우는 데만 쓴다.
const KEY = 'seoullearn.settings.v1'
export const MENTOR_TYPES = ['시급형', '봉사형']
const TEXT_KEYS = ['name', 'phone', 'mentoringType', 'university', 'major']

export function loadSettings() {
  let s = {}
  try {
    s = JSON.parse(localStorage.getItem(KEY) || '{}') || {}
  } catch {
    s = {}
  }
  return Object.fromEntries(TEXT_KEYS.map((k) => [k, typeof s[k] === 'string' ? s[k] : '']))
}

/** 이 브라우저에 저장한 멘토 설정을 지운다. */
export function clearSettings() {
  try { localStorage.removeItem(KEY) } catch { /* 저장소를 못 써도 지장 없다 */ }
}

/** 바꿀 값만 넘긴다. */
export function saveSettings(patch) {
  const next = loadSettings()
  for (const k of TEXT_KEYS) if (k in patch) next[k] = String(patch[k] || '').trim()
  localStorage.setItem(KEY, JSON.stringify(next))
}
