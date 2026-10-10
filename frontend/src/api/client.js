// backend(/api) 호출. 세션 쿠키와 CSRF 토큰(XSRF-TOKEN 쿠키 → X-XSRF-TOKEN 헤더)을 다룬다.

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
  if (method !== 'GET') {
    if (!readCookie('XSRF-TOKEN')) await fetch('/api/auth/csrf', { credentials: 'same-origin' })
    headers['X-XSRF-TOKEN'] = readCookie('XSRF-TOKEN')
  }
  let res
  try {
    res = await fetch(path, {
      method,
      headers,
      credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, '서버에 연결할 수 없습니다. 네트워크를 확인해 주세요.')
  }
  if (res.status === 204) return null
  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  if (!res.ok) throw new ApiError(res.status, detailOf(data, res.status))
  return data
}

export const api = {
  me: () => request('GET', '/api/auth/me'),
  login: (username, password) => request('POST', '/api/auth/login', { username, password }),
  signup: (username, password) => request('POST', '/api/auth/signup', { username, password }),
  logout: () => request('POST', '/api/auth/logout'),
  places: () => request('GET', '/api/places'),
  /** 종합활동계획서 서식 파일(docx, hwpx)의 bytes. 서버에 없으면 null. */
  planTemplate: async (format) => {
    const res = await fetch(`/api/templates/plan?format=${format}`, { credentials: 'same-origin' })
    return res.ok ? new Uint8Array(await res.arrayBuffer()) : null
  },
  config: () => request('GET', '/api/config'),
  forms: () => request('GET', '/api/forms'),
  form: (id) => request('GET', `/api/forms/${id}`),
  chat: (message, ieumdanChatUrl) =>
    request('POST', '/api/chat', ieumdanChatUrl ? { message, ieumdan_chat_url: ieumdanChatUrl } : { message }),
  draft: (formId, inputs, extra = {}) => request('POST', `/api/drafts/${formId}`, { inputs, extra }),
  preContact: (mode, callTime, answers, subject = '') =>
    request('POST', '/api/drafts/pre_contact', { mode, call_time: callTime || null, answers: answers || null, subject }),
  courseOutline: (text) => request('POST', '/api/drafts/course_outline', { text }),
  courseOutlineImage: (image) => request('POST', '/api/drafts/course_outline_image', { image }),
  weeklyPlan: (payload) => request('POST', '/api/drafts/weekly_plan', payload),
  allowance: (payload) => request('POST', '/api/tools/allowance', payload),
  splitReports: (text) => request('POST', '/api/drafts/split_reports', { text }),
  handover: (reports) => request('POST', '/api/drafts/handover_summary', { reports }),
  ieumdanRequest: (payload) => request('POST', '/api/drafts/ieumdan_request', payload),
  unanswered: () => request('GET', '/api/admin/unanswered'),
  deleteUnanswered: (id) => request('DELETE', `/api/admin/unanswered/${id}`),
}
