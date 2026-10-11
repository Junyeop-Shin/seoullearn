import { reactive } from 'vue'
import { monthDay } from './photos'
import { todayText } from './schedule'

// 보고서 체크리스트: 활동가이드의 '보고서 작성 시 빠진 것이 없는지 확인해보세요' 표를 화면에 적은 글로 판단한다 (규칙, AI 미사용).
// mark: 'o' 작성함 / 'tri' 일부만 작성했거나 화면에서 알 수 없어 직접 확인 / 'x' 빠짐. 참고용이라 아무것도 막지 않는다.
export const checklist = reactive({ title: '', items: null })   // 팝업 하나를 앱 틀이 띄운다 (저장한 뒤 단계 화면이 다시 그려져도 남게)
/** from: 저장한 화면(getCurrentInstance()). 응답이 늦게 와 그 화면이 이미 사라졌으면 띄우지 않는다 (다른 화면 위에 뜨지 않게) */
export const showChecklist = (title, items, from) => { if (!from?.isUnmounted && !from?.isDeactivated) Object.assign(checklist, { title, items }) }

const has = (v) => !!String(v ?? '').trim()
const rowsOf = (t) => String(t || '').split('\n').map((x) => x.trim()).filter(Boolean)
const mark = (m, note = '') => ({ mark: m, note })
/** 여러 부분 가운데 채운 것으로 판단한다: 모두 → o, 일부 → tri, 없음 → x. parts: [[이름, 채웠는지], …] */
function byParts(parts) {
  const missing = parts.filter(([, ok]) => !ok).map(([name]) => name)
  return missing.length ? mark(missing.length === parts.length ? 'x' : 'tri', `빠진 것: ${missing.join(', ')}`) : mark('o')
}
/** '머리말: 내용' 줄이 있는지 (예: '학습범위: …') */
const headed = (text, head) => rowsOf(text).some((l) => l.startsWith(`${head}:`) && has(l.slice(head.length + 1)))
/** 머리말을 쓰지 않고 적은 글은 빠졌다고 하지 않고 확인을 부탁한다 */
const orAsk = (judged, text, ask) => (judged.mark === 'x' && has(text) ? mark('tri', ask) : judged)
const UNSEEN = '화면에서 알 수 없습니다. '   // 플랫폼에서 하는 일은 판단하지 못한다
const LATER = '제출한 뒤에 확인할 일입니다.'

/** 종합계획서 (1-1 ~ 1-7). v: {mentee, subject, course, schedule, goals[4], diag[4], rows[{online, mentoring}], structure, rules} */
export function planChecklist(v) {
  const weeks = v.rows || []
  const written = weeks.filter((r) => has(r.online) || has(r.mentoring)).length
  const timed = rowsOf(v.structure).filter((l) => /\d{1,2}:\d{2}/.test(l)).length
  return [
    { no: '1-1', text: '멘토링 기본 정보를 정확하게 작성했다.', ...byParts([['멘티 성명', has(v.mentee)], ['멘토링 과목', has(v.subject)], ['학습사이트 강좌명', has(v.course)], ['일정', has(v.schedule)]]) },
    { no: '1-2', text: '학습목표 항목에 학습사이트 수강목표와 진로·진학 목표를 작성했다.', ...byParts([['① 학습사이트 수강 목표', has(v.goals[0])], ['④ 진로·진학 목표', has(v.goals[3])]]) },
    { no: '1-3', text: '멘티 진단 항목에 멘티의 멘토링 과목 역량과 학습 수준, 학습 태도에 대해 상담하고 평가한 내용을 작성했다.',
      ...byParts([['과목역량', has(v.diag[0])], ['학습수준 및 희망진로', has(v.diag[1])], ['학습습관 및 태도', has(v.diag[3])]]) },
    { no: '1-4', text: '학습사이트 강의를 바탕으로 회차(주차)별 커리큘럼 항목을 작성했다.',
      ...(!written ? mark('x', '커리큘럼 표가 비어 있습니다.') : written < weeks.length ? mark('tri', `${weeks.length - written}개 주차가 비어 있습니다.`)
        : weeks.some((r) => has(r.online)) ? mark('o') : mark('tri', '온라인 강의를 적은 주차가 없습니다.')) },
    { no: '1-5', text: '멘토링 구성 항목에 시간 단위로 1회차(주차)의 활동 내용을 작성했다.',
      ...(!has(v.structure) ? mark('x', '멘토링 구성 칸이 비어 있습니다.') : timed >= 2 ? mark('o') : mark('tri', "'17:00~17:10 개념학습'처럼 시각을 붙여 적어 주세요.")) },
    { no: '1-6', text: '멘티와 협의한 멘토링 활동 규칙을 해당 항목에 작성했다.', ...(has(v.rules) ? mark('o') : mark('x', '활동규칙 칸이 비어 있습니다.')) },
    { no: '1-7', text: '1회차(주차) 활동보고서 첨부파일에 종합계획서를 기간 내에 등록했다.', ...mark('tri', `${UNSEEN}서식 파일을 내려받아 1회차 활동보고서에 첨부해 주세요.`) },
  ]
}

