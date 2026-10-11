import 'fake-indexeddb/auto'

import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { api } from '../src/api/client'
import { checklist } from '../src/lib/checklist'
import { listItems, saveItem } from '../src/stores/vault'
import * as chat from '../src/stores/chat'
import ChatView from '../src/views/ChatView.vue'
import CompletionView from '../src/views/CompletionView.vue'
import HandoverView from '../src/views/HandoverView.vue'
import ReportView from '../src/views/ReportView.vue'
import PlanStage from '../src/views/stages/PlanStage.vue'

// 화면을 실제로 띄워 보는 테스트: AI를 언제 부르는지, 저장해 둔 것을 다시 여는지처럼 화면 안에서만 정해지는 동작을 본다.
const settle = async () => { for (let i = 0; i < 10; i += 1) await flushPromises() }
async function open(view, alias, path) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/mentees/:alias/:rest(.*)*', component: view }, { path: '/:x(.*)*', component: { template: '<i />' } }] })
  router.push(`/mentees/${encodeURIComponent(alias)}/${path}`)
  await router.isReady()
  const w = mount(view, { global: { plugins: [router] } })
  await settle()
  return w
}
const profile = (alias, stage) => saveItem({ alias, formId: 'mentee_profile', title: '멘티 정보', draft: { name: alias, stage, term: 1, currentRound: 16, duration: '60', subject: '수학' } })
const report = (alias, no) => saveItem({ alias, formId: 'activity_report', title: `활동보고서 ${no}회차`, sessionNo: no,
  inputs: { session_no: String(no), session_date: '2026-10-06', status: '출석' }, draft: { attendance: '정시 출석', session_content: '예제는 혼자 품' } })
const drafted = { draft: { content: ['플래너 작성 습관 형성'], achievement: ['2회차 모두 출석'], emotional_care: '', requests: [] }, warnings: [], reminders: [] }

afterEach(() => { vi.restoreAllMocks(); checklist.items = null })

