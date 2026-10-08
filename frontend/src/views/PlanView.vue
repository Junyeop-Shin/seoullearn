<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api/client'
import { useRoute } from 'vue-router'
import MenteeHeader from '../components/MenteeHeader.vue'
import DraftResult from '../components/DraftResult.vue'
import SchemaForm from '../components/SchemaForm.vue'
import { emptyInputs, inputFields, toPayload } from '../lib/formFields'
import { menteePath, preContactFromProfile, profileFromVault, subjectTimeText } from '../lib/mentee'
import { COURSE_ALIAS, COURSE_FORM, coursesFromVault, handoverFromVault } from '../lib/reports'
import { toast } from '../lib/toast'
import { listItems, saveItem } from '../stores/vault'

// 종합계획서: ① 강의 목차 → ② 주차별 계획 → ③ 종합계획서①(플랫폼 입력) → ④ 종합계획서②(서식 파일)
const alias = ref(String(useRoute().params.alias))
const error = ref('')
const busy = ref('')
const status = ref('')

// ① 목차
const outlineText = ref('')
const outline = ref(null)
const courses = ref([])       // 보관함에 저장해 둔 내 강좌
const pickedCourse = ref('')
const courseName = ref('')
const courseStatus = ref('')

async function loadCourses() {
  try {
    courses.value = coursesFromVault(await listItems(COURSE_ALIAS))
  } catch {
    courses.value = []
  }
}

function useCourse() {
  const c = courses.value.find((x) => x.id === pickedCourse.value)
  if (!c) return
  outline.value = { lectures: c.lectures, warnings: [], unparsed: [] }
  courseName.value = c.title
  courseStatus.value = `'${c.title}' ${c.lectures.length}강을 불러왔습니다.`
}

async function saveCourse() {
  try {
    const same = courses.value.find((x) => x.title === courseName.value.trim())
    await saveItem({ id: same?.id, alias: COURSE_ALIAS, formId: COURSE_FORM, title: courseName.value.trim(), draft: { lectures: outline.value.lectures } })
    courseStatus.value = same ? '같은 이름의 강좌를 새 목차로 바꿔 저장했습니다.' : '내 강좌에 저장했습니다. 다음부터는 목록에서 고르면 됩니다.'
    await loadCourses()
  } catch (e) {
    courseStatus.value = e.message
  }
}
// ② 주차별 계획
const opt = reactive({ done: 0, pace: '보통', startDate: '', examStart: '', examEnd: '', breakStart: '', breakEnd: '' })
const plan = ref(null)
// ③ 종합계획서①
const formInitial = ref(null)
const fieldsInitial = computed(() => (formInitial.value ? inputFields(formInitial.value) : []))
const valuesInitial = ref({})
const mode = ref('온라인')
const answers = ref({})
const handover = reactive({ attendance_pattern: '', homework_pattern: '', attitude: '', course_progress: '' })
const HANDOVER = [['attendance_pattern', '출석 패턴'], ['homework_pattern', '과제 수행'], ['attitude', '학습 태도'], ['course_progress', '수강 강의와 진도']]
const resultInitial = ref(null)
const editedInitial = ref(null)
// ④ 종합계획서②
const formFile = ref(null)
const fieldsFile = computed(() => (formFile.value ? inputFields(formFile.value) : []))
const valuesFile = ref({})
const counseling = reactive({ level: '', goal: '', career: '' })
const resultFile = ref(null)

onMounted(async () => {
  try {
    ;[formInitial.value, formFile.value] = await Promise.all([api.form('plan_initial'), api.form('plan_file')])
    valuesInitial.value = emptyInputs(fieldsInitial.value)
    valuesFile.value = emptyInputs(fieldsFile.value)
    await loadCourses()
    await loadAnswers()
  } catch (e) {
    error.value = e.message
  }
})

