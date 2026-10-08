// 설정은 이 브라우저에만 저장한다 (localStorage). 서버로는 질문할 때 주소만 함께 보낸다.
const KEY = 'seoullearn.settings.v1'
export const OPENCHAT_PATTERN = /^https:\/\/open\.kakao\.com\/[A-Za-z0-9/_-]+$/

export function loadSettings() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || '{}')
    return { ieumdanChatUrl: typeof s.ieumdanChatUrl === 'string' ? s.ieumdanChatUrl : '' }
  } catch {
    return { ieumdanChatUrl: '' }
  }
}

/** 주소가 비었거나 카카오톡 오픈채팅 형식이면 저장하고 true. 아니면 저장하지 않고 false. */
export function saveSettings({ ieumdanChatUrl }) {
  const url = (ieumdanChatUrl || '').trim()
  if (url && !OPENCHAT_PATTERN.test(url)) return false
  localStorage.setItem(KEY, JSON.stringify({ ieumdanChatUrl: url }))
  return true
}
