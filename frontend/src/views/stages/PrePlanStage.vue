<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../../api/client'
import CurriculumEditor from '../../components/CurriculumEditor.vue'
import { copyText } from '../../lib/copy'
import { toText } from '../../lib/formFields'
import { displayName } from '../../lib/mentee'
import { CURRICULUM_SUBJECTS, GRADES, SEMESTERS, findUnits, genericHints, gradeKey, hasExams, loadCurriculum, spreadUnits } from '../../lib/curriculum'
import { DIAG_SLOTS, GOAL_SLOTS, changedLines, composeSlots, parseSlots, platformSafe } from '../../lib/plan'
import { curriculumLines, handoverForDraft, handoverFromVault, handoverNote, latestOf, termSummaryFromVault, termSummaryText } from '../../lib/reports'
import { WEEKDAYS, weekdayOf } from '../../lib/schedule'
import { totalRounds } from '../../lib/stage'
import { revealError } from '../../lib/reveal'
import { toast } from '../../lib/toast'
import { loadSettings } from '../../stores/settings'
import { saveItem } from '../../stores/vault'

// 종합계획서①(사전 종합계획서): 1회차 전에 서울런 플랫폼에 입력한다.
// 플랫폼 입력 칸과 같은 순서로 한 묶음에 모았다. 여기에 적은 글이 곧 옮길 내용이고, 항목마다 복사 버튼이 있다.
// 학습목표와 학생진단은 서식 예시의 항목별로 받아 '(1) …', '(과목역량) …' 줄로 묶는다. 커리큘럼은 학습 내용만 대략 적는다.
const FORM_ID = 'plan_initial'
defineOptions({ inheritAttrs: false })   // 멘티 화면이 모든 단계에 같은 값을 넘긴다: 안 쓰는 값이 화면 요소에 붙지 않게 한다
const props = defineProps({ alias: { type: String, required: true }, profile: { type: Object, required: true }, items: { type: Array, required: true },
  update: { type: Function, required: true } })
const mentor = loadSettings()
const saved = computed(() => latestOf(props.items, FORM_ID))
const start = ref(props.profile.start_datetime || '')
const weekday = ref(props.profile.regularSchedule?.[0]?.weekday || weekdayOf(props.profile.start_datetime))
const goal = reactive({ parts: ['', '', '', ''], rest: '' })
const diag = reactive({ parts: ['', '', '', ''], rest: '' })
const text = reactive({ structure: '', rules: '' })
const rows = ref([])
const notes = ref([])
const busy = ref('')
const error = ref('')
const filled = ref('')
const defaults = {}   // 규칙으로 만든 기본안 (멘토링 구성, 활동규칙). 고치지 않았으면 서버에 보내지 않는다
const rounds = computed(() => totalRounds(props.profile))
const subject = computed(() => [props.profile.subject, props.profile.subjectEtc].filter(Boolean).join(' / '))
// 참고 자료는 두 경우를 나눠 다룬다.
// - previous: 같은 멘토가 같은 멘티와 지난 회기를 마치고 이어 가는 경우 (지난 회기 요약)
// - handover: 다른 멘토에게 멘티를 인계받은 경우 (인계받은 글)
// 지난 회기 요약이 있으면 이어 가는 경우로 보고, 인계받은 글은 쓰지 않는다 (지난 회기 전의 내용이다)
const previous = termSummaryFromVault(props.items)
const handoverDraft = previous ? null : handoverFromVault(props.items)
const handover = handoverNote(handoverDraft)                       // 이전 멘토에게 인계받은 글 (참고용)
const source = previous ? 'previous' : handoverForDraft(handoverDraft) ? 'handover' : ''
const SOURCE = {
  previous: { button: '지난 회기에 이어 초안 채우기', text: '지난 회기 요약을 바탕으로, 비워 둔 학습목표와 학생진단의 초안을 채워 드립니다.' },
  handover: { button: '인계받은 내용으로 초안 채우기', text: '이전 멘토에게 인계받은 내용(출석, 과제, 태도, 수강 진도)을 바탕으로 학생진단과 수강 목표의 초안을 채워 드립니다.' },
}
// AI가 바꾼 내용: 무엇이 새로 들어갔고 무엇이 어떻게 고쳐졌는지 보여 주고, 되돌릴 수 있게 한다
const changes = ref(null)   // {mode, items: [{label, before, after}], undo: 되돌릴 값}
// 플랫폼은 특수문자에서 오류가 날 수 있어 학습목표의 머리말은 (1)~(4)로 쓴다
const goalText = computed(() => composeSlots(GOAL_SLOTS, goal.parts, goal.rest, true))
const diagText = computed(() => composeSlots(DIAG_SLOTS, diag.parts, diag.rest))
// 1회차 일시를 정하면 학습요일을 그 요일로 맞춘다 (다르면 고칠 수 있다)
watch(start, (v, old) => { if (!weekday.value || weekday.value === weekdayOf(old)) weekday.value = weekdayOf(v) })

