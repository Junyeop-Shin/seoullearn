<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../../api/client'
import CurriculumEditor from '../../components/CurriculumEditor.vue'
import { copyText } from '../../lib/copy'
import { fillValues, menteePath, scheduleText } from '../../lib/mentee'
import { DIAG_SLOTS, GOAL_SLOTS, changedLines, composeSlots, freshLines, mergeLines, onlineText, parseSlots, toCircled } from '../../lib/plan'
import { COURSE_ALIAS, COURSE_FORM, courseName, coursesFromVault, curriculumCell, curriculumLines, handoverForDraft, handoverFromVault, handoverNote,
  termSummaryFromVault, termSummaryText } from '../../lib/reports'
import { totalRounds } from '../../lib/stage'
import { toast } from '../../lib/toast'
import { loadSettings } from '../../stores/settings'
import { listItems, saveItem } from '../../stores/vault'

// 종합계획서②: 1회차 후 정해진 서식 파일(종합활동계획서)에 옮겨 적어 1회차 활동보고서에 첨부한다.
// 화면은 서식 파일의 표와 같은 칸, 같은 순서다. 칸마다 적은 글을 [복사]해 서식의 같은 칸에 붙여 넣는다.
// 종합계획서①의 내용을 미리 가져오고, 강좌 목차로 커리큘럼을 채우고, 필요하면 AI로 초안을 채우거나 표현을 다듬는다.
const FORM_ID = 'plan_file'
defineOptions({ inheritAttrs: false })   // 멘티 화면이 모든 단계에 같은 값을 넘긴다: 안 쓰는 값이 화면 요소에 붙지 않게 한다
const props = defineProps({ alias: { type: String, required: true }, profile: { type: Object, required: true }, items: { type: Array, required: true },
  update: { type: Function, required: true } })
const latest = (formId) => props.items.filter((x) => x.formId === formId).sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]
const pre = latest('plan_initial')
const saved = latest(FORM_ID)
const fill = fillValues(props.profile, loadSettings())
const rounds = computed(() => totalRounds(props.profile))
const newCourse = (over = {}) => ({ platform: '', lecture: '', instructor: '', lectures: [], done: '', text: '', note: '', ...over })
const [site, ...lecture] = (props.profile.course || '').split(' ')
const common = reactive({ subject: props.profile.subject === '기타' ? props.profile.subjectEtc : props.profile.subject || '', schedule: scheduleText(props.profile) })
const courses = reactive([newCourse({ platform: site || '', lecture: lecture.join(' ') })])
const alloc = reactive({ mode: 'weekly', perWeek: 2, target: '' })
const savedCourses = ref([])   // 보관함에 저장해 둔 내 강좌 (목차)
const text = (v) => (Array.isArray(v) ? v.join('\n') : v || '')
const KEYS = ['learning_goal', 'diagnosis', 'structure', 'rules']
// 종합계획서①의 글을 서식 형식으로 가져온다: 학습목표의 (1)~(4)는 ①~④로. 아무것도 적지 않아 들어간 문구는 가져오지 않는다
const fromPre = (k) => (k === 'learning_goal' ? toCircled(text(pre?.draft?.[k])) : text(pre?.draft?.[k]).replace(/^1회차에 자세한 상담 예정$/, ''))
const base = Object.fromEntries(KEYS.map((k) => [k, fromPre(k)]))
const goal = reactive({ parts: ['', '', '', ''], rest: '' })
const diag = reactive({ parts: ['', '', '', ''], rest: '' })
const plain = reactive({ structure: '', rules: '' })
const rows = ref(pre?.extra?.rows?.length ? pre.extra.rows.map((r) => ({ ...r, mentoring: r.mentoring || r.content || '' })) : [])
// 참고 자료는 종합계획서①과 같이 두 경우를 나눈다: 지난 회기 요약(같은 멘토가 이어 가는 경우)이 있으면 그것만, 없으면 인계받은 글
const previous = termSummaryFromVault(props.items)
const handoverDraft = previous ? null : handoverFromVault(props.items)
const handover = handoverNote(handoverDraft)
const source = previous ? 'previous' : handoverForDraft(handoverDraft) ? 'handover' : ''
const SOURCE = { previous: '지난 회기에 이어 초안 채우기', handover: '인계받은 내용으로 초안 채우기' }
const busy = ref('')
const error = ref('')
const fillNote = ref('')
const notes = ref([])
const done = ref(!!saved)
const defaults = {}   // 서버가 규칙으로 만든 기본안 (멘토링 구성). 고치지 않은 줄은 AI로 다듬지 않는다
const polished = {}   // 마지막으로 AI가 다듬어 준 글. 그 뒤로 고치지 않은 줄은 다시 다듬지 않는다
const changes = ref(null)   // AI가 바꾼 내용 {mode, items: [{label, before, after}], undo}

