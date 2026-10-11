import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, request } from '../src/api/client'
import { toText } from '../src/lib/formFields'
import { loadSettings, saveSettings } from '../src/stores/settings'

describe('초안 값 → 글', () => {
  it('목록은 줄마다 하나, 없는 값은 빈 글', () => {
    expect(toText(['가', '나'])).toBe('가\n나')
    expect(toText(null)).toBe('')
  })
})

describe('설정 (이 브라우저에만 저장)', () => {
  beforeEach(() => localStorage.clear())
  it('멘토 정보만 저장하고, 예전에 저장한 이음단 주소 같은 다른 값은 읽지 않는다', () => {
    localStorage.setItem('seoullearn.settings.v1', JSON.stringify({ name: '이멘토', ieumdanChatUrl: 'https://open.kakao.com/o/old', ieumdanChats: { 성동구: 'x' } }))
    expect(loadSettings()).toEqual({ name: '이멘토', phone: '', mentoringType: '', university: '', major: '' })
    saveSettings({ phone: ' 010-0000-0000 ' })
    expect(JSON.parse(localStorage.getItem('seoullearn.settings.v1'))).toEqual({ name: '이멘토', phone: '010-0000-0000', mentoringType: '', university: '', major: '' })
  })
})

describe('API 클라이언트', () => {
  beforeEach(() => {
    document.cookie = 'XSRF-TOKEN=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
    vi.restoreAllMocks()
  })
  const reply = (status, body) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

  it('POST에는 CSRF 토큰 헤더를 붙이고 /api로만 보낸다', async () => {
    const calls = []
    vi.stubGlobal('fetch', vi.fn(async (url, init) => {
      calls.push([url, init])
      if (url === '/api/auth/csrf') {
        document.cookie = 'XSRF-TOKEN=tok123'
        return reply(200, {})
      }
      return reply(200, { intent: 'qa', answer: '답' })
    }))
    const res = await api.chat('지각 처리 어떻게 해요?')
    expect(res.answer).toBe('답')
    expect(calls.map((c) => c[0])).toEqual(['/api/auth/csrf', '/api/chat'])
    expect(calls[1][1].headers['X-XSRF-TOKEN']).toBe('tok123')
    expect(JSON.parse(calls[1][1].body)).toEqual({ message: '지각 처리 어떻게 해요?' })   // 질문만 보낸다
    expect(calls.every((c) => c[0].startsWith('/api/'))).toBe(true)
  })

  it('오류는 서버의 안내 문구로 바꾼다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => reply(429, { detail: '로그인 시도가 너무 많습니다. 10분 후에 다시 시도해 주세요.' })))
    await expect(request('GET', '/api/auth/me')).rejects.toMatchObject({ status: 429, message: '로그인 시도가 너무 많습니다. 10분 후에 다시 시도해 주세요.' })
    vi.stubGlobal('fetch', vi.fn(async () => reply(422, { detail: [{ msg: 'Field required' }] })))
    await expect(request('GET', '/api/x')).rejects.toMatchObject({ message: '입력값을 확인해 주세요.' })
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('network') }))
    await expect(request('GET', '/api/x')).rejects.toBeInstanceOf(ApiError)
  })
})