function load(target, slots, value, fallback) {
  const { parts, rest } = parseSlots(slots, value)
  // 머리말 없이 적어 둔 예전 글은 가장 가까운 항목에 넣는다
  if (rest && !parts.some(Boolean) && fallback !== undefined) { parts[fallback] = rest.replace(/\s*\n\s*/g, ' '); target.rest = '' } else target.rest = rest
  target.parts = parts
}

// 서버가 돌려준 글을 항목 칸에 다시 넣는다. 멘토가 적은 글이 말없이 사라지지 않게, 형식이 깨졌거나 항목이 비워졌으면 알린다
function applyText(target, slots, value, label, keepRest) {
  if (!value.trim()) return []
  const before = [...target.parts]
  const filled = before.filter((v) => v.trim()).length
  let { parts, rest } = parseSlots(slots, value)
  if (!parts.some(Boolean) && filled) {
    // 항목 머리말이 빠진 채 돌아왔다: 줄 수가 같으면 차례대로 넣고, 다르면 적어 둔 글을 그대로 둔다
    const lines = rest.split('\n').filter((x) => x.trim())
    if (lines.length !== filled) return [`AI가 ${label}의 항목 형식을 지키지 않아 적어 둔 글을 그대로 두었습니다. 한 번 더 누르거나 직접 고쳐 주세요.`]
    let k = 0
    parts = before.map((v) => (v.trim() ? lines[k++] : ''))
    rest = ''
  }
  target.parts = parts
  target.rest = keepRest ? rest : ''
  const emptied = slots.filter((s, i) => before[i].trim() && !parts[i]).map((s) => s.label)
  return emptied.length ? [`${label}의 '${emptied.join("', '")}' 항목이 비워졌습니다. 개인정보나 계획서에 넣지 않는 내용만 있었을 수 있습니다.`] : []
}

const inputs = () => ({ duration: String(props.profile.duration || '60'), weekday: weekday.value, start_datetime: start.value.replace('T', ' ') })

