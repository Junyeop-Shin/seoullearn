<script setup>
import { computed, reactive, ref } from 'vue'
import { api } from '../../api/client'
import CurriculumEditor from '../../components/CurriculumEditor.vue'
import { shrinkImage } from '../../lib/image'
import { fillValues, scheduleText } from '../../lib/mentee'
import { fillPlanFile, mentorCode, planFileName } from '../../lib/planFile'
import { DIAG_SLOTS, GOAL_SLOTS, changedLines, composeSlots, onlineText, parseSlots, toCircled } from '../../lib/plan'
import { courseName, curriculumCell, curriculumLines, handoverForDraft, handoverFromVault, handoverNote, latestOf,
  termSummaryFromVault, termSummaryText } from '../../lib/reports'
import { totalRounds } from '../../lib/stage'
import { toast } from '../../lib/toast'
import { loadSettings } from '../../stores/settings'
import { saveItem } from '../../stores/vault'

// 종합계획서②: 1회차 후 정해진 서식 파일(종합활동계획서)에 옮겨 적어 1회차 활동보고서에 첨부한다.
// 화면은 서식 파일의 표와 같은 칸, 같은 순서다. 적은 글은 맨 아래에서 서식 파일(hwpx, docx)에 채워 내려받는다.
// 종합계획서①의 내용을 미리 가져오고, 강좌 목차로 커리큘럼을 채우고, 지난 회기를 이어 가면 AI로 초안을 채울 수 있다. 다 쓰면 서식 파일로 내려받는다.
const FORM_ID = 'plan_file'
defineOptions({ inheritAttrs: false })   // 멘티 화면이 모든 단계에 같은 값을 넘긴다: 안 쓰는 값이 화면 요소에 붙지 않게 한다
const props = defineProps({ alias: { type: String, required: true }, profile: { type: Object, required: true }, items: { type: Array, required: true },
  update: { type: Function, required: true } })
const pre = latestOf(props.items, 'plan_initial')
const saved = latestOf(props.items, FORM_ID)
let savedId = saved?.id   // 처음 저장한 뒤에도 같은 항목을 덮어쓴다 (이 화면은 저장해도 다시 그려지지 않는다)
const mentor = loadSettings()
const fill = fillValues(props.profile, mentor)
const rounds = computed(() => totalRounds(props.profile))
const newCourse = (over = {}) => ({ platform: '', lecture: '', instructor: '', lectures: [], done: '', text: '', note: '', images: [], ...over })
const [site, ...lecture] = (props.profile.course || '').split(' ')
const common = reactive({ subject: props.profile.subject === '기타' ? props.profile.subjectEtc : props.profile.subject || '', schedule: scheduleText(props.profile) })
const courses = reactive([newCourse({ platform: site || '', lecture: lecture.join(' ') })])
const alloc = reactive({ mode: 'weekly', perWeek: 2, target: '' })
const text = (v) => (Array.isArray(v) ? v.join('\n') : v || '')
const KEYS = ['learning_goal', 'diagnosis', 'structure', 'rules']
// 종합계획서①의 글을 서식 형식으로 가져온다: 학습목표의 (1)~(4)는 ①~④로. 아무것도 적지 않아 들어간 문구는 가져오지 않는다
const LATER = '1회차에 자세한 상담 예정'   // 종합계획서①이 덜 적힌 진단에 붙이는 문구. 1회차를 마친 종합계획서②에는 넣지 않는다
const noLater = (t) => String(t || '').split('\n').filter((l) => l.trim() !== LATER).join('\n')
const fromPre = (k) => (k === 'learning_goal' ? toCircled(text(pre?.draft?.[k])) : noLater(text(pre?.draft?.[k])))
const base = Object.fromEntries(KEYS.map((k) => [k, fromPre(k)]))
const goal = reactive({ parts: ['', '', '', ''], rest: '' })
const diag = reactive({ parts: ['', '', '', ''], rest: '' })
const plain = reactive({ structure: '', rules: '' })
const rows = ref(pre?.extra?.rows?.length ? pre.extra.rows.map((r) => ({ ...r, mentoring: r.mentoring || r.content || '' })) : [])
// 참고 자료는 종합계획서①과 같이 두 경우를 나눈다: 지난 회기 요약(같은 멘토가 이어 가는 경우)이 있으면 그것만, 없으면 인계받은 글
const previous = termSummaryFromVault(props.items)
const handoverDraft = previous ? null : handoverFromVault(props.items)
const handover = handoverNote(handoverDraft)
const handoverNeeds = handoverForDraft(handoverDraft)   // 인계받은 글 가운데 허용된 네 항목
const busy = ref('')
const error = ref('')
const fillNote = ref('')
const notes = ref([])
const defaults = {}   // 서버가 규칙으로 만든 기본안 (멘토링 구성). 고치지 않았으면 서버가 다시 만든다
const changes = ref(null)   // AI가 바꾼 내용 {mode, items: [{label, before, after}], undo}