describe('완료보고서 화면', () => {
  it('완료보고서 단계에서 열면 초안을 한 번 쓰고 바로 저장해 둔다. 다시 열 때는 AI를 부르지 않는다', async () => {
    const draft = vi.spyOn(api, 'draft').mockResolvedValue(drafted)
    await profile('완료A', 'COMPLETION'); await report('완료A', 1); await report('완료A', 2)
    const w = await open(CompletionView, '완료A', 'completion')
    expect(draft).toHaveBeenCalledTimes(1)
    expect(w.find('[data-draft=content]').element.value).toBe('- 플래너 작성 습관 형성')
    expect((await listItems('완료A')).filter((x) => x.formId === 'completion_report')).toHaveLength(1)
    expect(checklist.items).toBe(null)   // 자동으로 저장할 때는 체크리스트를 띄우지 않는다
    w.unmount()
    const again = await open(CompletionView, '완료A', 'completion')
    expect(draft).toHaveBeenCalledTimes(1)
    expect(again.find('[data-draft=achievement]').element.value).toBe('- 2회차 모두 출석')
    // 직접 저장하면 체크리스트가 뜨고, 같은 항목을 덮어쓴다
    await again.find('[data-draft=emotional_care]').setValue('진로 고민을 들어 줌')
    await again.find('form').trigger('submit')
    await settle()
    expect(checklist.items.map((i) => i.mark)).toEqual(['o', 'o', 'o', 'tri', 'tri'])
    expect((await listItems('완료A')).filter((x) => x.formId === 'completion_report')).toHaveLength(1)
  })

  it('회기 중간에 눌러 본 것으로는 AI를 부르지 않고, 빈 칸과 [초안 만들기]를 보여 준다', async () => {
    const draft = vi.spyOn(api, 'draft').mockResolvedValue(drafted)
    await profile('완료B', 'ACTIVITY'); await report('완료B', 1)
    const w = await open(CompletionView, '완료B', 'completion')
    expect(draft).not.toHaveBeenCalled()
    expect(w.find('[data-draft=content]').element.value).toBe('')
    expect(w.find('[data-test=redraft]').text()).toBe('초안 만들기')
    await w.find('[data-test=redraft]').trigger('click')
    await settle()
    expect(draft).toHaveBeenCalledTimes(1)
    expect(w.find('[data-test=redraft]').text()).toBe('초안 다시 만들기')
    expect((await listItems('완료B')).some((x) => x.formId === 'completion_report')).toBe(false)   // 눌러서 만든 초안은 [저장]을 눌러야 남는다
  })

  it('AI의 답을 읽지 못했으면 빈 칸으로 넘어가지 않고 알린다. 칸과 다시 만들기 버튼은 남는다', async () => {
    vi.spyOn(api, 'draft').mockResolvedValue({ ...drafted, draft: { content: [], achievement: [], emotional_care: '', requests: [] }, error: 'JSONDecodeError' })
    await profile('완료C', 'COMPLETION'); await report('완료C', 1)
    const w = await open(CompletionView, '완료C', 'completion')
    expect(w.find('.box.error').text()).toContain('AI의 답을 읽지 못했습니다')
    expect(w.find('[data-test=completion-form]').exists()).toBe(true)
    expect(w.find('[data-test=redraft]').text()).toBe('초안 만들기')
    expect((await listItems('완료C')).some((x) => x.formId === 'completion_report')).toBe(false)
  })

  it('초안을 쓰는 사이에 다음 회기를 시작했으면 늦게 온 초안을 저장하지 않는다', async () => {
    let arrive
    vi.spyOn(api, 'draft').mockReturnValue(new Promise((r) => { arrive = r }))
    const p = await profile('완료D', 'COMPLETION'); await report('완료D', 1)
    await open(CompletionView, '완료D', 'completion')
    await saveItem({ id: p.id, alias: '완료D', formId: 'mentee_profile', title: '멘티 정보', draft: { ...p.draft, stage: 'PLAN', term: 2, currentRound: 1 } })
    arrive(drafted)
    await settle()
    expect((await listItems('완료D')).some((x) => x.formId === 'completion_report')).toBe(false)
  })
})

describe('활동보고서 화면', () => {
  it('저장할 때 멘티 정보를 다시 읽어 얹는다: 화면을 연 뒤 다른 단계에서 고친 값을 옛 값으로 되돌리지 않는다', async () => {
    vi.spyOn(api, 'draft').mockImplementation(async (_form, inputs) => ({ draft: { ...inputs }, pii_masked: [], warnings: [], reminders: [] }))
    const p = await saveItem({ alias: '보고A', formId: 'mentee_profile', title: '멘티 정보', draft: { name: '보고A', stage: 'ACTIVITY', term: 1, currentRound: 3, duration: '60', subject: '수학',
      start_datetime: '2026-10-05T17:00', course: '옛 강좌' } })
    const w = await open(ReportView, '보고A', 'report')
    // 살려 둔 화면 뒤에서 종합계획서가 1회차 일시와 강좌를 고쳤다
    await saveItem({ id: p.id, alias: '보고A', formId: 'mentee_profile', title: '멘티 정보', draft: { ...p.draft, start_datetime: '2026-10-07T19:00', course: '새 강좌' } })
    await w.find('form').trigger('submit')
    await settle(); await settle()
    const now = (await listItems('보고A')).find((x) => x.formId === 'mentee_profile').draft
    expect(now).toMatchObject({ currentRound: 4, start_datetime: '2026-10-07T19:00', course: '새 강좌' })
    w.unmount()
  })
})