onMounted(async () => {
  loadCurriculum().then((d) => { curriculum.value = d })   // 주차별 예시와 '교과과정으로 채우기'에 쓴다
  const s = saved.value
  const done = []
  if (s) {
    // 저장해 둔 계획서를 다시 연다
    load(goal, GOAL_SLOTS, s.extra?.memo?.learning_goal)
    load(diag, DIAG_SLOTS, s.extra?.memo?.diagnosis)
    Object.assign(text, { structure: s.extra?.memo?.structure || '', rules: s.extra?.memo?.rules || '' })
    if (s.extra?.rows?.length) rows.value = s.extra.rows
    // 1회차 일시는 멘티 정보가 기준이다 (멘티 설정에서 고친 값이 저장본의 옛 값으로 되돌아가지 않게). 학습요일은 일시가 저장본과 같을 때만 저장본을 쓴다
    start.value = start.value || (s.inputs?.start_datetime || '').replace(' ', 'T')
    if (s.inputs?.weekday && start.value.replace('T', ' ') === s.inputs.start_datetime) weekday.value = s.inputs.weekday
  } else {
    load(goal, GOAL_SLOTS, props.profile.goal, 1)
    load(diag, DIAG_SLOTS, props.profile.level, 3)
    // 인계받은 글의 출석·과제·태도를 '학습습관 및 태도'에 미리 넣는다 (항목 이름이 붙은 인계 글만 가능하다)
    const ho = source === 'handover' ? handoverForDraft(handoverDraft) : null
    const habit = ho && [ho.attendance_pattern, ho.homework_pattern, ho.attitude].filter(Boolean).join(' ')
    if (habit && !diag.parts[3]) { diag.parts[3] = habit; done.push('학생진단(인계받은 내용)') }
    // 지난 회기를 마칠 때 적어 둔 이번 회기 강좌를 수강 목표에 미리 넣는다 (규칙, AI 미사용)
    if (previous?.next_course && !goal.parts[0]) { goal.parts[0] = `${previous.next_course} 수강`; done.push('학습목표(이번 회기 강좌)') }
  }
  try {
    // 멘토링 구성과 활동규칙의 기본안 (서식 예시를 따른 글, AI 미사용)
    const res = await api.draft(FORM_ID, inputs(), { only: [], mode: props.profile.mode || '온라인' })
    for (const k of ['structure', 'rules']) {
      defaults[k] = toText(res.draft[k])
      if (!text[k].trim()) { text[k] = defaults[k]; if (!s) done.push(k === 'structure' ? '멘토링 구성' : '활동규칙') }
    }
  } catch (e) {
    error.value = e.message
  }
  if (done.length) filled.value = `${done.join(', ')}에 예시를 넣어 두었습니다. 멘티와 이야기한 내용에 맞게 고쳐 주세요.`
})

// 1회차 시각을 바꾸면 기본안 그대로인 멘토링 구성의 시각도 따라간다
let asked = 0
watch(start, async () => {
  if (!start.value || text.structure.trim() !== (defaults.structure || '').trim()) return
  const mine = (asked += 1)
  try {
    const res = await api.draft(FORM_ID, inputs(), { only: [], mode: props.profile.mode || '온라인' })
    // 늦게 온 예전 응답은 버린다. 기다리는 사이 멘토가 칸을 고쳤으면 그 글도 덮지 않는다
    if (mine === asked && text.structure.trim() === (defaults.structure || '').trim()) defaults.structure = text.structure = toText(res.draft.structure)
  } catch { /* 기본안을 못 받아도 적어 둔 글은 그대로다 */ }
})