async function run(name, fn) {
  error.value = status.value = ''
  busy.value = name
  try {
    await fn()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}

watch(alias, loadAnswers)

const parseOutline = () => run('outline', async () => {
  outline.value = await api.courseOutline(outlineText.value)
})

const makePlan = () => run('plan', async () => {
  const range = (a, b) => (a && b ? [{ start: a, end: b }] : [])
  plan.value = await api.weeklyPlan({
    lectures: outline.value.lectures, done: Number(opt.done) || 0, pace: opt.pace, start_date: opt.startDate || null,
    exams: range(opt.examStart, opt.examEnd), breaks: range(opt.breakStart, opt.breakEnd),
  })
})

// 멘티를 고르면 '내 멘티'에 적어 둔 일정·과목·목표와 저장해 둔 인계 요약을 불러온다
async function loadAnswers() {
  status.value = ''
  if (!alias.value.trim() || !formInitial.value) return
  const items = await listItems(alias.value.trim())
  const p = profileFromVault(items)
  if (p) {
    answers.value = preContactFromProfile(p)
    if (p.mode) mode.value = p.mode
    const v = { ...valuesInitial.value }
    for (const k of ['duration', 'weekday', 'start_datetime']) if (p[k] && !String(v[k] ?? '').trim()) v[k] = p[k]
    valuesInitial.value = v
    if (p.start_datetime && !opt.startDate) opt.startDate = p.start_datetime.slice(0, 10)
    const st = subjectTimeText(p)
    if (st && !String(valuesFile.value.subject_time ?? '').trim()) valuesFile.value = { ...valuesFile.value, subject_time: st }
    const course = courses.value.find((c) => p.course && (c.title === p.course || p.course.includes(c.title) || c.title.includes(p.course)))
    if (course && !outline.value) {
      pickedCourse.value = course.id
      useCourse()
    }
    status.value = '기본 정보에서 일정과 목표를 불러왔습니다.'
  } else status.value = '기본 정보가 아직 없습니다. 멘티 화면에서 적어 두면 일정과 목표가 자동으로 채워집니다.'
  const ho = handoverFromVault(items)
  if (ho) {
    for (const k of Object.keys(handover)) handover[k] = ho[k] || ''
    status.value += ' 보관함의 인계 요약도 불러왔습니다.'
  }
}

function handoverGiven() {
  return Object.fromEntries(Object.entries(handover).filter(([, v]) => v.trim()))
}

const draftInitial = () => run('initial', async () => {
  const inputs = toPayload(fieldsInitial.value, valuesInitial.value)
  const extra = { pre_contact: answers.value, mode: mode.value }
  if (plan.value) extra.weekly_plan = plan.value.sessions
  if (Object.keys(handoverGiven()).length) extra.handover = handoverGiven()
  resultInitial.value = await api.draft('plan_initial', inputs, extra)
  editedInitial.value = resultInitial.value.draft
})

const draftFile = () => run('file', async () => {
  const start = toPayload(fieldsInitial.value, valuesInitial.value)
  const extra = { start_datetime: start.start_datetime, duration: Number(start.duration) || 60, counseling: { ...counseling } }
  if (plan.value) extra.weekly_plan = plan.value.sessions
  if (editedInitial.value) extra.plan_initial = { learning_goal: editedInitial.value.learning_goal }
  resultFile.value = await api.draft('plan_file', toPayload(fieldsFile.value, valuesFile.value), extra)
})

async function save(formId, title, draft) {
  try {
    await saveItem({ alias: alias.value, formId, title, inputs: toPayload(fieldsInitial.value, valuesInitial.value),
      extra: { weekly_plan: plan.value?.sessions || [] }, draft })
    toast('보관함에 저장했습니다.')
  } catch (e) {
    toast(e.message)
  }
}

const CONFIRM = '종합계획서①은 플랫폼에 등록한 뒤에는 수정할 수 없습니다(1회차 일정만 변경 가능). 내용을 모두 확인하셨나요?'
</script>

<template>
  <div class="shell">
    <MenteeHeader :alias="alias" title="종합계획서" />
    <h1>종합계획서 작성</h1>
    <p v-if="status" class="notice" data-test="profile-status">{{ status }}</p>
    <div v-if="error" class="box error">{{ error }}</div>

    <h2>① 강의 목차 붙여 넣기</h2>
    <div class="card">
      <label v-if="courses.length" class="field" data-test="saved-courses"><span class="name">저장해 둔 강좌에서 고르기</span>
        <select v-model="pickedCourse" @change="useCourse">
          <option value="">선택해 주세요</option>
          <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.title }} ({{ c.lectures.length }}강)</option>
        </select>
      </label>
      <p class="muted">{{ courses.length ? '새 강좌라면 ' : '' }}학습사이트 강좌 페이지에서 목차를 복사해 붙여 넣어 주세요. 이 도구가 학습사이트에 접속하지는 않습니다.</p>
      <textarea v-model="outlineText" rows="6" placeholder="1강 문학 감상의 관점&#10;2강 시적 화자와 정서&#10;…"></textarea>
      <button type="button" class="primary" style="margin-top: 8px" :disabled="!outlineText.trim() || busy === 'outline'" @click="parseOutline">강 목록으로 정리</button>
      <template v-if="outline">
        <p>{{ outline.lectures.length }}강을 읽었습니다.</p>
        <div v-if="outline.warnings.length" class="box warn"><ul><li v-for="w in outline.warnings" :key="w">{{ w }}</li></ul></div>
        <div v-if="outline.lectures.length" class="row" data-test="save-course">
          <input v-model="courseName" placeholder="강좌 이름 (예: 대성마이맥 고1 국어 문학 개념)" maxlength="60" style="flex: 1; min-width: 220px" aria-label="강좌 이름" />
          <button type="button" :disabled="!courseName.trim()" @click="saveCourse">내 강좌로 저장</button>
        </div>
        <p v-if="courseStatus" class="notice">{{ courseStatus }}</p>
        <p v-else-if="outline.lectures.length" class="notice">저장해 두면 다음 회기나 다른 멘티 때 다시 붙여 넣지 않아도 됩니다. 이 브라우저에만 저장됩니다.</p>
      </template>
    </div>

    <h2>② 주차별 계획</h2>
    <div class="card">
      <div class="row">
        <label class="field" style="flex: 1"><span class="name">이미 들은 강 수</span><input v-model="opt.done" type="number" min="0" /></label>
        <label class="field" style="flex: 1"><span class="name">학습 속도</span><select v-model="opt.pace"><option>느림</option><option>보통</option><option>빠름</option></select></label>
        <label class="field" style="flex: 1"><span class="name">1회차 날짜</span><input v-model="opt.startDate" type="date" /></label>
      </div>
      <div class="row">
        <label class="field" style="flex: 1"><span class="name">시험 기간 (선택)</span><input v-model="opt.examStart" type="date" /></label>
        <label class="field" style="flex: 1"><span class="name">~</span><input v-model="opt.examEnd" type="date" /></label>
        <label class="field" style="flex: 1"><span class="name">방학 (선택)</span><input v-model="opt.breakStart" type="date" /></label>
        <label class="field" style="flex: 1"><span class="name">~</span><input v-model="opt.breakEnd" type="date" /></label>
      </div>
      <button type="button" class="primary" :disabled="!outline?.lectures.length || busy === 'plan'" @click="makePlan">16회차 계획 만들기</button>
      <template v-if="plan">
        <div v-if="plan.warnings.length" class="box warn"><ul><li v-for="w in plan.warnings" :key="w">{{ w }}</li></ul></div>
        <table style="margin-top: 10px">
          <tr><th>회차</th><th>날짜</th><th>종류</th><th>계획</th></tr>
          <tr v-for="s in plan.sessions" :key="s.no"><td>{{ s.no }}</td><td>{{ s.date || '-' }}</td><td>{{ s.kind }}</td><td>{{ s.line }}</td></tr>
        </table>
      </template>
    </div>

    <h2>③ 종합계획서① (플랫폼 입력)</h2>
    <form v-if="formInitial" class="card" @submit.prevent="draftInitial">
      <label class="field"><span class="name">멘토링 유형</span><select v-model="mode"><option>온라인</option><option>오프라인</option></select></label>
      <SchemaForm v-model="valuesInitial" :fields="fieldsInitial" />
      <div class="mini" data-test="profile-used">
        <span class="t">초안에 쓰는 멘티 정보</span>
        <template v-if="Object.keys(answers).length">
          <div v-if="answers.subject_confirm">과목·유형: {{ answers.subject_confirm }}</div>
          <div v-if="answers.site_course">강좌: {{ answers.site_course }}</div>
          <div v-if="answers.goal">목표: {{ answers.goal }}</div>
          <div v-if="answers.level">학습 상황: {{ answers.level }}</div>
        </template>
        <div v-else>적어 둔 멘티 정보가 없습니다. 목표와 학습 상황 없이 만들면 학습목표와 학생진단이 거의 비게 됩니다.</div>
        <router-link :to="menteePath(alias)">기본 정보에서 고치기</router-link>
      </div>
      <details>
        <summary>이전 멘토의 인계 요약이 있으면 입력 (멘토 교체)</summary>
        <label v-for="[k, label] in HANDOVER" :key="k" class="field"><span class="name">{{ label }}</span><textarea v-model="handover[k]"></textarea></label>
        <p class="notice">이 네 가지만 받습니다. 학업 수준(성적·이해도)과 정서·상담 내용은 넘기지 않습니다.</p>
      </details>
      <button class="primary" style="margin-top: 10px" :disabled="busy === 'initial'">{{ busy === 'initial' ? '초안을 만드는 중입니다…' : '종합계획서① 초안 만들기' }}</button>
    </form>
    <template v-if="resultInitial">
      <DraftResult :form="formInitial" :result="resultInitial" :confirm-before-copy="CONFIRM" @change="editedInitial = $event" />
      <button type="button" @click="save('plan_initial', '종합계획서①', editedInitial)">보관함에 저장</button>
    </template>

    <h2>④ 종합계획서② (1회차 후, 서식 파일)</h2>
    <form v-if="formFile" class="card" @submit.prevent="draftFile">
      <p class="muted">1회차 멘토링에서 확인한 내용을 적어 주세요. 위 ②의 계획과 ③의 시작 일시를 함께 씁니다.</p>
      <SchemaForm v-model="valuesFile" :fields="fieldsFile" />
      <label class="field"><span class="name">1회차 상담: 멘티가 말한 목표</span><textarea v-model="counseling.goal"></textarea></label>
      <label class="field"><span class="name">1회차 상담: 희망 진로 (말한 경우만)</span><textarea v-model="counseling.career"></textarea></label>
      <button class="primary" :disabled="busy === 'file'">{{ busy === 'file' ? '초안을 만드는 중입니다…' : '종합계획서② 초안 만들기' }}</button>
    </form>
    <template v-if="resultFile">
      <DraftResult :form="formFile" :result="resultFile" />
      <button type="button" @click="save('plan_file', '종합계획서②', resultFile.draft)">보관함에 저장</button>
    </template>
  </div>
</template>
