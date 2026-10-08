import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import AnswerCard from '../src/components/AnswerCard.vue'
import DraftResult from '../src/components/DraftResult.vue'
import SchemaForm from '../src/components/SchemaForm.vue'
import { emptyInputs, inputFields } from '../src/lib/formFields'

// 저장소의 forms/*.json (backend가 /api/forms로 그대로 내려주는 파일)
const form = (id) => JSON.parse(readFileSync(resolve(process.cwd(), '..', 'forms', `${id}.json`), 'utf-8'))
const stubs = { 'router-link': { template: '<a><slot /></a>' } }

describe('SchemaForm', () => {
  it('스키마대로 입력 칸을 그리고 값을 올려 보낸다', async () => {
    const fields = inputFields(form('activity_report'))
    const w = mount(SchemaForm, { props: { fields, modelValue: emptyInputs(fields) } })
    expect(w.findAll('label.field')).toHaveLength(fields.length)
    expect(w.find('[data-key="mentee_name"]').exists()).toBe(false)
    expect(w.find('select[data-key="progress_scale"]').findAll('option')).toHaveLength(6)
    await w.find('[data-key="session_no"]').setValue('3')
    expect(w.emitted('update:modelValue')[0][0].session_no).toBe('3')
  })
})

describe('DraftResult', () => {
  const result = {
    draft: { duration: '60', weekday: '월', start_datetime: '2026-10-12 20:00', learning_goal: '문학 감 잡기', diagnosis: '1회차에 자세한 상담 예정',
      structure: '10분 확인', rules: '시간 준수', curriculum: ['1회차 계획', '2회차 계획'] },
    missing_questions: [{ key: 'weekday', label: '학습 요일', question: "'학습 요일'을(를) 알려 주세요." }],
    warnings: ['활동규칙은 기본 예시입니다.'], reminders: ['종합계획서①은 등록 후 수정할 수 없습니다.'], pii_masked: ['학교명'],
  }

  it('되물을 질문, 경고, 가린 정보, 안내를 보여준다', () => {
    const w = mount(DraftResult, { props: { form: form('plan_initial'), result } })
    expect(w.find('[data-test="missing"]').text()).toContain('학습 요일')
    expect(w.find('[data-test="warnings"]').text()).toContain('기본 예시')
    expect(w.find('[data-test="pii"]').text()).toContain('학교명')
    expect(w.find('[data-test="reminders"]').text()).toContain('수정할 수 없습니다')
    expect(w.find('[data-draft="curriculum"]').element.value).toBe('1회차 계획\n2회차 계획')
  })

  it('필드별로 고칠 수 있고, 고친 값을 올려 보낸다', async () => {
    const w = mount(DraftResult, { props: { form: form('plan_initial'), result } })
    await w.find('[data-draft="curriculum"]').setValue('1회차 수정\n\n2회차 계획\n3회차 추가')
    const draft = w.emitted('change').at(-1)[0]
    expect(draft.curriculum).toEqual(['1회차 수정', '2회차 계획', '3회차 추가'])
    expect(draft.learning_goal).toBe('문학 감 잡기')
  })

  it('종합계획서①은 복사 전에 수정 불가 경고를 한 번 띄운다', async () => {
    const writeText = vi.fn(async () => {})
    Object.assign(navigator, { clipboard: { writeText } })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValue(true)
    const w = mount(DraftResult, { props: { form: form('plan_initial'), result, confirmBeforeCopy: '등록 후 수정 불가' } })
    await w.find('[data-copy="learning_goal"]').trigger('click')
    expect(writeText).not.toHaveBeenCalled() // 취소하면 복사하지 않는다
    await w.find('[data-copy="learning_goal"]').trigger('click')
    await w.find('[data-copy="diagnosis"]').trigger('click')
    await vi.waitFor(() => expect(writeText).toHaveBeenCalledTimes(2))
    expect(writeText).toHaveBeenCalledWith('문학 감 잡기')
    expect(confirm).toHaveBeenCalledTimes(2) // 확인한 뒤에는 다시 묻지 않는다
  })

  it('개인정보 칸은 자리표시만 보여주고 복사 버튼을 두지 않는다', () => {
    const r = { draft: { mentee_name: '[멘티명]', goal: '지수법칙' }, missing_questions: [], warnings: [], reminders: [], pii_masked: [] }
    const w = mount(DraftResult, { props: { form: form('activity_report'), result: r } })
    expect(w.find('[data-copy="mentee_name"]').exists()).toBe(false)
    expect(w.find('[data-draft="mentee_name"]').exists()).toBe(false)
    expect(w.text()).toContain('[멘티명]')
    expect(w.find('[data-test="missing"]').exists()).toBe(false)
  })
})

describe('AnswerCard', () => {
  it('근거와 문의처를 카드로, 이음단이면 오픈채팅 버튼을 보여준다', () => {
    const res = { intent: 'qa', answer: '이음단과 협의해 주세요.', citations: ['활동가이드 p.37 출결 규정'], route: '이음단',
      route_info: '소속 자치구 이음단 (카카오톡 오픈채팅)', route_link: 'https://open.kakao.com/o/abc', pii_masked: ['학교명'],
      inquiry_draft: '안녕하세요, 서울런 멘토입니다.', inquiry_contact: 'https://open.kakao.com/o/abc' }
    const w = mount(AnswerCard, { props: { res }, global: { stubs } })
    expect(w.find('[data-test="citations"]').text()).toContain('p.37')
    expect(w.find('[data-test="route"] a').attributes('href')).toBe('https://open.kakao.com/o/abc')
    expect(w.find('[data-test="inquiry"]').text()).toContain('서울런 멘토입니다')
    expect(w.find('[data-test="pii"]').text()).toContain('학교명')
  })

  it('주소가 없으면 설정 안내를, 문의처가 없으면 카드를 그리지 않는다', () => {
    const base = { intent: 'qa', answer: '답', citations: [], pii_masked: [] }
    const w = mount(AnswerCard, { props: { res: { ...base, route: '이음단', route_info: '이음단', route_link: null } }, global: { stubs } })
    expect(w.find('[data-test="route"] a').exists()).toBe(false)
    expect(w.find('[data-test="route"]').text()).toContain('설정에서')
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