const goalText = computed(() => composeSlots(GOAL_SLOTS, goal.parts, goal.rest))
const diagText = computed(() => composeSlots(DIAG_SLOTS, diag.parts, diag.rest))
const memo = () => ({ learning_goal: goalText.value, diagnosis: diagText.value, structure: plain.structure, rules: plain.rules })
function apply(v) {
  Object.assign(goal, parseSlots(GOAL_SLOTS, v.learning_goal))
  Object.assign(diag, parseSlots(DIAG_SLOTS, noLater(v.diagnosis)))
  Object.assign(plain, { structure: v.structure || '', rules: v.rules || '' })
}
apply(base)
// 인계받은 글의 출석·과제·태도를 '학습습관 및 태도'에 기본값으로 넣는다 (종합계획서①과 같은 규칙, AI 미사용). 고쳐 쓸 수 있다
const habit = [handoverNeeds?.attendance_pattern, handoverNeeds?.homework_pattern, handoverNeeds?.attitude].filter(Boolean).join(' ')
if (!saved && habit && !diag.parts[3]) diag.parts[3] = habit

if (saved) {
  const x = saved.extra || {}
  // 예전에는 강좌를 하나만 받았다 (extra.course)
  const list = x.courses?.length ? x.courses : x.course ? [x.course] : []
  if (list.length) courses.splice(0, courses.length, ...list.map((c) => newCourse(c)))
  Object.assign(common, { subject: x.common?.subject ?? x.course?.subject ?? common.subject, schedule: x.common?.schedule ?? x.course?.schedule ?? common.schedule })
  Object.assign(alloc, x.alloc || {})
  // 종합계획서①에서 가져온 뒤 고치지 않은 칸은 지금의 종합계획서① 글을 따른다 (①을 나중에 고쳐도 반영되게)
  apply(Object.fromEntries(KEYS.map((k) => [k, x.base && (x.value?.[k] ?? '') === (x.base[k] ?? '') ? base[k] : x.value?.[k] ?? base[k]])))
  Object.assign(defaults, x.defaults || {})
  if (x.rows?.length) rows.value = x.rows
}

// ---- 서식의 위쪽 칸: 규칙으로 만든다
const dot = (d) => (d ? `${d.replaceAll('-', '.')}.` : '')
const period = computed(() => {
  const dated = rows.value.filter((r) => r.date)
  return dated.length ? `${dot(dated[0].date)}~${dot(dated.at(-1).date)}` : ''
})
const courseList = computed(() => courses.map((c) => [c.platform, courseName(c)].filter(Boolean).join(' ')).filter(Boolean).join(', '))
const subjectTime = computed(() => [common.subject, courseList.value, common.schedule].filter((x) => x && x.trim()).join(' / '))
const lines = (s) => s.split('\n').map((x) => x.trim()).filter(Boolean)
const ready = computed(() => courses.reduce((n, c) => n + Math.max(0, c.lectures.length - (Number(c.done) || 0)), 0))   // 아직 안 들은 강 수


