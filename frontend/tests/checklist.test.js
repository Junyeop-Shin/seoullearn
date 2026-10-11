import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it } from 'vitest'
import ChecklistDialog from '../src/components/ChecklistDialog.vue'
import { checklist, completionChecklist, planChecklist, reportChecklist, showChecklist } from '../src/lib/checklist'

const marks = (items) => Object.fromEntries(items.map((i) => [i.no, i.mark]))

describe('보고서 체크리스트 (활동가이드의 표를 화면에 적은 글로 판단)', () => {
  it('종합계획서: 다 적으면 ○, 일부만 적으면 △와 빠진 것, 비면 ✕. 첨부 등록은 알 수 없어 △', () => {
    const rows = Array.from({ length: 16 }, (_, i) => ({ online: `${i + 1}강`, mentoring: '개념 정리' }))
    const full = { mentee: '오가상 (고1)', subject: '수학', course: '메가스터디 수학의 시작', schedule: '매주 화 17:00~18:00', goals: ['완강', '', '', '입시 정보 찾기'],
      diag: ['기본기 있음', '내신 4등급', '', '자율학습 부족'], rows, structure: '17:00~17:10 확인\n17:10~17:50 개념학습', rules: '시간 지키기' }
    expect(marks(planChecklist(full))).toEqual({ '1-1': 'o', '1-2': 'o', '1-3': 'o', '1-4': 'o', '1-5': 'o', '1-6': 'o', '1-7': 'tri' })

    const part = planChecklist({ ...full, course: '', goals: ['완강', '', '', ''], diag: ['', '', '', ''], rows: [...rows.slice(0, 14), { online: '', mentoring: '' }, { online: '', mentoring: '' }],
      structure: '개념학습 후 문제 풀이', rules: '' })
    expect(marks(part)).toEqual({ '1-1': 'tri', '1-2': 'tri', '1-3': 'x', '1-4': 'tri', '1-5': 'tri', '1-6': 'x', '1-7': 'tri' })
    expect(part[0].note).toBe('빠진 것: 학습사이트 강좌명')
    expect(part[3].note).toBe('2개 주차가 비어 있습니다.')
    expect(planChecklist({ ...full, rows: [] })[3].mark).toBe('x')
    expect(planChecklist({ ...full, rows: rows.map((r) => ({ ...r, online: '' })) })[3]).toMatchObject({ mark: 'tri', note: '온라인 강의를 적은 주차가 없습니다.' })
  })

  it('활동보고서: 머리말 줄로 판단하고, 제출 기한은 진행일로부터 7일', () => {
    const v = { absent: false, status: '출석', content: '학습범위: 지수법칙\n학습목표: 식을 계산할 수 있다', progress: '출결: 정시 출석 (17:02~18:04)\n인강: 메가스터디 5~6강 수강함\n과제: RPM 10p - 수행함',
      understanding: '예제는 혼자 품\n풀이 과정을 건너뜀\n과제: RPM 20p 풀기', task: true, date: '2026-10-06', photos: true }
    expect(marks(reportChecklist(v, '2026-10-11'))).toEqual({ '2-1': 'o', '2-2': 'o', '2-3': 'o', '2-4': 'o', '2-5': 'o', '2-6': 'tri' })
    expect(reportChecklist(v, '2026-10-11')[3].note).toBe('10.13까지 제출해 주세요.')
    expect(reportChecklist(v, '2026-10-13')[3]).toMatchObject({ mark: 'tri', note: '오늘(10.13)이 제출 기한입니다.' })
    expect(reportChecklist(v, '2026-10-14')[3]).toMatchObject({ mark: 'x', note: '제출 기한(10.13)이 지났습니다.' })

    // 과제를 냈는데 과제 줄이 없으면 △, 낸 과제가 없으면 과제 줄을 찾지 않는다
    const noTask = { ...v, progress: '출결: 정시 출석\n인강: 5~6강 수강함' }
    expect(reportChecklist(noTask, '2026-10-11')[1]).toMatchObject({ mark: 'tri', note: '빠진 것: 과제 수행' })
    expect(reportChecklist({ ...noTask, task: false }, '2026-10-11')[1].mark).toBe('o')
    // 머리말 없이 적은 글은 빠졌다고 하지 않고 확인을 부탁한다. 과제 줄만 있는 학습 이해도는 비어 있는 것으로 본다
    const loose = reportChecklist({ ...v, content: '지수법칙 복습', progress: '5분 일찍 옴', understanding: '과제: RPM 20p 풀기', photos: false }, '2026-10-11')
    expect(marks(loose)).toMatchObject({ '2-1': 'tri', '2-2': 'tri', '2-3': 'x', '2-5': 'tri' })
    expect(loose[2].note).toContain('과제·인강 줄만 있습니다')   // 글이 있는 칸을 '비어 있습니다'라고 하지 않는다
    expect(reportChecklist({ ...v, understanding: '' }, '2026-10-11')[2].note).toBe('학습 이해도 칸이 비어 있습니다.')
    expect(reportChecklist({ ...v, content: '', understanding: '예제는 혼자 품' }, '2026-10-11').slice(0, 3).map((i) => i.mark)).toEqual(['x', 'o', 'tri'])
  })

  it('진행하지 못한 회차는 학습 내용 항목(2-1, 2-3)을 빼고 본다', () => {
    const items = reportChecklist({ absent: true, status: '무단결석', content: '멘티 무단결석으로 멘토링을 진행하지 못함.', progress: '', understanding: '', task: false, date: '2026-10-06', photos: false }, '2026-10-07')
    expect(items.map((i) => i.no)).toEqual(['2-2', '2-4', '2-5', '2-6'])
    expect(items[0]).toMatchObject({ mark: 'o', note: '회차 상태: 무단결석' })
    expect(items[2].mark).toBe('tri')
  })

  it('완료보고서: 감성케어 상담이 비어 있으면 직접 적으라고 알린다', () => {
    expect(marks(completionChecklist({ content: '- 플래너 습관', achievement: '- 30강 수강', emotional_care: '진로 고민 상담', requests: '' }))).toEqual({ '3-1': 'o', '3-2': 'o', '3-3': 'o', '3-4': 'tri', '3-5': 'tri' })
    expect(marks(completionChecklist({ content: '', achievement: ' ', emotional_care: '', requests: '- 교재 요청' }))).toMatchObject({ '3-1': 'x', '3-2': 'x', '3-3': 'tri' })
    expect(completionChecklist({ content: '', achievement: '', emotional_care: '', requests: '' })[2]).toMatchObject({ mark: 'x' })
  })

  it('팝업: 참고용이라고 알리고, 항목마다 ○ △ ✕를 보여 주며, [확인]으로 닫는다', async () => {
    const w = mount(ChecklistDialog, { attachTo: document.body })
    expect(w.find('dialog').element.open).toBe(false)
    showChecklist('완료보고서', completionChecklist({ content: '- 플래너 습관', achievement: '', emotional_care: '', requests: '' }))
    await nextTick()
    expect(w.find('dialog').element.open).toBe(true)
    expect(w.text()).toContain('완료보고서 체크리스트')
    expect(w.text()).toContain('참고용')
    expect(w.findAll('li').map((li) => li.find('.mark').text())).toEqual(['○', '✕', '✕', '△', '△'])
    expect(w.find('[data-check="3-2"] .mark').attributes('aria-label')).toBe('빠짐')
    await w.find('[data-test=checklist-ok]').trigger('click')
    await nextTick()
    expect(checklist.items).toBe(null)
    expect(w.find('dialog').element.open).toBe(false)
    // 저장한 화면이 이미 사라졌거나 가려졌으면(응답이 늦게 온 경우) 다른 화면 위에 띄우지 않는다
    showChecklist('완료보고서', [], { isUnmounted: true })
    showChecklist('완료보고서', [], { isDeactivated: true })
    expect(checklist.items).toBe(null)
    w.unmount()
  })
})