// 교과과정으로 채우기: 강좌가 정해지기 전의 임시 커리큘럼. 학년·학기·과목의 교육과정 단원(자료 파일)을 주차에 나눈다.
// 규칙만 쓰고(AI 미사용) 브라우저 안에서 계산하므로 학년과 과목이 서버로 나가지 않는다
// 과목은 멘티의 신청 과목 그대로다 (신청 과목이 '기타'일 때만 고른다). 학년과 학기는 멘티의 학년과 1회차 날짜로 기본값을 잡되 바꿀 수 있다:
// 기초가 부족하면 아래 학년이나 지난 학기 내용부터 계획할 수 있다
const fixedSubject = CURRICULUM_SUBJECTS.includes(props.profile.subject) ? props.profile.subject : ''
const semesterOf = (datetime) => ((Number((datetime || '').slice(5, 7)) || new Date().getMonth() + 1) <= 7 ? '1학기' : '2학기')   // 8월부터 2학기
const curriculum = ref(null)
const general = reactive({ subject: fixedSubject, grade: gradeKey(props.profile.grade), semester: semesterOf(props.profile.start_datetime), course: '' })
let semesterPicked = false   // 멘토가 학기를 직접 골랐으면 1회차 날짜를 바꿔도 따라가지 않는다
watch(start, (v) => { if (!semesterPicked) general.semester = semesterOf(v) })
const found = computed(() => findUnits(curriculum.value, general.grade, general.semester, general.subject, general.course))
// 학년이나 과목을 바꿔 세부 과목 목록이 달라지면 고른 세부 과목을 비운다 (다른 학년의 과목이 남아 있지 않게)
watch(() => found.value.courses.join('|'), () => { if (!found.value.courses.includes(general.course)) general.course = '' })
const generalNote = ref('')
// 주차마다 칸에 흐리게 보여 줄 예시: 고른 학년·과목의 단원이 있으면 그것으로, 없으면 일반적인 흐름으로
const hints = computed(() => {
  const exam = hasExams(general.grade)
  const fromUnits = spreadUnits(found.value.units, rounds.value, exam)
  return fromUnits.length ? fromUnits : genericHints(rounds.value, exam)
})
function fillGeneral() {
  if (rows.value.some((r) => (r.content || '').trim()) && !window.confirm('적어 둔 학습 내용을 교육과정 단원으로 바꿉니다. 계속할까요?')) return
  const filled = spreadUnits(found.value.units, rounds.value, hasExams(general.grade))
  rows.value = rows.value.map((r, i) => ({ ...r, content: filled[i] ?? r.content }))
  generalNote.value = `${[general.grade, general.semester, found.value.name || general.subject].join(' ')} 단원 ${found.value.units.length}개를 ${rounds.value}주에 나눠 채웠습니다. 멘티의 교과서와 지금 진도에 맞게 고쳐 주세요.`
}

const memo = () => ({ learning_goal: goalText.value, diagnosis: diagText.value, structure: text.structure, rules: text.rules })

// mode: save(저장, AI 미사용) | fill(비워 둔 목표·진단의 초안을 참고 자료로 쓴다)
async function draft(mode) {
  const fill = mode === 'fill'
  // 기본안을 그대로 둔 칸은 보내지 않는다: 서버가 같은 기본안을 다시 넣는다
  const given = Object.fromEntries(Object.entries(memo()).filter(([k, v]) => v.trim() && v.trim() !== (defaults[k] || '').trim()))
  const extra = { mode: props.profile.mode || '온라인', memo: given, curriculum_lines: curriculumLines(rows.value),
    pre_contact: { subject_confirm: [subject.value, props.profile.mode].filter(Boolean).join(', '), site_course: props.profile.course || '' } }
  // 참고 자료는 초안 채우기에서만, 해당하는 한 가지만 넘긴다
  if (fill && source === 'handover') extra.handover = handoverForDraft(handoverDraft)   // 인계받은 글 가운데 허용된 네 항목만
  if (fill && source === 'previous') extra.previous_term = previous
  const snap = snapshot()
  const before = memo()
  // 저장은 AI를 부르지 않는다. 초안 채우기는 비워 둔 목표·진단만 채운다
  extra.only = fill ? ['learning_goal', 'diagnosis'].filter((k) => !before[k].trim()) : []
  if (fill && !extra.only.length) return null
  const res = await api.draft(FORM_ID, inputs(), extra)
  // 아동 안전 신호가 있으면 서버가 초안을 만들지 않고 운영사무국 안내만 돌려준다: 그 안내를 보여 주고 저장하지 않는다
  if (!Object.keys(res.draft).length) throw new Error(res.warnings[0] || '초안을 만들지 못했습니다. 잠시 후 다시 눌러 주세요.')
  if (fill && res.error) throw new Error('AI의 답을 읽지 못했습니다. 잠시 후 다시 눌러 주세요.')
  const out = Object.fromEntries(Object.keys(before).map((k) => [k, toText(res.draft[k])]))
  // 서버가 정리한 글(특수문자 정리, 채운 초안)을 같은 칸에 다시 넣는다
  const lost = [...applyText(goal, GOAL_SLOTS, out.learning_goal, '학습목표', true), ...applyText(diag, DIAG_SLOTS, out.diagnosis, '학생진단', false)]
  for (const k of ['structure', 'rules']) if (out[k].trim()) text[k] = out[k]
  if (fill) {
    // 무엇이 새로 들어갔는지 남긴다
    const items = snapshot().flatMap(([label, after], i) => changedLines(snap[i][1], after).map(([b, a]) => ({ label, before: b, after: a })))
    changes.value = items.length ? { items, undo: { goal: [...snap.slice(0, 4).map((x) => x[1])], diag: [...snap.slice(4, 8).map((x) => x[1])], structure: snap[8][1], rules: snap[9][1] } } : null
  }
  notes.value = [...lost, ...(res.pii_masked.length ? [`AI에 보내기 전에 가린 정보: ${res.pii_masked.join(', ')}`] : []), ...res.missing_questions.map((q) => q.question), ...res.warnings, ...res.reminders]
  return res
}