const goalText = computed(() => composeSlots(GOAL_SLOTS, goal.parts, goal.rest))
const diagText = computed(() => composeSlots(DIAG_SLOTS, diag.parts, diag.rest))
const memo = () => ({ learning_goal: goalText.value, diagnosis: diagText.value, structure: plain.structure, rules: plain.rules })
function apply(v) {
  Object.assign(goal, parseSlots(GOAL_SLOTS, v.learning_goal))
  Object.assign(diag, parseSlots(DIAG_SLOTS, v.diagnosis))
  Object.assign(plain, { structure: v.structure || '', rules: v.rules || '' })
}
apply(base)

async function loadSaved() {
  try {
    savedCourses.value = coursesFromVault(await listItems(COURSE_ALIAS))
  } catch {
    savedCourses.value = []
  }
}

onMounted(async () => {
  await loadSaved()
  if (!saved) return
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
})

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
const curriculumText = computed(() => curriculumLines(rows.value, true, courses).join('\n\n'))

async function copy(label, value) {
  toast((await copyText(value)) ? `${label}을(를) 복사했습니다.` : '복사하지 못했습니다.')
}

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
function useSaved(c, id) {
  const s = savedCourses.value.find((x) => x.id === id)
  if (!s) return
  c.lectures = s.lectures
  c.note = `저장해 둔 '${s.title}' ${s.lectures.length}강을 불러왔습니다.`
}

const parseOutline = (c) => run('outline', async () => {
  const res = await api.courseOutline(c.text)
  c.lectures = res.lectures
  c.note = `${res.lectures.length}강을 읽었습니다.${res.warnings.length ? ' ' + res.warnings.join(' ') : ''}`
  // 다음 회기나 다른 멘티 때 다시 붙여 넣지 않도록 내 강좌에 저장해 둔다
  const title = [c.platform, courseName(c)].filter(Boolean).join(' ').trim()
  if (title && res.lectures.length) {
    await saveItem({ id: savedCourses.value.find((x) => x.title === title)?.id, alias: COURSE_ALIAS, formId: COURSE_FORM, title, draft: { lectures: res.lectures } })
    await loadSaved()
  }
})

// ---- 커리큘럼 채우기: 강좌를 순서대로 이어 붙여(이미 들은 강은 빼고) 주차에 나눈다
const fillCurriculum = () => run('fill-curriculum', async () => {
  if (rows.value.some((r) => (r.online || '').trim()) && !window.confirm('표에 적어 둔 온라인 강의와 멘토링 내용을 불러온 강의로 바꿉니다. 계속할까요?')) return
  const combined = courses.flatMap((c, ci) => c.lectures.slice(Number(c.done) || 0).map((l) => ({ ...l, course: ci })))
  const how = alloc.mode === 'weekly' ? { per_week: Number(alloc.perWeek) || 1 } : { target: Number(alloc.target) }
  const res = await api.weeklyPlan({ lectures: combined, done: 0, sessions: rounds.value, start_date: (props.profile.start_datetime || '').slice(0, 10) || null, ...how })
  rows.value = rows.value.map((r, i) => {
    const s = res.sessions[i]
    if (!s) return r
    // 온라인 강의 칸에는 몇 강인지, 멘토링 내용 칸에는 학습 내용. 상담 내용은 넣지 않는다
    return { ...r, ...onlineText(s.lectures, courses, courseName), mentoring: i === 0 ? `오리엔테이션(OT), ${s.mentoring}` : s.mentoring }
  })
  const wanted = alloc.mode === 'target' ? Math.min(Number(alloc.target), combined.length) : combined.length
  const left = wanted - res.covered
  // 진도 회차(첫 주와 마지막 정리 주 사이)에 빈 주가 있으면 강의가 회기 중간에 끝난 것이다
  const endsEarly = left <= 0 && res.sessions.slice(1, -1).some((x) => !x.lectures.length)
  fillNote.value = `${res.covered}강을 ${rounds.value}주에 나눠 채웠습니다. 표에서 고쳐 쓰세요.`
    + (left > 0 ? ` 이 속도로는 ${left}강이 남습니다.` : endsEarly ? ' 강의가 회기 중간에 끝납니다. 이어서 들을 강좌가 있으면 [강좌 추가]로 더한 뒤 다시 채워 주세요.' : '')
})