async function run(name, fn) {
  error.value = ''
  notes.value = []
  busy.value = name
  try {
    await fn()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}

// ---- 강좌 목차 불러오기
async function loadOutline(c) {
  const res = await api.courseOutline(c.text)
  c.lectures = res.lectures
  c.note = `${res.lectures.length}강을 읽었습니다.${res.warnings.length ? ' ' + res.warnings.join(' ') : ''}`
}
const parseOutline = (c) => run('outline', () => loadOutline(c))

// 복사가 안 되는 사이트: 강의 목록을 찍은 이미지를 올리면 AI가 보이는 글자를 옮겨 적어 위 칸에 넣는다. 멘토가 확인하고 고친 뒤 [목차 불러오기]를 누른다.
// 이미지는 브라우저에서 줄여 한 장씩 보내고, 서버는 저장하지 않는다. 이미지는 가릴 수 없으므로 강의 목록만 보이게 올리도록 안내한다
// 캡처한 이미지를 Ctrl+V(⌘V)로 바로 붙여 넣는다. 글을 붙여 넣을 때는 끼어들지 않는다
function pasteImages(c, event) {
  const files = [...(event.clipboardData?.files || [])].filter((f) => f.type.startsWith('image/'))
  if (!files.length) return
  event.preventDefault()
  addImages(c, files.map((f, i) => new File([f], f.name && f.name !== 'image.png' ? f.name : `붙여 넣은 이미지 ${c.images.length + i + 1}`, { type: f.type })))
}
async function addImages(c, files) {
  error.value = ''
  try {
    for (const f of files) c.images.push({ name: f.name, url: await shrinkImage(f) })
  } catch (e) {
    error.value = e.message
  }
}
const readImages = (c) => run('image', async () => {
  let got = 0
  const failed = []
  while (c.images.length) {
    const img = c.images[0]
    const res = await api.courseOutlineImage(img.url)
    c.images.shift()
    if (res.error) { failed.push(`${img.name}: ${res.error}`); continue }
    c.text = [c.text.trim(), res.text].filter(Boolean).join('\n')
    got += res.lines
  }
  // 읽은 글로 바로 목차를 불러온다. 글은 위 칸에 남으므로 잘못 읽은 글자가 있으면 고쳐서 [목차 불러오기]를 다시 누르면 된다
  if (got) {
    await loadOutline(c)
    c.note = `이미지에서 ${c.note} 잘못 읽은 글자가 있으면 위 칸에서 고친 뒤 [목차 불러오기]를 다시 눌러 주세요.`
  }
  if (failed.length) error.value = failed.join(' ')
})

// ---- 커리큘럼 채우기: 강좌를 순서대로 이어 붙여(이미 들은 강은 빼고) 주차에 나눈다
const fillCurriculum = () => run('fill-curriculum', async () => {
  if (rows.value.some((r) => (r.online || '').trim()) && !window.confirm('표에 적어 둔 온라인 강의와 멘토링 내용을 불러온 강의로 바꿉니다. 계속할까요?')) return
  // order: 그 강좌의 목차에서 몇 번째 강인지 (제목에 적힌 번호가 아니라 순서)
  const combined = courses.flatMap((c, ci) => c.lectures.map((l, i) => ({ ...l, course: ci, order: i + 1 })).slice(Number(c.done) || 0))
  const how = alloc.mode === 'weekly' ? { per_week: Number(alloc.perWeek) || 1 } : { target: Number(alloc.target) }
  const res = await api.weeklyPlan({ lectures: combined, done: 0, sessions: rounds.value, start_date: (props.profile.start_datetime || '').slice(0, 10) || null, ...how })
  rows.value = rows.value.map((r, i) => {
    const s = res.sessions[i]
    if (!s) return r
    // 온라인 강의 칸에는 강의 제목과 (목차에서 몇 강인지), 멘토링 내용 칸에는 학습 내용. 상담 내용은 넣지 않는다
    return { ...r, ...onlineText(s.lectures, courses, courseName), mentoring: i === 0 ? `오리엔테이션(OT), ${s.mentoring}` : s.mentoring }
  })
  const wanted = alloc.mode === 'target' ? Math.min(Number(alloc.target), combined.length) : combined.length
  const left = wanted - res.covered
  // 진도 회차(첫 주와 마지막 정리 주 사이)에 빈 주가 있으면 강의가 회기 중간에 끝난 것이다
  const endsEarly = left <= 0 && res.sessions.slice(1, -1).some((x) => !x.lectures.length)
  fillNote.value = `${res.covered}강을 ${rounds.value}주에 나눠 채웠습니다. 표에서 고쳐 쓰세요.`
    + (left > 0 ? ` 이 속도로는 ${left}강이 남습니다.` : endsEarly ? ' 강의가 회기 중간에 끝납니다. 이어서 들을 강좌가 있으면 [강좌 추가]로 더한 뒤 다시 채워 주세요.' : '')
    + (res.warnings?.length ? ` ${res.warnings.join(' ')}` : '')   // AI를 쓰지 못해 기본 문장으로 채운 경우 등
})

// ---- AI: 바뀐 내용을 보여 주고 되돌릴 수 있게 한다
const snapshot = () => [...GOAL_SLOTS.map((s, i) => [`멘티 학습목표 ${s.mark}`, goal.parts[i] || '']), ...DIAG_SLOTS.map((s, i) => [`학생진단 ${s.mark}`, diag.parts[i] || '']),
  ['멘토링 구성', plain.structure], ['활동규칙', plain.rules]]
function track(mode, before, snap) {
  const items = snapshot().flatMap(([label, after], i) => changedLines(snap[i][1], after).map(([b, a]) => ({ label, before: b, after: a })))
  changes.value = items.length ? { mode, items, undo: before } : null
}
function undoChanges() {
  apply(changes.value.undo)
  changes.value = null
  toast('AI가 바꾸기 전으로 되돌렸습니다.')
}
const timing = () => ({ start_datetime: (props.profile.start_datetime || '').replace('T', ' '), duration: Number(props.profile.duration) || 60, rounds: rounds.value })
const safe = (res) => {
  // 아동 안전 신호가 있으면 서버가 초안을 만들지 않고 운영사무국 안내만 돌려준다: 그 안내를 보여 주고 저장하지 않는다
  if (!Object.keys(res.draft).length) throw new Error(res.warnings[0] || '초안을 만들지 못했습니다.')
  if (res.error) throw new Error('AI의 답을 읽지 못했습니다. 잠시 뒤 다시 눌러 주세요.')
  return res
}

// 초안 채우기(지난 회기를 이어 가는 경우만): 비워 둔 학습목표·학생진단을 지난 회기 요약으로. 종합계획서①과 같은 규칙(같은 양식)으로 쓴다
const fillDraft = () => run('fill', async () => {
  const before = memo(), snap = snapshot()
  const only = ['learning_goal', 'diagnosis'].filter((k) => !before[k].trim())
  if (!only.length) return toast('학습목표와 학생진단에 이미 적은 내용이 있어 채우지 않았습니다.')
  const extra = { mode: props.profile.mode || '온라인', memo: {}, curriculum_lines: [], only, previous_term: previous }
  const res = safe(await api.draft('plan_initial', { duration: String(props.profile.duration || '60'), weekday: props.profile.weekday || '', start_datetime: timing().start_datetime }, extra))
  const next = { ...before }
  for (const k of only) next[k] = k === 'learning_goal' ? toCircled(text(res.draft[k])) : noLater(text(res.draft[k]))
  apply(next)
  track('fill', before, snap)
  toast(changes.value ? '초안을 채웠습니다. 새로 들어간 내용을 확인하고 고쳐 주세요.' : '참고 자료에서 채울 내용을 찾지 못했습니다.')
})

// ---- 서식 파일로 내보내기: 서식 파일(docx, hwpx)에 이 화면의 글을 채워 내려받는다. 채우는 일은 이 브라우저 안에서만 하고 내용은 서버로 보내지 않는다
// 빈 서식은 서버에 올려 둔 것을 받아 쓴다 (로그인한 멘토에게만 내준다)
const exportAs = (format) => run('export', async () => {
  const bytes = await api.planTemplate(format)
  if (!bytes) throw new Error('서버에 서식 파일이 없어 내보내지 못했습니다. 서버의 서식 폴더를 확인해 주세요.')
  const v = memo()
  const out = fillPlanFile(bytes, { period: period.value, mentee: fill.mentee || '', mentor: fill.mentor || '', subject_time: subjectTime.value,
    course: courseList.value, goal: lines(v.learning_goal), diagnosis: lines(v.diagnosis), structure: lines(v.structure), rules: lines(v.rules),
    weeks: rows.value.map((r) => ((r.online || '').trim() || (r.mentoring || '').trim() ? curriculumCell(r, courses).split('\n') : [])) })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([out]))
  a.download = planFileName(format, { code: mentorCode(mentor.name, mentor.phone), term: props.profile.term, mentee: props.profile.name })
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)   // 바로 지우면 내려받기가 취소되는 브라우저가 있다
  toast(`${a.download} 파일을 내려받았습니다. 열어서 내용과 모양을 확인해 주세요.`)
})

