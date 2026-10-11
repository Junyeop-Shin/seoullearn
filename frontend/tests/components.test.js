import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import AnswerCard from '../src/components/AnswerCard.vue'

// 저장소의 forms/*.json (backend가 /api/forms로 그대로 내려주는 파일)
const form = (id) => JSON.parse(readFileSync(resolve(process.cwd(), '..', 'forms', `${id}.json`), 'utf-8'))
const stubs = { 'router-link': { template: '<a><slot /></a>' } }

describe('AnswerCard', () => {
  it('근거와 문의처를 카드로, 이음단이면 자치구별 채널을 볼 수 있는 이음단 연락처로 안내한다', () => {
    const res = { intent: 'qa', answer: '이음단과 협의해 주세요.', citations: ['활동가이드 p.37 출결 규정'], route: '이음단',
      route_info: '소속 자치구 이음단 (자치구별 카카오톡 채널)', pii_masked: ['학교명'],
      inquiry_draft: '안녕하세요, 서울런 멘토입니다.', inquiry_contact: '소속 자치구 이음단 (자치구별 카카오톡 채널)' }
    const w = mount(AnswerCard, { props: { res }, global: { stubs } })
    expect(w.find('[data-test="citations"]').text()).toContain('p.37')
    expect(w.find('[data-test="route-contacts"]').exists()).toBe(true)
    expect(w.find('[data-test="inquiry"]').text()).toContain('서울런 멘토입니다')
    expect(w.find('[data-test="pii"]').text()).toContain('학교명')
  })

  it('이음단이 아닌 문의처에는 채널 안내가 없고, 문의처가 없으면 카드를 그리지 않는다', () => {
    const base = { intent: 'qa', answer: '답', citations: [], pii_masked: [] }
    const w = mount(AnswerCard, { props: { res: { ...base, route: '운영사무국', route_info: '멘토링 운영사무국 (02-3274-9212)' } }, global: { stubs } })
    expect(w.find('[data-test="route"]').text()).toContain('02-3274-9212')
    expect(w.find('[data-test="route-contacts"]').exists()).toBe(false)
    const w2 = mount(AnswerCard, { props: { res: { ...base, route: null } }, global: { stubs } })
    expect(w2.find('[data-test="route"]').exists()).toBe(false)
    expect(w2.find('[data-test="pii"]').exists()).toBe(false)
  })

  it('보고서 작성 요청이면 화면 이동 버튼과 입력 항목을 보여준다', () => {
    const res = { intent: 'report', answer: '활동보고서 작성 화면으로 이동해 주세요.', screen: '활동보고서 작성', required_inputs: ['멘토링 일자', '진행 회차'], citations: [] }
    const w = mount(AnswerCard, { props: { res }, global: { stubs } })
    expect(w.text()).toContain('활동보고서 작성 화면으로 이동')
    expect(w.text()).toContain('진행 회차')
  })
})

import { defineComponent, h, nextTick, ref } from 'vue'
import CurriculumEditor from '../src/components/CurriculumEditor.vue'

describe('커리큘럼 표', () => {
  // 부모가 v-model로 받은 줄을 다시 내려 주는 실제 쓰임대로 붙인다
  const host = (initial, rounds) => defineComponent({
    setup() {
      const rows = ref(initial)
      const count = ref(0)
      return () => h(CurriculumEditor, { modelValue: rows.value, rounds, start: '2026-10-12T17:00', 'onUpdate:modelValue': (v) => { rows.value = v; count.value += 1 }, 'data-count': count.value })
    },
  })

  it('저장한 줄이 회차 수와 달라도 지금의 회차 수에 맞추고, 끝없이 되풀이하지 않는다', async () => {
    const saved = Array.from({ length: 16 }, (_, i) => ({ week: i + 1, date: '', time: '', content: `${i + 1}주 내용` }))
    const w = mount(host(saved, 8))
    for (let i = 0; i < 5; i += 1) await nextTick()
    expect(w.findAll('[data-content]')).toHaveLength(8)                        // 시간확대(8회차)로 바꾼 뒤에는 8줄
    expect(w.find('[data-content="8"]').element.value).toBe('8주 내용')         // 적어 둔 내용은 남는다
    expect(w.find('[data-date="2"]').element.value).toBe('2026-10-19')          // 날짜는 1회차 일시에서 매주
    expect(Number(w.find('[data-test=curriculum]').attributes('data-count'))).toBeLessThanOrEqual(2)
  })
})