async function run(name, fn) {
  error.value = ''
  notes.value = []
  busy.value = name
  try {
    await fn()
  } catch (e) {
    error.value = e.message
    revealError()
  } finally {
    busy.value = ''
  }
}

// 지금 칸에 적힌 글 (항목 이름, 글). AI가 바꾸기 전후를 견주는 데 쓴다
function snapshot() {
  return [...GOAL_SLOTS.map((x, i) => [`학습목표 ${x.plain}`, goal.parts[i] || '']), ...DIAG_SLOTS.map((x, i) => [`학생진단 ${x.mark}`, diag.parts[i] || '']),
    ['멘토링 구성', text.structure], ['활동규칙', text.rules]]
}

function undoChanges() {
  const u = changes.value.undo
  goal.parts = [...u.goal]
  diag.parts = [...u.diag]
  Object.assign(text, { structure: u.structure, rules: u.rules })
  changes.value = null
  toast('AI가 바꾸기 전으로 되돌렸습니다.')
}

// 쓰기 전에 누르는 버튼: 인계받은 내용이나 지난 회기 요약이 있을 때 비워 둔 목표·진단의 초안을 채운다
const canFill = !!source
const fill = () => run('fill', async () => {
  const res = await draft('fill')
  toast(res ? (changes.value ? '초안을 채웠습니다. 새로 들어간 내용을 확인하고 고쳐 주세요.' : '참고 자료에서 채울 내용을 찾지 못했습니다.') : '학습목표와 학생진단에 이미 적은 내용이 있어 채우지 않았습니다.')
})

const save = () => run('save', async () => {
  const res = await draft('save')
  await saveItem({ id: saved.value?.id, alias: props.alias, formId: FORM_ID, title: '종합계획서①', draft: res.draft, inputs: inputs(),
    extra: { memo: memo(), rows: rows.value } })
  await props.update({ start_datetime: start.value, goal: goalText.value, level: diagText.value },
    '종합계획서①을 저장했습니다. 1회차를 마친 뒤 종합계획서②를 써 주세요.')
})

// 복사하는 글은 플랫폼에서 오류가 나지 않게 글자를 정리한다 (서버가 저장할 때 하는 정리와 같은 규칙)
const copy = (label, value) => copyText(platformSafe(value), label)
</script>