// 저장은 AI를 쓰지 않는다. 서버가 정리한 글(개인정보·민감 내용 제거, 비워 둔 멘토링 구성의 기본 배분)을 같은 칸에 다시 넣는다
const save = () => run('save', async () => {
  const v = memo()
  const m = { learning_goal: v.learning_goal }
  // 멘토링 구성은 고쳤을 때만 적은 글을 쓴다. 종합계획서①에서 가져온 그대로면 서식 표기(& 등)의 시간 배분 기본안을 서버가 다시 만든다
  if (v.structure.trim() && v.structure.trim() !== base.structure.trim()) m.structure = v.structure
  const res = safe(await api.draft(FORM_ID, { subject_time: subjectTime.value, diagnosis: lines(v.diagnosis), rules: lines(v.rules) },
    { ...timing(), memo: m, curriculum_lines: curriculumLines(rows.value, true, courses), only: [] }))
  if (!m.structure) defaults.structure = text(res.draft.structure)
  apply(Object.fromEntries(KEYS.map((k) => [k, text(res.draft[k])])))
  notes.value = [...(res.pii_masked.length ? [`가린 정보: ${res.pii_masked.join(', ')}`] : []), ...res.missing_questions.map((q) => q.question), ...res.warnings, ...res.reminders]
  // 목차 원문(text)은 저장하지 않는다. 강 목록만 남긴다
  const keep = courses.map(({ text: _text, note: _note, images: _images, ...c }) => c)
  savedId = (await saveItem({ id: savedId, alias: props.alias, formId: FORM_ID, title: '종합계획서②', draft: res.draft, inputs: { subject_time: subjectTime.value },
    extra: { courses: keep, common: { ...common }, alloc: { ...alloc }, value: memo(), base: { ...base }, defaults: { ...defaults }, rows: rows.value } })).id
  await props.update({ course: [courses[0].platform, courses[0].lecture].filter(Boolean).join(' ') || props.profile.course, goal: goalText.value },
    props.profile.stage === 'PLAN' ? '종합계획서②를 저장했습니다. 아래 [다음 단계]를 누르면 1회차 활동보고서로 넘어갑니다.' : '종합계획서②를 저장했습니다.')
})
</script>

