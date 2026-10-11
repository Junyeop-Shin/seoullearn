import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ConsentStep from '../src/components/ConsentStep.vue'
import { COLLECTED, CONSENTS, OVERSEAS, VERSION } from '../src/lib/privacy'

describe('가입 전 동의', () => {
  it('필수 항목을 하나씩 따로 받고, 모두 동의해야 넘어간다. 미리 체크해 두지 않는다', async () => {
    const w = mount(ConsentStep)
    const boxes = CONSENTS.map((c) => w.find(`[data-consent=${c.id}]`))
    expect(boxes.every((b) => b.element.checked === false)).toBe(true)
    expect(w.find('[data-test=consent-ok]').element.disabled).toBe(true)
    for (const b of boxes.slice(0, 3)) await b.setValue(true)
    expect(w.find('[data-test=consent-ok]').element.disabled).toBe(true)
    expect(w.find('[data-consent=all]').element.checked).toBe(false)
    await boxes[3].setValue(true)
    expect(w.find('[data-consent=all]').element.checked).toBe(true)
    await w.find('form').trigger('submit')
    expect(w.emitted('agreed')[0][0]).toEqual({ version: VERSION, items: ['age14', 'collect', 'overseas', 'mentee'] })
    // 전체 동의를 끄면 모두 꺼진다
    await w.find('[data-consent=all]').setValue(false)
    expect(boxes.every((b) => b.element.checked === false)).toBe(true)
  })

  it('알려야 하는 사항이 화면에 있다: 항목·목적·보유 기간, 거부할 권리, 국외 이전의 여섯 가지', () => {
    const text = mount(ConsentStep).text()
    for (const r of COLLECTED) for (const v of [r.items, r.purpose, r.period]) expect(text).toContain(v)
    for (const [k, v] of OVERSEAS) { expect(text).toContain(k); expect(text).toContain(v) }
    expect(OVERSEAS.map(([k]) => k)).toEqual(['이전받는 자', '이전되는 국가', '이전 일시와 방법', '이전하는 항목', '이용 목적', '보유·이용 기간'])
    expect(text).toContain('동의를 거부할 권리가 있습니다')
    expect(text).toContain('동의하지 않으면 가입할 수 없습니다')
  })

  it('동의 항목과 문서의 시행일 형식이 서버가 받는 것과 같다', () => {
    const java = readFileSync(resolve(process.cwd(), '..', 'backend/src/main/java/com/seoullearn/mentor/auth/AuthController.java'), 'utf-8')
    const required = /REQUIRED_CONSENTS = Set\.of\(([^)]*)\)/.exec(java)[1].split(',').map((x) => x.trim().replaceAll('"', ''))
    expect(CONSENTS.map((c) => c.id).sort()).toEqual(required.sort())
    expect(VERSION).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
})