<template>
  <div>
    <p class="muted">1회차 전에 서울런 플랫폼에 입력하는 계획입니다. 다 쓴 뒤 맨 아래 [저장]을 먼저 누르고, 항목마다 [복사]해 플랫폼의 같은 칸에 붙여 넣어 주세요. 멘토링 시작일만 정하면 저장할 수 있고, 아직 정하지 못한 항목은 비워 두어도 됩니다. 매칭 후 7일 이내에 입력해 주세요.</p>
    <div v-if="error" class="box error" role="alert">{{ error }}</div>
    <div v-if="previous" class="mini pre" data-test="previous-term">
      <span class="t">지난 회기 요약 (참고)</span>{{ termSummaryText(previous) }}
    </div>
    <div v-if="handover" class="mini pre" data-test="handover-ref">
      <span class="t">이전 멘토에게 인계받은 내용 (참고)</span>{{ handover }}
    </div>
    <div v-if="filled" class="box ask closable" data-test="prefilled">
      <span>{{ filled }}</span><button type="button" aria-label="안내 닫기" data-test="close-prefilled" @click="filled = ''">×</button>
    </div>

    <fieldset class="card plan-form" :disabled="!!busy" data-test="plan-form">
      <div class="facts" data-test="auto">
        <div><span>멘토링 유형</span>{{ mentor.mentoringType || '멘토 설정에서 선택' }}</div>
        <div><span>멘티</span>{{ displayName(profile, alias) }}</div>
        <div><span>신청 과목</span>{{ subject || '-' }}</div>
        <div><span>멘토링 회당 학습시간</span>{{ profile.duration || '60' }}분 ({{ rounds }}주)</div>
      </div>

      <div class="form-grid">
        <label class="field"><span class="name">멘토링 시작일 및 멘토링 시작시간<span class="req">*</span></span><input v-model="start" type="datetime-local" data-plan="start" /></label>
        <label class="field"><span class="name">학습요일</span>
          <select v-model="weekday" data-plan="weekday"><option value="">선택해 주세요</option><option v-for="d in WEEKDAYS" :key="d" :value="d">{{ d }}요일</option></select>
        </label>
      </div>

      <div v-if="canFill" class="course-card" data-test="fill-box" :data-source="source">
        <strong>AI로 초안 채우기</strong>
        <p class="notice">{{ SOURCE[source].text }} 이미 적은 칸은 건드리지 않습니다. 채운 뒤 멘티와 이야기한 내용에 맞게 고쳐 주세요.</p>
        <button type="button" :disabled="!!busy || !start" data-test="fill" @click="fill">{{ busy === 'fill' ? '채우는 중…' : SOURCE[source].button }}</button>
        <span v-if="!start" class="notice">멘토링 시작일과 시작시간을 정하면 채울 수 있습니다.</span>
      </div>
      <div v-if="changes" class="box ask changes" data-test="changes">
        <div class="row"><strong class="grow">AI가 새로 채운 내용 {{ changes.items.length }}곳</strong><button type="button" class="small" data-test="undo" @click="undoChanges">되돌리기</button></div>
        <ul><li v-for="(c, i) in changes.items" :key="i"><b>{{ c.label }}</b><ins>{{ c.after }}</ins></li></ul>
        <p class="notice">멘티가 말한 내용이 아니라 참고 자료로 쓴 초안입니다. 멘티와 이야기한 내용에 맞게 고쳐 주세요.</p>
      </div>

      <div class="item">
        <div class="head"><strong>학습목표</strong><button type="button" class="small" :disabled="!goalText" data-copy="learning_goal" @click="copy('학습목표', goalText)">복사</button></div>
        <label v-for="(s, i) in GOAL_SLOTS" :key="s.mark" class="slot"><span>{{ s.plain }} {{ s.label }}</span>
          <textarea v-model="goal.parts[i]" rows="1" :placeholder="`예: ${s.example}`" :data-goal="i" @keydown.enter.prevent></textarea></label>
        <label v-if="goal.rest" class="slot"><span>그 밖에</span><textarea v-model="goal.rest" rows="2"></textarea></label>
      </div>

      <div class="item">
        <div class="head"><strong>학생진단</strong><button type="button" class="small" :disabled="!diagText" data-copy="diagnosis" @click="copy('학생진단', diagText)">복사</button></div>
        <label v-for="(s, i) in DIAG_SLOTS" :key="s.mark" class="slot"><span>{{ s.mark }}</span>
          <textarea v-model="diag.parts[i]" rows="1" :placeholder="`예: ${s.example}`" :data-diag="i" @keydown.enter.prevent></textarea></label>
        <span class="notice">사전 연락에서 확인한 항목만 적고, 확인하지 못한 항목은 비워 두어도 됩니다.</span>
      </div>

      <div class="item">
        <div class="head"><strong>멘토링 구성</strong><button type="button" class="small" :disabled="!text.structure.trim()" data-copy="structure" @click="copy('멘토링 구성', text.structure)">복사</button></div>
        <textarea v-model="text.structure" rows="5" placeholder="17:00~17:10 온라인 강의 수강(필수) 확인 및 퀴즈&#10;17:10~17:30 개념학습&#10;…" aria-label="멘토링 구성" data-field="structure"></textarea>
      </div>

      <div class="item">
        <div class="head"><strong>활동규칙</strong><button type="button" class="small" :disabled="!text.rules.trim()" data-copy="rules" @click="copy('활동규칙', text.rules)">복사</button></div>
        <textarea v-model="text.rules" rows="5" placeholder="한 줄에 규칙 하나씩" aria-label="활동규칙" data-field="rules"></textarea>
      </div>

      <div class="item">
        <div class="head"><strong>커리큘럼 ({{ rounds }}주)</strong><button type="button" class="small" :disabled="!curriculumLines(rows).length" data-test="copy-curriculum" @click="copy('커리큘럼', curriculumLines(rows).join('\n'))">복사</button></div>
        <p class="notice">1회차 전이라 임시 계획입니다. 주차마다 학습 내용만 대략 적어 주세요. 강좌 목차로 자세히 채우는 것은 종합계획서②에서 합니다.</p>
        <div class="course-card" data-test="general">
          <strong>교육과정 단원으로 채우기</strong>
          <p class="notice">고른 학년·학기의 교육과정 단원을 주차에 나눠 채워 드립니다. 첫 주는 진단, 가운데와 마지막 주는 복습으로 잡습니다. 기초부터 해야 하면 아래 학년이나 지난 학기를 골라 주세요.</p>
          <div class="row">
            <select v-model="general.grade" aria-label="학년" data-general="grade"><option value="">학년</option><option v-for="g in GRADES" :key="g">{{ g }}</option></select>
            <select v-model="general.semester" aria-label="학기" data-general="semester" @change="semesterPicked = true"><option v-for="x in SEMESTERS" :key="x">{{ x }}</option></select>
            <span v-if="fixedSubject" class="tag strong" data-general="subject">{{ fixedSubject }}</span>
            <select v-else v-model="general.subject" aria-label="과목" data-general="subject"><option value="">과목</option><option v-for="x in CURRICULUM_SUBJECTS" :key="x">{{ x }}</option></select>
            <select v-if="found.courses.length" v-model="general.course" class="wide" aria-label="세부 과목" data-general="course">
              <option value="">{{ found.basic || '세부 과목을 골라 주세요' }}</option><option v-for="c in found.courses" :key="c">{{ c }}</option>
            </select>
            <button type="button" :disabled="!found.units.length" data-test="general-fill" @click="fillGeneral">단원으로 채우기</button>
          </div>
          <ul v-if="general.grade && general.subject && found.notes.length" class="notice" data-test="general-notes"><li v-for="n in found.notes" :key="n">{{ n }}</li></ul>
          <p v-if="generalNote" class="ok" data-test="general-done">{{ generalNote }}</p>
        </div>
        <CurriculumEditor v-model="rows" :rounds="rounds" :start="start" :hints="hints" />
      </div>

      <div v-if="notes.length" class="box warn" data-test="notes"><ul><li v-for="n in notes" :key="n">{{ n }}</li></ul></div>
      <div class="row">
        <button type="button" class="primary" :disabled="!!busy || !start" data-test="save" @click="save">{{ busy === 'save' ? '저장하는 중…' : '저장' }}</button>
        <span v-if="!start" class="notice">멘토링 시작일과 시작시간을 정하면 저장할 수 있습니다.</span>
      </div>
    </fieldset>
  </div>
</template>
