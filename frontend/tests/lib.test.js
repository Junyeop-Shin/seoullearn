import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, request } from '../src/api/client'
import { draftFields, emptyInputs, inputFields, toPayload, toText } from '../src/lib/formFields'
import { loadSettings, saveSettings } from '../src/stores/settings'

// 저장소의 forms/*.json (backend가 /api/forms로 그대로 내려주는 파일)
const form = (id) => JSON.parse(readFileSync(resolve(process.cwd(), '..', 'forms', `${id}.json`), 'utf-8'))

describe('양식 스키마 → 입력 칸', () => {
  it('활동보고서: 개인정보 칸은 입력으로 그리지 않고, 회차 상태를 맨 앞에 둔다', () => {
    const fields = inputFields(form('activity_report'))
    const keys = fields.map((f) => f.key)
    expect(keys[0]).toBe('status')
    expect(keys).not.toContain('mentee_name')
    expect(keys).not.toContain('mentee_grade')
    expect(keys).not.toContain('mentor')
    expect(keys).toContain('session_content')
    const scale = fields.find((f) => f.key === 'progress_scale')
    expect(scale.control).toBe('select')
    expect(scale.options).toHaveLength(5)
    expect(fields.find((f) => f.key === 'session_no')).toMatchObject({ control: 'number', min: 1, max: 16 })
    expect(emptyInputs(fields).status).toBe('출석')
  })

  it('종합계획서①: AI·규칙이 채우는 칸은 입력으로 그리지 않는다', () => {
    const keys = inputFields(form('plan_initial')).map((f) => f.key)
    expect(keys).toEqual(['duration', 'weekday', 'start_datetime'])
    expect(draftFields(form('plan_initial')).map((f) => f.key)).toContain('curriculum')
  })

  it('종합계획서②: 목록 칸은 줄 단위로 받아 배열로 보낸다', () => {
    const fields = inputFields(form('plan_file'))
    expect(fields.find((f) => f.key === 'diagnosis').control).toBe('lines')
    const payload = toPayload(fields, { subject_time: ' 국어 ', diagnosis: '문학이 약함\n\n 인강 미수강 ', rules: '' })
    expect(payload).toEqual({ subject_time: '국어', diagnosis: ['문학이 약함', '인강 미수강'], rules: [] })
  })

  it('날짜·시간 입력을 서버 형식으로 바꾼다', () => {
    const fields = inputFields(form('plan_initial'))
    expect(toPayload(fields, { duration: '60', weekday: '월', start_datetime: '2026-10-12T20:00' }).start_datetime).toBe('2026-10-12 20:00')
    expect(toText(['a', 'b'])).toBe('a\nb')
    expect(toText(null)).toBe('')
  })
})

describe('설정 (이 브라우저에만 저장)', () => {
  beforeEach(() => localStorage.clear())
  it('오픈채팅 주소만 저장한다', () => {
    expect(saveSettings({ ieumdanChatUrl: 'https://example.com/chat' })).toBe(false)
    expect(loadSettings().ieumdanChatUrl).toBe('')
    expect(saveSettings({ ieumdanChatUrl: ' https://open.kakao.com/o/abc123 ' })).toBe(true)
    expect(loadSettings().ieumdanChatUrl).toBe('https://open.kakao.com/o/abc123')
    expect(saveSettings({ ieumdanChatUrl: '' })).toBe(true)
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
    const res = await api.chat('지각 처리 어떻게 해요?', 'https://open.kakao.com/o/abc')
    expect(res.answer).toBe('답')
    expect(calls.map((c) => c[0])).toEqual(['/api/auth/csrf', '/api/chat'])
    expect(calls[1][1].headers['X-XSRF-TOKEN']).toBe('tok123')
    expect(JSON.parse(calls[1][1].body)).toEqual({ message: '지각 처리 어떻게 해요?', ieumdan_chat_url: 'https://open.kakao.com/o/abc' })
    await api.chat('질문입니다')
    expect(JSON.parse(calls[2][1].body)).toEqual({ message: '질문입니다' }) // 주소가 없으면 보내지 않는다
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