// ---- AI: 바뀐 내용을 보여 주고 되돌릴 수 있게 한다
const LABELS = { learning_goal: '멘티 학습목표', diagnosis: '학생진단', structure: '멘토링 구성', rules: '활동규칙' }
const snapshot = () => [...GOAL_SLOTS.map((s, i) => [`멘티 학습목표 ${s.mark}`, goal.parts[i] || '']), ...DIAG_SLOTS.map((s, i) => [`학생진단 ${s.mark}`, diag.parts[i] || '']),
  ['멘토링 구성', plain.structure], ['활동규칙', plain.rules]]
function track(mode, before, snap) {
  const items = snapshot().flatMap(([label, after], i) => changedLines(snap[i][1], after).map(([b, a]) => ({ label, before: b, after: a })))
  changes.value = items.length ? { mode, items, undo: before } : null
}
function undoChanges() {
  apply(changes.value.undo)
  for (const k of Object.keys(polished)) delete polished[k]
  changes.value = null
  toast('AI가 바꾸기 전으로 되돌렸습니다.')
}
const timing = () => ({ start_datetime: (props.profile.start_datetime || '').replace('T', ' '), duration: Number(props.profile.duration) || 60, rounds: rounds.value })
const safe = (res) => {
  // 아동 안전 신호가 있으면 서버가 초안을 만들지 않고 운영사무국 안내만 돌려준다: 그 안내를 보여 주고 저장하지 않는다
  if (!Object.keys(res.draft).length) throw new Error(res.warnings[0] || '초안을 만들지 못했습니다.')
  return res
}

// 초안 채우기: 비워 둔 학습목표·학생진단만, 참고 자료 한 가지로. 종합계획서①과 같은 규칙(같은 양식)으로 쓴다
const fillDraft = () => run('fill', async () => {
  const before = memo(), snap = snapshot()
  const only = ['learning_goal', 'diagnosis'].filter((k) => !before[k].trim())
  if (!only.length) return toast('학습목표와 학생진단에 이미 적은 내용이 있어 채우지 않았습니다.')
  const extra = { mode: props.profile.mode || '온라인', memo: {}, curriculum_lines: [], only }
  if (source === 'handover') extra.handover = handoverForDraft(handoverDraft)   // 인계받은 글 가운데 허용된 네 항목만
  else extra.previous_term = previous
  const res = safe(await api.draft('plan_initial', { duration: String(props.profile.duration || '60'), weekday: props.profile.weekday || '', start_datetime: timing().start_datetime }, extra))
  const next = { ...before }
  for (const k of only) next[k] = k === 'learning_goal' ? toCircled(text(res.draft[k])) : text(res.draft[k]).replace(/^1회차에 자세한 상담 예정$/, '')
  apply(next)
  track('fill', before, snap)
  toast(changes.value ? '초안을 채웠습니다. 새로 들어간 내용을 확인하고 고쳐 주세요.' : '참고 자료에서 채울 내용을 찾지 못했습니다.')
})