<template>
  <div>
    <p class="muted">1회차를 마친 뒤, 협의한 내용으로 종합계획서②를 씁니다. 다 쓰면 맨 아래에서 서식 파일로 내려받아 1회차 활동보고서에 첨부해 주세요.</p>
    <div v-if="error" class="box error">{{ error }}</div>
    <div v-if="previous" class="mini pre" data-test="previous-term"><span class="t">지난 회기 요약 (참고)</span>{{ termSummaryText(previous) }}</div>
    <div v-else-if="handover" class="mini pre" data-test="handover-ref"><span class="t">이전 멘토에게 인계받은 내용 (참고)</span>{{ handover }}</div>

    <form class="card plan-form" @submit.prevent="save">
      <!-- 서버 응답을 기다리는 동안에는 입력을 잠근다: 그 사이에 적은 글이 응답으로 덮이지 않게 -->
      <fieldset :disabled="!!busy">
      <h3 class="sheet-title">「서울런 멘토단」 멘토링 종합 계획서</h3>
      <table class="sheet" data-test="sheet">
        <tr>
          <th>멘토링기간</th>
          <td colspan="3"><span data-sheet="period">{{ period || '커리큘럼 표의 날짜가 정해지면 채워집니다' }}</span></td>
        </tr>
        <tr>
          <th>멘 티</th>
          <td><span data-sheet="mentee">{{ fill.mentee || '멘티 설정에서 이름·학년 입력' }}</span></td>
          <th>멘 토</th>
          <td><span data-sheet="mentor">{{ fill.mentor || '멘토 설정에서 이름·대학교·전공 입력' }}</span></td>
        </tr>
        <tr>
          <th>멘토링<br />과목 및 시간</th>
          <td colspan="3">
            <p class="mini flush" data-sheet="subject_time">{{ subjectTime || '멘토링과목 / 수강강좌정보 / 진행일정(요일, 시간)' }}</p>
            <div class="form-grid">
              <label class="field"><span class="name">멘토링과목</span><input v-model="common.subject" data-course="subject" /></label>
              <label class="field"><span class="name">진행일정 (요일, 시간)</span><input v-model="common.schedule" placeholder="예: 매주(화) 17:00~18:00" data-course="schedule" /></label>
            </div>
            <div v-for="(c, ci) in courses" :key="ci" class="course-card" :data-test="`course-${ci}`">
              <div class="row"><strong class="grow">수강강좌{{ courses.length > 1 ? ` ${ci + 1}` : '' }}</strong>
                <button v-if="courses.length > 1" type="button" class="small" @click="courses.splice(ci, 1)">이 강좌 빼기</button></div>
              <div class="form-grid">
                <label class="field"><span class="name">학습사이트</span><input v-model="c.platform" placeholder="예: 메가스터디" :data-course="`platform-${ci}`" /></label>
                <label class="field"><span class="name">강좌명</span><input v-model="c.lecture" placeholder="예: 수학의 시작, 시발점 - 수1" :data-course="`lecture-${ci}`" /></label>
                <label class="field"><span class="name">강사명</span><input v-model="c.instructor" :data-course="`instructor-${ci}`" /></label>
              </div>
            </div>
            <button type="button" class="small" data-test="add-course" @click="courses.push(newCourse())">강좌 추가</button>
            <span class="notice inline">이번 회기 안에 강좌를 다 듣게 되면, 이어서 들을 강좌를 추가해 주세요.</span>
          </td>
        </tr>
        <tr>
          <th>멘티<br />학습목표</th>
          <td colspan="3">
            <div v-if="previous" class="course-card" data-test="fill-box" data-source="previous">
              <strong>AI로 초안 채우기</strong>
              <p class="notice">비워 둔 학습목표와 학생진단을 지난 회기 요약으로 채워 드립니다. 이미 적은 칸은 건드리지 않습니다.</p>
              <button type="button" :disabled="!!busy" data-test="fill" @click="fillDraft">{{ busy === 'fill' ? '채우는 중…' : '지난 회기에 이어 초안 채우기' }}</button>
            </div>
            <div v-if="changes" class="box ask changes" data-test="changes">
              <div class="row"><strong class="grow">AI가 새로 채운 내용 {{ changes.items.length }}곳</strong><button type="button" class="small" data-test="undo" @click="undoChanges">되돌리기</button></div>
              <ul><li v-for="(c, i) in changes.items" :key="i"><b>{{ c.label }}</b><ins>{{ c.after }}</ins></li></ul>
              <p class="notice">멘티가 말한 내용이 아니라 참고 자료로 쓴 초안입니다. 1회차에 이야기한 내용에 맞게 고쳐 주세요.</p>
            </div>
            <span class="notice">{{ pre ? '종합계획서①에서 가져왔습니다. 1회차에 협의한 내용으로 고쳐 주세요.' : '1회차에 협의한 목표를 항목별로 적어 주세요.' }}</span>
            <label v-for="(s, i) in GOAL_SLOTS" :key="s.mark" class="slot"><span>{{ s.mark }} {{ s.label }}</span>
              <input v-model="goal.parts[i]" :placeholder="`예: ${s.example}`" :data-goal="i" /></label>
            <label v-if="goal.rest" class="slot"><span>그 밖에</span><textarea v-model="goal.rest" rows="2"></textarea></label>
          </td>
        </tr>
        <tr>
          <th>학생진단</th>
          <td colspan="3">
            <span class="notice">1회차에 확인한 내용을 항목별로 적어 주세요. 확인하지 못한 항목은 비워 둡니다.</span>
            <label v-for="(s, i) in DIAG_SLOTS" :key="s.mark" class="slot"><span>{{ s.mark }}</span>
              <input v-model="diag.parts[i]" :placeholder="`예: ${s.example}`" :data-diag="i" /></label>
            <label v-if="diag.rest" class="slot"><span>그 밖에</span><textarea v-model="diag.rest" rows="2"></textarea></label>
          </td>
        </tr>
        <tr>
          <th>커리큘럼<br /><small data-sheet="course">{{ courseList }}</small></th>
          <td colspan="3">
            <div v-for="(c, ci) in courses" :key="ci" class="course-card">
              <details :open="!c.lectures.length" :data-test="`outline-${ci}`" @paste="pasteImages(c, $event)">
                <summary>{{ courseName(c) || `강좌 ${ci + 1}` }}의 목차 불러와서 커리큘럼 채우기{{ c.lectures.length ? ` · ${c.lectures.length}강 불러옴` : '' }}</summary>
                <p class="notice">학습사이트 강좌 페이지의 강의 목록을 통째로 복사해 붙여 넣으면 강의를 가려 읽습니다. 강의 제목이 제각각이어도 순서대로 몇 강인지 붙여 드립니다. 이 도구가 학습사이트에 접속하지는 않습니다.</p>
                <textarea v-model="c.text" rows="4" placeholder="강의 목록을 여기에 붙여 넣어 주세요" :data-outline="ci"></textarea>
                <button type="button" class="gap-top" :disabled="!c.text.trim() || !!busy" :data-parse="ci" @click="parseOutline(c)">{{ busy === 'outline' ? '읽는 중…' : '목차 불러오기' }}</button>
                <div class="image-read" :data-test="`image-${ci}`">
                  <strong>복사가 안 되는 사이트라면: 이미지에서 읽기</strong>
                  <p class="notice">강의 목록 화면을 캡처해 아래 자리에 붙여 넣으면 AI가 글자를 읽어 목차로 불러옵니다. 목록이 길면 여러 장을 순서대로 넣어 주세요. 이미지는 AI로 보내므로 이름이나 아이디가 보이지 않게 강의 목록만 찍어 주세요. 이미지는 저장하지 않습니다.</p>
                  <div class="paste-zone" tabindex="0" aria-label="여기를 누르고 이미지를 붙여 넣기" :data-paste="ci">여기를 누르고 붙여 넣기 (Ctrl+V, ⌘V)</div>
                  <div v-if="c.images.length" class="thumbs">
                    <figure v-for="(img, k) in c.images" :key="k"><img :src="img.url" :alt="`올린 이미지 ${k + 1}`" /><button type="button" class="small" @click="c.images.splice(k, 1)">빼기</button></figure>
                  </div>
                  <button v-if="c.images.length" type="button" :disabled="!!busy" :data-image-read="ci" @click="readImages(c)">{{ busy === 'image' ? '이미지를 읽는 중…' : `이미지 ${c.images.length}장에서 읽기` }}</button>
                </div>
              </details>
              <label class="row gap-top">이미 들은 강의 수 (선택) <input v-model="c.done" type="number" min="0" placeholder="0" class="num" :data-course="`done-${ci}`" /></label>
              <p v-if="c.note" class="notice" :data-note="ci">{{ c.note }}</p>
            </div>
            <div v-if="ready" class="course-card" data-test="alloc">
              <strong>불러온 강의를 주차에 나누기</strong> <span class="muted">아직 안 들은 강의 {{ ready }}강</span>
              <div class="choices gap-top">
                <label><input v-model="alloc.mode" type="radio" value="weekly" name="alloc" />일주일에 <input v-model="alloc.perWeek" type="number" min="1" max="10" class="num" data-alloc="perWeek" /> 강씩</label>
                <label><input v-model="alloc.mode" type="radio" value="target" name="alloc" data-alloc="mode-target" />이번 회기에 <input v-model="alloc.target" type="number" min="1" :max="ready" class="num" placeholder="필수" data-alloc="target" /> 강 듣기 (회차에 고르게 나눔)</label>
              </div>
              <p class="notice">강의는 규칙으로 나누고, 멘토링 내용 문장은 AI가 씁니다. 채운 뒤 표에서 고쳐 주세요.</p>
              <button type="button" class="primary" :disabled="!!busy || (alloc.mode === 'target' && !Number(alloc.target))" data-test="fill-curriculum" @click="fillCurriculum">{{ busy === 'fill-curriculum' ? '채우는 중…' : '커리큘럼 채우기' }}</button>
              <p v-if="fillNote" class="notice" data-test="fill-note">{{ fillNote }}</p>
            </div>
            <span class="notice">서식에는 주차마다 "(온라인강의) 강좌명(강사명), 강의 제목 (n~m강)" 줄바꿈 "(멘토링 내용) 학습 내용"으로 들어갑니다. 괄호 안은 목차에서 몇 번째 강인지입니다.</span>
            <CurriculumEditor v-model="rows" :rounds="rounds" :start="profile.start_datetime || ''" :courses="courses" full />
          </td>
        </tr>
        <tr>
          <th>멘토링<br />구성</th>
          <td colspan="3">
            <textarea v-model="plain.structure" :rows="Math.max(5, plain.structure.split('\n').length)" placeholder="17:00~17:10 온라인 강의 수강(필수) 확인 & 퀴즈&#10;17:10~17:30 개념학습&#10;… (비워 두고 저장하면 시간 배분 기본안이 들어갑니다)" aria-label="멘토링 구성" data-field="structure"></textarea>
          </td>
        </tr>
        <tr>
          <th>활동규칙</th>
          <td colspan="3">
            <textarea v-model="plain.rules" :rows="Math.max(5, plain.rules.split('\n').length)" placeholder="한 줄에 규칙 하나씩&#10;멘토링 시간 준수하기&#10;일정 변경은 최소 3일 전에 논의하기" aria-label="활동규칙" data-field="rules"></textarea>
          </td>
        </tr>
      </table>

      <div v-if="notes.length" class="box warn" data-test="notes"><ul><li v-for="n in notes" :key="n">{{ n }}</li></ul></div>
      <div class="row">
        <button class="primary" :disabled="!!busy" data-test="save">{{ busy === 'save' ? '저장하는 중…' : '저장' }}</button>
      </div>
      <div class="course-card" data-test="export">
        <strong>서식 파일로 내보내기</strong>
        <p class="notice">이 화면의 내용을 종합활동계획서 서식에 채운 파일을 내려받습니다. 내용은 이 브라우저 안에서 채우고 서버로 보내지 않습니다. 파일 이름의 멘토코드는 멘토 설정의 이름과 연락처 뒤 네 자리로 만듭니다.</p>
        <div class="row">
          <button type="button" class="primary" :disabled="!!busy" data-export="hwpx" @click="exportAs('hwpx')">한글(hwpx)로 내려받기</button>
          <button type="button" :disabled="!!busy" data-export="docx" @click="exportAs('docx')">워드(docx)로 내려받기</button>
        </div>
      </div>
      </fieldset>
    </form>
  </div>
</template>