describe('매뉴얼 질문 화면', () => {
  it('로그아웃하거나 대화를 지운 뒤에 늦게 온 답은 버린다. 답을 기다리는 동안에는 다른 화면에 다녀와도 입력이 잠겨 있다', async () => {
    let arrive
    vi.spyOn(api, 'chat').mockReturnValue(new Promise((r) => { arrive = r }))
    const w = await open(ChatView, '-', 'chat')
    await w.find('textarea').setValue('활동보고서는 언제까지 내야 해요?')
    await w.find('form').trigger('submit')
    expect(chat.busy.value).toBe(true)
    w.unmount()
    const again = await open(ChatView, '-', 'chat')            // 다른 화면에 다녀왔다
    expect(again.find('form button').attributes('disabled')).toBeDefined()
    chat.clearChat()                                            // 로그아웃·탈퇴·대화 지우기
    arrive({ intent: 'qa', answer: '7일 이내입니다.' })
    await settle()
    expect(chat.messages.value).toEqual([])
    expect(chat.busy.value).toBe(false)
    again.unmount()
  })
})

describe('인계 요약 화면', () => {
  it('저장해 둔 요약을 다시 열고(AI를 부르지 않는다), 저장하면 같은 항목을 덮어쓴다', async () => {
    const handover = vi.spyOn(api, 'handover')
    await profile('인계A', 'ACTIVITY'); await report('인계A', 1)
    await saveItem({ alias: '인계A', formId: 'handover_summary', title: '인계 요약', draft: { attendance_pattern: '대체로 정시 출석', attitude: '질문을 자주 함' } })
    const w = await open(HandoverView, '인계A', 'handover')
    expect(handover).not.toHaveBeenCalled()
    expect(w.find('[data-summary=attendance_pattern]').element.value).toBe('대체로 정시 출석')
    expect(w.find('[data-test=build-handover]').text()).toBe('인계 요약 다시 만들기')
    await w.find('[data-summary=attitude]').setValue('질문을 자주 하고 필기를 꼼꼼히 함')
    await w.find('[data-test=save-handover]').trigger('click')
    await settle()
    const saved = (await listItems('인계A')).filter((x) => x.formId === 'handover_summary')
    expect(saved).toHaveLength(1)
    expect(saved[0].draft).toMatchObject({ attitude: '질문을 자주 하고 필기를 꼼꼼히 함' })
    expect(saved[0].draft).not.toHaveProperty('text')   // 원문(text)이 없는 것이 내가 만든 요약이다
  })
})

describe('종합계획서② 화면', () => {
  it('종합계획서①에서 고쳐 쓴 멘토링 구성을 그대로 보낸다 (기본안으로 바뀌지 않는다). 저장하면 체크리스트가 뜬다', async () => {
    const structure = '17:00~17:20 지난 과제 점검\n17:20~18:00 개념학습'   // 멘토가 ①에서 직접 고쳐 쓴 글
    const pre = await saveItem({ alias: '계획A', formId: 'plan_initial', title: '종합계획서①', draft: { learning_goal: '(1) 수학의 시작 완강', diagnosis: '(과목역량) 기본기는 있음', structure, rules: '시간 지키기' },
      extra: { rows: [{ date: '2026-10-12', time: '17:00', content: '진단' }] } })
    const sent = []
    vi.spyOn(api, 'draft').mockImplementation(async (formId, inputs, extra) => {
      sent.push(extra)
      return { draft: { learning_goal: ['① 수학의 시작 완강'], diagnosis: inputs.diagnosis, structure: extra.memo.structure ?? '기본안', rules: inputs.rules }, pii_masked: [], missing_questions: [], warnings: [], reminders: [] }
    })
    const update = vi.fn()
    const w = mount(PlanStage, { props: { alias: '계획A', profile: { name: '계획A', grade: '고1', subject: '수학', course: '메가스터디 수학의 시작', duration: '60', start_datetime: '2026-10-12T17:00', stage: 'PLAN', term: 1 }, items: [pre], update },
      global: { stubs: { CurriculumEditor: true } } })
    await settle()
    expect(w.find('[data-field=structure]').element.value).toBe(structure)
    await w.find('form').trigger('submit')
    await settle()
    expect(sent.at(-1).memo.structure).toBe(structure)
    expect(update).toHaveBeenCalled()
    expect(checklist.title).toBe('종합계획서②')
    expect(checklist.items.find((i) => i.no === '1-5').mark).toBe('o')
  })
})
