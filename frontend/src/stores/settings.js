// 설정은 이 브라우저에만 저장한다 (localStorage). 서버로는 질문할 때 이음단 주소만 함께 보낸다.
// 멘토 이름·연락처·소속도 여기에만 두고, 초안의 [멘토명] 같은 자리표시를 이 브라우저에서 채우는 데만 쓴다.
const KEY = 'seoullearn.settings.v1'
export const OPENCHAT_PATTERN = /^https:\/\/open\.kakao\.com\/[A-Za-z0-9/_-]+$/
export const MENTOR_TYPES = ['시급형', '봉사형']
const TEXT_KEYS = ['name', 'phone', 'mentoringType', 'university', 'major']

export function loadSettings() {
  let s = {}
  try {
    s = JSON.parse(localStorage.getItem(KEY) || '{}') || {}
  } catch {
    s = {}
  }
  const out = { ieumdanChatUrl: typeof s.ieumdanChatUrl === 'string' ? s.ieumdanChatUrl : '', ieumdanChats: {} }
  for (const k of TEXT_KEYS) out[k] = typeof s[k] === 'string' ? s[k] : ''
  if (s.ieumdanChats && typeof s.ieumdanChats === 'object') {
    for (const [d, url] of Object.entries(s.ieumdanChats)) if (typeof url === 'string' && OPENCHAT_PATTERN.test(url)) out.ieumdanChats[d] = url
  }
  return out
}

/** 바꿀 값만 넘긴다. 이음단 주소가 카카오톡 오픈채팅 형식이 아니면 저장하지 않고 false. */
export function saveSettings(patch) {
  const next = { ...loadSettings() }
  if ('ieumdanChatUrl' in patch) {
    const url = (patch.ieumdanChatUrl || '').trim()
    if (url && !OPENCHAT_PATTERN.test(url)) return false
    next.ieumdanChatUrl = url
  }
  if (patch.ieumdanChats) {
    const chats = {}
    for (const [d, raw] of Object.entries(patch.ieumdanChats)) {
      const url = (raw || '').trim()
      if (url && !OPENCHAT_PATTERN.test(url)) return false
      if (url) chats[d] = url
    }
    next.ieumdanChats = chats
  }
  for (const k of TEXT_KEYS) if (k in patch) next[k] = String(patch[k] || '').trim()
  localStorage.setItem(KEY, JSON.stringify(next))
  return true
}

/** 자치구의 이음단 채널 주소: 멘토가 적어 둔 자치구별 주소 → 제공된 목록(channels) → 기본 주소 순. */
export function chatUrlFor(district, settings = loadSettings(), channels = {}) {
  const listed = typeof channels[district] === 'string' && OPENCHAT_PATTERN.test(channels[district]) ? channels[district] : ''
  return settings.ieumdanChats[district] || listed || settings.ieumdanChatUrl || ''
}

let channelsCache = null
/** 자치구별 이음단 채널 목록 (public/data/eumdan_channels.json). 아직 비어 있다. 못 읽으면 빈 목록. */
export async function loadChannels() {
  if (channelsCache) return channelsCache
  try {
    const res = await fetch('/data/eumdan_channels.json')
    channelsCache = res.ok ? await res.json() : {}
  } catch {
    channelsCache = {}
  }
  return channelsCache
}