// 표현 다듬기: 종합계획서①에서 가져온 그대로인 줄과 이미 다듬은 줄은 보내지 않는다. 참고 자료도 보내지 않는다
const polish = () => run('polish', async () => {
  const before = memo(), snap = snapshot(), fresh = {}
  for (const k of KEYS) {
    const l = freshLines(before[k], polished[k], base[k], defaults[k])
    if (l.length) fresh[k] = l
  }
  const only = Object.keys(fresh)
  if (!only.length) return toast('새로 다듬을 내용이 없습니다. 종합계획서①에서 가져온 그대로이거나 이미 다듬었습니다.')
  const m = {}
  for (const k of ['learning_goal', 'structure']) if (fresh[k]) m[k] = fresh[k].join('\n')
  const res = safe(await api.draft(FORM_ID, { subject_time: subjectTime.value, diagnosis: fresh.diagnosis || [], rules: fresh.rules || [] }, { ...timing(), memo: m, curriculum_lines: [], only }))
  const kept = []
  const out = { ...before }
  for (const k of only) {
    const merged = mergeLines(before[k], fresh[k], text(res.draft[k]))
    if (merged === null) kept.push(`${LABELS[k]}은(는) 다듬은 글의 줄 수가 달라 적어 둔 그대로 두었습니다. 내용이 빠졌을 수 있으니 확인해 주세요.`)
    else out[k] = merged
  }
  apply(out)
  const after = memo()
  for (const k of only) polished[k] = after[k]
  track('polish', before, snap)
  notes.value = [...kept, ...(res.pii_masked.length ? [`AI에 보내기 전에 가린 정보: ${res.pii_masked.join(', ')}`] : []), ...res.warnings.filter((w) => !w.includes('주차별 계획이 없어'))]
  toast(changes.value ? '표현을 다듬었습니다. 바뀐 내용을 확인하고 저장해 주세요.' : '다듬어 보았지만 바꿀 표현이 없었습니다.')
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
  const keep = courses.map(({ text: _text, note: _note, ...c }) => c)
  await saveItem({ id: saved?.id, alias: props.alias, formId: FORM_ID, title: '종합계획서②', draft: res.draft, inputs: { subject_time: subjectTime.value },
    extra: { courses: keep, common: { ...common }, alloc: { ...alloc }, value: memo(), base: { ...base }, defaults: { ...defaults }, rows: rows.value } })
  done.value = true
  await props.update({ course: [courses[0].platform, courses[0].lecture].filter(Boolean).join(' ') || props.profile.course, goal: goalText.value }, '종합계획서②를 저장했습니다.')
})
</script>

