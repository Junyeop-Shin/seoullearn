// backend(/api) 호출. 세션 쿠키와 CSRF 토큰(XSRF-TOKEN 쿠키 → X-XSRF-TOKEN 헤더)을 다룬다.
// 보내는 글에서 등록한 멘티·멘토 이름을 자리표시로 가리고, 응답에서 되돌린다 (lib/nameMask.js). 로그인·가입 요청은 건드리지 않는다.
import { currentRules, maskBody, nameMask, unmask } from '../lib/nameMask'

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

function readCookie(name) {
  const m = document.cookie.split('; ').find((c) => c.startsWith(name + '='))
  return m ? decodeURIComponent(m.slice(name.length + 1)) : ''
}

const FALLBACK = {
  401: '로그인이 필요합니다.',
  403: '요청을 처리할 수 없습니다. 화면을 새로 고친 뒤 다시 시도해 주세요.',
  413: '보내는 내용이 너무 큽니다. 사진이나 글을 줄여 주세요.',
  429: '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.',
}

function detailOf(body, status) {
  const d = body && body.detail
  if (typeof d === 'string') return d
  // FastAPI 검증 오류는 detail이 배열이다
  if (Array.isArray(d)) return '입력값을 확인해 주세요.'
  return FALLBACK[status] || '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'
}

export async function request(method, path, body) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let res, found = {}
  if (body !== undefined && !path.startsWith('/api/auth/')) {
    const m = maskBody(body, await currentRules());
    ({ body, found } = m)
    if (Object.keys(found).length) Object.assign(nameMask, { words: Object.values(found), loose: m.loose })   // 방금 푼 말(released)의 [되돌리기]는 닫을 때까지 남긴다
  }
  try {
    if (method !== 'GET') {
      if (!readCookie('XSRF-TOKEN')) await fetch('/api/auth/csrf', { credentials: 'same-origin' })
      headers['X-XSRF-TOKEN'] = readCookie('XSRF-TOKEN')
    }
    res = await fetch(path, {
      method,
      headers,
      credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, '연결하지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요.')
  }
  if (res.status === 204) return null
  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  // 쓰는 도중 로그인이 풀린 경우: 적던 글을 잃지 않고 이어 갈 방법을 알린다 (로그인 쿠키는 탭끼리 함께 쓴다)
  if (res.status === 401 && !path.startsWith('/api/auth/')) throw new ApiError(401, '로그인이 풀렸습니다. 새 탭에서 다시 로그인한 뒤 이 화면에서 다시 눌러 주세요. 적던 내용은 그대로 있습니다.')
  if (!res.ok) throw new ApiError(res.status, detailOf(data, res.status))
  return unmask(data, found)
}

export const api = {
  me: () => request('GET', '/api/auth/me'),
  login: (username, password) => request('POST', '/api/auth/login', { username, password }),
  /** consent: 가입 전 동의 {version: 동의한 문서의 시행일, items: 동의한 항목} */
  signup: (username, password, consent) => request('POST', '/api/auth/signup', { username, password, consentVersion: consent?.version, consents: consent?.items }),
  withdraw: () => request('DELETE', '/api/auth/me'),
  logout: () => request('POST', '/api/auth/logout'),
  places: () => request('GET', '/api/places'),
  /** 종합활동계획서 서식 파일(docx, hwpx)의 bytes. 서버에 서식이 없으면(404) null. 로그인이 풀렸거나 연결이 끊긴 것은 오류로 알린다. */
  planTemplate: async (format) => {
    const res = await fetch(`/api/templates/plan?format=${format}`, { credentials: 'same-origin' }).catch(() => { throw new ApiError(0, '연결하지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요.') })
    if (res.status === 404) return null
    if (!res.ok) throw new ApiError(res.status, detailOf(null, res.status))
    return new Uint8Array(await res.arrayBuffer())
  },
  config: () => request('GET', '/api/config'),
  form: (id) => request('GET', `/api/forms/${id}`),
  chat: (message) => request('POST', '/api/chat', { message }),
  draft: (formId, inputs, extra = {}) => request('POST', `/api/drafts/${formId}`, { inputs, extra }),
  preContact: (mode, subject = '') => request('POST', '/api/drafts/pre_contact', { mode, subject }),
  courseOutline: (text) => request('POST', '/api/drafts/course_outline', { text }),
  courseOutlineImage: (image) => request('POST', '/api/drafts/course_outline_image', { image }),
  weeklyPlan: (payload) => request('POST', '/api/drafts/weekly_plan', payload),
  allowance: (payload) => request('POST', '/api/tools/allowance', payload),
  allowanceMonth: (payload) => request('POST', '/api/tools/allowance_month', payload),
  handover: (reports) => request('POST', '/api/drafts/handover_summary', { reports }),
  unanswered: () => request('GET', '/api/admin/unanswered'),
  deleteUnanswered: (id) => request('DELETE', `/api/admin/unanswered/${id}`),
}