/** 제출 기한: 진행일로부터 7일 이내 (서버의 안내와 같은 규칙) */
function deadline(date, today) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date || '')
  if (!m) return mark('tri', '진행일을 적으면 제출 기한을 알려 드립니다.')
  const due = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3] + 7)).toISOString().slice(0, 10)
  return today < due ? mark('o', `${monthDay(due)}까지 제출해 주세요.`) : today === due ? mark('tri', `오늘(${monthDay(due)})이 제출 기한입니다.`) : mark('x', `제출 기한(${monthDay(due)})이 지났습니다.`)
}

/** 활동보고서 (2-1 ~ 2-6). v: {absent, status, content, progress, understanding, task(지난 회차에 낸 과제가 있는지), date, photos(시작·종료 사진을 넣었는지)}.
 * 진행하지 못한 회차(임박취소, 무단결석, 인정결석)는 학습 내용을 적지 않으므로 2-1과 2-3을 뺀다. */
export function reportChecklist(v, today = todayText()) {
  const parts = [['출결', headed(v.progress, '출결')], ['인강 수강 여부', headed(v.progress, '인강')], ...(v.task ? [['과제 수행', headed(v.progress, '과제')]] : [])]
  const notes = rowsOf(v.understanding).filter((l) => !/^(과제|인강):/.test(l)).length   // 다음 회차까지 낸 과제 줄은 세지 않는다
  const all = [
    { no: '2-1', text: '해당 회차(주차)의 학습(혹은 멘토링) 범위와 목표를 작성했다.',
      ...orAsk(byParts([['학습범위', headed(v.content, '학습범위')], ['학습목표', headed(v.content, '학습목표')]]), v.content, '학습범위와 학습목표를 모두 적었는지 확인해 주세요.') },
    { no: '2-2', text: '멘티의 출결과 학습사이트 수강 여부, 과제 수행 정도를 확인하여 작성했다.',
      ...(v.absent ? mark('o', `회차 상태: ${v.status}`) : orAsk(byParts(parts), v.progress, '출결, 인강 수강 여부, 과제 수행을 모두 적었는지 확인해 주세요.')) },
    { no: '2-3', text: '해당 회차(주차)의 멘토링(학습) 내용과 멘티의 참여도와 이해도를 작성했다.',
      ...(!notes ? mark('x', has(v.understanding) ? '과제·인강 줄만 있습니다. 진행한 내용과 멘티의 참여도·이해도를 적어 주세요.' : '학습 이해도 칸이 비어 있습니다.') : notes === 1 ? mark('tri', '진행한 내용과 멘티의 참여도·이해도를 함께 적었는지 확인해 주세요.') : mark('o')) },
    { no: '2-4', text: '활동보고서 제출기한(7일 이내)을 준수했다.', ...deadline(v.date, today) },
    { no: '2-5', text: '출석 증빙 사진을 규정에 맞게 첨부파일에 업로드했다.',
      ...(v.absent ? mark('tri', '진행하지 못한 회차는 저장할 때 안내한 증빙을 첨부해 주세요.')
        : v.photos ? mark('o', '시작·종료 사진을 넣었습니다. 내려받은 압축 파일을 첨부해 주세요.') : mark('tri', `${UNSEEN}시작·종료 인증사진을 첨부했는지 확인해 주세요.`)) },
    { no: '2-6', text: '보고서 제출 후 승인 여부를 확인했고, 보완 요청 시 보완사유를 확인하여 기한 내(7일 내) 재제출했다.', ...mark('tri', LATER) },
  ]
  return v.absent ? all.filter((i) => !['2-1', '2-3'].includes(i.no)) : all
}

/** 완료보고서 (3-1 ~ 3-5). v: 화면의 네 칸 {content, achievement, emotional_care, requests} */
export function completionChecklist(v) {
  return [
    { no: '3-1', text: '1회기 동안 진행한 멘토링 내용을 모두 작성했다.', ...(has(v.content) ? mark('o') : mark('x', '멘토링 내용 칸이 비어 있습니다.')) },
    { no: '3-2', text: '1회기 동안 멘토링을 진행하며 성취한 내용(학습진도, 성적향상, 진로 설정 등)을 작성했다.', ...(has(v.achievement) ? mark('o') : mark('x', '학습목표 대비 성취도 칸이 비어 있습니다.')) },
    { no: '3-3', text: '1회기 동안 진행된 상담 활동이나 고민 해결 등의 내용을 작성했다.',
      ...(has(v.emotional_care) ? mark('o') : mark(has(v.requests) ? 'tri' : 'x', '감성케어 상담은 초안을 만들지 않습니다. 상담한 내용이 있으면 직접 적어 주세요.')) },
    { no: '3-4', text: '사전에 멘티와 연장 여부를 논의해 필요한 절차를 이행했다.', ...mark('tri', `${UNSEEN}멘티와 연장 여부를 이야기했는지 확인해 주세요.`) },
    { no: '3-5', text: '보고서 제출 후 최종 승인 여부를 확인했다.', ...mark('tri', LATER) },
  ]
}