<template>
  <div>
    <p class="muted">1회차를 마친 뒤, 협의한 내용으로 종합계획서②를 씁니다. 아래 표는 서식 파일(종합활동계획서)과 같은 칸, 같은 순서입니다. 칸마다 [복사]해 서식 파일의 같은 칸에 붙여 넣고, 1회차 활동보고서에 첨부해 주세요.</p>
    <div v-if="error" class="box error">{{ error }}</div>
    <div v-if="previous" class="mini" style="white-space: pre-wrap; margin: 12px 0" data-test="previous-term"><span class="t">지난 회기 요약 (참고)</span>{{ termSummaryText(previous) }}</div>
    <div v-else-if="handover" class="mini" style="white-space: pre-wrap; margin: 12px 0" data-test="handover-ref"><span class="t">이전 멘토에게 인계받은 내용 (참고)</span>{{ handover }}</div>

    <form class="card plan-form" @submit.prevent="save">
      <h3 style="text-align: center; margin-top: 0">「서울런 멘토단」 멘토링 종합 계획서</h3>
      <table class="sheet" data-test="sheet">
        <tr>
          <th>멘토링기간</th>
          <td colspan="3"><div class="cell-row"><span data-sheet="period">{{ period || '커리큘럼 표의 날짜가 정해지면 채워집니다' }}</span>
            <button type="button" class="small" :disabled="!period" data-copy="period" @click="copy('멘토링기간', period)">복사</button></div></td>
        </tr>
        <tr>
          <th>멘 티</th>
          <td><div class="cell-row"><span data-sheet="mentee">{{ fill.mentee || '멘티 설정에서 이름·학년 입력' }}</span>
            <button type="button" class="small" :disabled="!fill.mentee" data-copy="mentee" @click="copy('멘티', fill.mentee)">복사</button></div></td>
          <th>멘 토</th>
          <td><div class="cell-row"><span data-sheet="mentor">{{ fill.mentor || '멘토 설정에서 이름·대학교·전공 입력' }}</span>
            <button type="button" class="small" :disabled="!fill.mentor" data-copy="mentor" @click="copy('멘토', fill.mentor)">복사</button></div></td>
        </tr>
        <tr>
          <th>멘토링<br />과목 및 시간</th>
          <td colspan="3">
            <div class="cell-row"><span class="mini" style="flex: 1; margin: 0" data-sheet="subject_time">{{ subjectTime || '멘토링과목 / 수강강좌정보 / 진행일정(요일, 시간)' }}</span>
              <button type="button" class="small" :disabled="!subjectTime" data-copy="subject_time" @click="copy('멘토링 과목 및 시간', subjectTime)">복사</button></div>
            <div class="form-grid">
              <label class="field"><span class="name">멘토링과목</span><input v-model="common.subject" data-course="subject" /></label>
              <label class="field"><span class="name">진행일정 (요일, 시간)</span><input v-model="common.schedule" placeholder="예: 매주(화) 17:00~18:00" data-course="schedule" /></label>
            </div>
            <div v-for="(c, ci) in courses" :key="ci" class="course-card" :data-test="`course-${ci}`">
              <div class="row"><strong>수강강좌{{ courses.length > 1 ? ` ${ci + 1}` : '' }}</strong><span style="flex: 1"></span>
                <button v-if="courses.length > 1" type="button" class="small" @click="courses.splice(ci, 1)">이 강좌 빼기</button></div>
              <div class="form-grid">
                <label class="field"><span class="name">학습 플랫폼</span><input v-model="c.platform" placeholder="예: 메가스터디" :data-course="`platform-${ci}`" /></label>
                <label class="field"><span class="name">강좌명</span><input v-model="c.lecture" placeholder="예: 수학의 시작, 시발점 - 수1" :data-course="`lecture-${ci}`" /></label>
                <label class="field"><span class="name">강사명</span><input v-model="c.instructor" :data-course="`instructor-${ci}`" /></label>
              </div>
            </div>
            <button type="button" class="small" data-test="add-course" @click="courses.push(newCourse())">강좌 추가</button>
            <span class="notice" style="display: inline; margin-left: 8px">이번 회기 안에 강좌를 다 듣게 되면, 이어서 들을 강좌를 추가해 주세요.</span>
          </td>
        </tr>
        <tr>
          <th>멘티<br />학습목표</th>
          <td colspan="3">
            <div v-if="source" class="course-card" data-test="fill-box" :data-source="source">
              <strong>AI로 초안 채우기</strong>
              <p class="notice" style="margin-top: 2px">비워 둔 학습목표와 학생진단을 {{ previous ? '지난 회기 요약' : '인계받은 내용' }}으로 채워 드립니다. 이미 적은 칸은 건드리지 않습니다.</p>
              <button type="button" :disabled="!!busy" data-test="fill" @click="fillDraft">{{ busy === 'fill' ? '채우는 중…' : SOURCE[source] }}</button>
            </div>
            <div v-if="changes && changes.mode === 'fill'" class="box ask changes" data-test="changes">
              <div class="row"><strong>AI가 새로 채운 내용 {{ changes.items.length }}곳</strong><span style="flex: 1"></span><button type="button" class="small" data-test="undo" @click="undoChanges">되돌리기</button></div>
              <ul><li v-for="(c, i) in changes.items" :key="i"><b>{{ c.label }}</b><ins>{{ c.after }}</ins></li></ul>
              <p class="notice">멘티가 말한 내용이 아니라 참고 자료로 쓴 초안입니다. 1회차에 이야기한 내용에 맞게 고쳐 주세요.</p>
            </div>
            <div class="cell-row"><span class="notice" style="flex: 1; margin: 0">{{ pre ? '종합계획서①에서 가져왔습니다. 1회차에 협의한 내용으로 고쳐 주세요.' : '1회차에 협의한 목표를 항목별로 적어 주세요.' }}</span>
              <button type="button" class="small" :disabled="!goalText" data-copy="learning_goal" @click="copy('멘티 학습목표', goalText)">복사</button></div>
            <label v-for="(s, i) in GOAL_SLOTS" :key="s.mark" class="slot"><span>{{ s.mark }} {{ s.label }}</span>
              <input v-model="goal.parts[i]" :placeholder="`예: ${s.example}`" :data-goal="i" /></label>
            <label v-if="goal.rest" class="slot"><span>그 밖에</span><textarea v-model="goal.rest" rows="2"></textarea></label>
          </td>
        </tr>
        <tr>
          <th>학생진단</th>
          <td colspan="3">
            <div class="cell-row"><span class="notice" style="flex: 1; margin: 0">1회차에 확인한 내용을 항목별로 적어 주세요. 확인하지 못한 항목은 비워 둡니다.</span>
              <button type="button" class="small" :disabled="!diagText" data-copy="diagnosis" @click="copy('학생진단', diagText)">복사</button></div>
            <label v-for="(s, i) in DIAG_SLOTS" :key="s.mark" class="slot"><span>{{ s.mark }}</span>
              <input v-model="diag.parts[i]" :placeholder="`예: ${s.example}`" :data-diag="i" /></label>
            <label v-if="diag.rest" class="slot"><span>그 밖에</span><textarea v-model="diag.rest" rows="2"></textarea></label>
          </td>
        </tr>
        <tr>
          <th>커리큘럼<br /><small data-sheet="course">{{ courseList }}</small></th>
          <td colspan="3">
            <div v-for="(c, ci) in courses" :key="ci" class="course-card">
              <details :open="!c.lectures.length" :data-test="`outline-${ci}`">
                <summary>{{ courseName(c) || `강좌 ${ci + 1}` }}의 목차 불러와서 커리큘럼 채우기{{ c.lectures.length ? ` · ${c.lectures.length}강 불러옴` : '' }}</summary>
                <p class="notice">학습사이트 강좌 페이지의 강의 목록을 통째로 복사해 붙여 넣으면 강의를 가려 읽습니다. 강의 제목이 제각각이어도 순서대로 몇 강인지 붙여 드립니다. 이 도구가 학습사이트에 접속하지는 않습니다.</p>
                <label v-if="savedCourses.length" class="field"><span class="name">전에 불러온 강좌에서 고르기</span>
                  <select :data-saved="ci" @change="useSaved(c, $event.target.value)">
                    <option value="">선택해 주세요</option><option v-for="s in savedCourses" :key="s.id" :value="s.id">{{ s.title }} ({{ s.lectures.length }}강)</option>
                  </select>
                </label>
                <textarea v-model="c.text" rows="4" placeholder="강의 목록을 여기에 붙여 넣어 주세요" :data-outline="ci"></textarea>
                <button type="button" style="margin-top: 8px" :disabled="!c.text.trim() || !!busy" :data-parse="ci" @click="parseOutline(c)">{{ busy === 'outline' ? '읽는 중…' : '목차 불러오기' }}</button>
              </details>
              <label class="row" style="gap: 6px; margin-top: 8px">이미 들은 강의 수 (선택) <input v-model="c.done" type="number" min="0" placeholder="0" style="width: 80px" :data-course="`done-${ci}`" /></label>
              <p v-if="c.note" class="notice" :data-note="ci">{{ c.note }}</p>
            </div>
            <div v-if="ready" class="course-card" data-test="alloc">
              <strong>불러온 강의를 주차에 나누기</strong> <span class="muted">아직 안 들은 강의 {{ ready }}강</span>
              <div class="choices" style="margin: 8px 0">
                <label><input v-model="alloc.mode" type="radio" value="weekly" name="alloc" />일주일에 <input v-model="alloc.perWeek" type="number" min="1" max="10" style="width: 64px" data-alloc="perWeek" /> 강씩</label>
                <label><input v-model="alloc.mode" type="radio" value="target" name="alloc" data-alloc="mode-target" />이번 회기에 <input v-model="alloc.target" type="number" min="1" :max="ready" style="width: 72px" placeholder="필수" data-alloc="target" /> 강 듣기 (회차에 고르게 나눔)</label>
              </div>
              <button type="button" class="primary" :disabled="!!busy || (alloc.mode === 'target' && !Number(alloc.target))" data-test="fill-curriculum" @click="fillCurriculum">{{ busy === 'fill-curriculum' ? '채우는 중…' : '커리큘럼 채우기' }}</button>
              <p v-if="fillNote" class="notice" data-test="fill-note">{{ fillNote }}</p>
            </div>
            <div class="cell-row"><span class="notice" style="flex: 1; margin: 0">서식에는 주차마다 "(온라인강의) 강좌명(강사명), n강" 줄바꿈 "(멘토링 내용) 학습 내용"으로 들어갑니다. 주차마다 [복사]하거나 전체를 복사해 주세요.</span>
              <button type="button" class="small" :disabled="!curriculumText" data-copy="curriculum" @click="copy('커리큘럼 전체', curriculumText)">전체 복사</button></div>
            <CurriculumEditor v-model="rows" :rounds="rounds" :start="profile.start_datetime || ''" :courses="courses" full copyable
              @copy="(r) => copy(`${r.week}주차`, curriculumCell(r, courses))" />
          </td>
        </tr>
        <tr>
          <th>멘토링<br />구성</th>
          <td colspan="3">
            <div class="cell-row"><span style="flex: 1"></span><button type="button" class="small" :disabled="!plain.structure.trim()" data-copy="structure" @click="copy('멘토링 구성', plain.structure)">복사</button></div>
            <textarea v-model="plain.structure" :rows="Math.max(5, plain.structure.split('\n').length)" placeholder="17:00~17:10 온라인 강의 수강(필수) 확인 & 퀴즈&#10;17:10~17:30 개념학습&#10;… (비워 두고 저장하면 시간 배분 기본안이 들어갑니다)" data-field="structure"></textarea>
          </td>
        </tr>
        <tr>
          <th>활동규칙</th>
          <td colspan="3">
            <div class="cell-row"><span style="flex: 1"></span><button type="button" class="small" :disabled="!plain.rules.trim()" data-copy="rules" @click="copy('활동규칙', plain.rules)">복사</button></div>
            <textarea v-model="plain.rules" :rows="Math.max(5, plain.rules.split('\n').length)" placeholder="한 줄에 규칙 하나씩&#10;멘토링 시간 준수하기&#10;일정 변경은 최소 3일 전에 논의하기" data-field="rules"></textarea>
          </td>
        </tr>
      </table>

      <div v-if="changes && changes.mode === 'polish'" class="box ask changes" data-test="changes">
        <div class="row"><strong>AI가 표현을 다듬은 곳 {{ changes.items.length }}곳</strong><span style="flex: 1"></span><button type="button" class="small" data-test="undo" @click="undoChanges">되돌리기</button></div>
        <ul><li v-for="(c, i) in changes.items" :key="i"><b>{{ c.label }}</b><del v-if="c.before.trim()">{{ c.before }}</del><ins>{{ c.after || '(비워짐)' }}</ins></li></ul>
      </div>
      <div v-if="notes.length" class="box warn" data-test="notes"><ul><li v-for="n in notes" :key="n">{{ n }}</li></ul></div>
      <div class="row">
        <button class="primary" :disabled="!!busy" data-test="save">{{ busy === 'save' ? '저장하는 중…' : '저장' }}</button>
        <button type="button" :disabled="!!busy" data-test="polish" @click="polish">{{ busy === 'polish' ? '다듬는 중…' : 'AI로 표현 다듬기' }}</button>
        <router-link v-if="done" :to="menteePath(alias, '/report/1')"><button type="button">1회차 활동보고서 쓰기</button></router-link>
      </div>
      <p class="notice">저장은 AI를 쓰지 않습니다. 표현 다듬기는 종합계획서①에서 가져온 뒤 새로 적거나 고친 줄만 다듬고, 무엇이 바뀌었는지 보여 드립니다.</p>
    </form>
  </div>
</template>
