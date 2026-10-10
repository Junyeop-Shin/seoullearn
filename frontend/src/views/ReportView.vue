<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import DraftResult from '../components/DraftResult.vue'
import MenteeHeader from '../components/MenteeHeader.vue'
import { fillValues, menteePath, profileFromVault, regularSchedule, suggestDate } from '../lib/mentee'
import { curriculumRow, plannedRow, previousHomework } from '../lib/reports'
import { endTime } from '../lib/schedule'
import { afterReport, totalRounds } from '../lib/stage'
import { toast } from '../lib/toast'
import { loadSettings } from '../stores/settings'
import { listItems, saveItem } from '../stores/vault'

// 한 회차 활동보고서. 멘토는 체크와 짧은 메모만 하고, 날짜·과목·지난 과제·이번 주 계획은 저장된 자료에서 채운다.
// 저장하면 다음 회차로 넘어가고, 이번에 낸 과제는 다음 회차의 '지난 과제 확인'에 다시 나온다.
const FORM_ID = 'activity_report'
defineOptions({ inheritAttrs: false })   // 멘티 화면이 모든 단계에 같은 값을 넘긴다: 안 쓰는 값이 화면 요소에 붙지 않게 한다
const props = defineProps({ embedded: { type: Boolean, default: false }, round: { type: Number, default: 0 } })
const emit = defineEmits(['saved'])
const route = useRoute()
const alias = String(route.params.alias)
const no = ref(props.round || Number(route.params.no) || 0)
const form = ref(null)
const profile = ref(null)
const items = ref([])
const savedId = ref(undefined)
const result = ref(null)
const edited = ref(null)
const busy = ref('')
const error = ref('')
const prevHw = ref(null)
const plan = ref(null)
let payload = {}

const STATUS = ['출석', '지각', '무단결석', '인정결석']
const LECTURE = ['다 들음', '일부 들음', '안 들음']
const TASK = ['함', '일부 함', '안 함']
// 멘토가 실제로 고르고 적은 것. 저장해 두었다가 다시 열거나 다시 만들 때 쓴다
const q = reactive({ status: '출석', date: '', time: '', subject: '', course: '', lectureDone: '', taskDone: '', asPlanned: true, scope: '', goal: '',
  progress: '', understanding: '', good: '', lacking: '', special: '', nextLecture: '', nextTask: '', requests: '' })
const absent = computed(() => ['무단결석', '인정결석'].includes(q.status))
const scales = computed(() => form.value?.fields.find((f) => f.key === 'progress_scale')?.options || [])
const fill = computed(() => fillValues(profile.value, loadSettings()))

onMounted(async () => {
  try {
    form.value = await api.form(FORM_ID)
    items.value = await listItems(alias)
    profile.value = profileFromVault(items.value)
    if (!no.value) no.value = profile.value?.currentRound || 1
    prevHw.value = previousHomework(items.value, no.value, profile.value)
    plan.value = curriculumRow(items.value, no.value)
    const existing = items.value.filter((x) => x.formId === FORM_ID && Number(x.sessionNo ?? x.inputs?.session_no) === no.value)
      .sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1))[0]
    if (existing) {
      // 저장한 보고서를 다시 연다. 예전에 저장한 것은 빠른 입력 원본이 없어 입력값에서 되살린다
      savedId.value = existing.id
      const i = existing.inputs || {}
      Object.assign(q, { status: i.status || '출석', date: i.session_date || '', time: i.actual_time || '', subject: i.subject || '', course: i.course || '',
        scope: i.scope || '', goal: i.goal || '', progress: i.progress_scale || '', understanding: i.understanding_scale || '', good: i.session_content || '',
        special: i.etc || '', requests: i.requests || '', nextLecture: existing.extra?.assignedHomework?.lecture || '', nextTask: existing.extra?.assignedHomework?.task || '' },
        existing.extra?.quick || {})
      payload = i
      result.value = { draft: existing.draft, missing_questions: [], warnings: [], reminders: [], pii_masked: [] }
      edited.value = existing.draft
      return
    }
    const p = profile.value || {}
    const first = regularSchedule(p)[0]
    const when = plannedRow(items.value, no.value)   // 계획서에서 이 회차의 일시를 고쳐 두었으면 그것을 쓴다
    Object.assign(q, { date: when?.date || suggestDate(p.start_datetime, no.value), subject: p.subject === '기타' ? p.subjectEtc || '' : p.subject || '', course: p.course || '',
      time: when?.time || first?.startTime ? `${when?.time || first.startTime}~${endTime(when?.time || first.startTime, p.duration)}` : '',
      scope: plan.value?.online || plan.value?.content || '', goal: plan.value?.mentoring || '' })
  } catch (e) {
    error.value = e.message
  }
})

const hwText = (label, what, done) => (done ? `${label}${what ? `(${what})` : ''}: ${done}` : '')

function inputs() {
  const content = [q.good && `잘한 점: ${q.good}`, q.lacking && `아쉬운 점: ${q.lacking}`].filter(Boolean).join('\n')
  return {
    status: q.status, session_date: q.date, session_no: String(no.value), subject: q.subject, course: q.course, actual_time: q.time,
    scope: q.scope, goal: q.goal, progress_scale: q.progress, understanding_scale: q.understanding,
    attendance: q.status === '출석' ? '정시 출석' : q.status,
    lecture_progress: hwText('지난 회차 인강', prevHw.value?.lecture, q.lectureDone), homework: hwText('지난 회차 과제', prevHw.value?.task, q.taskDone),
    session_content: content, etc: q.special, requests: q.requests,
  }
}

async function submit(only) {
  error.value = ''
  busy.value = only || 'all'
  try {
    payload = inputs()
    // 멘토가 고르고 적은 것만 보낸다. 다듬기에는 다른 자료를 섞지 않는다 (입력에 없는 내용이 들어가지 않게)
    const res = await api.draft(FORM_ID, payload, only ? { only: [only] } : {})
    if (only && edited.value) {
      // 한 항목만 다시 만든다: 나머지 칸은 화면에서 고친 그대로 둔다
      result.value = { ...res, draft: { ...edited.value, [only]: res.draft[only] } }
    } else result.value = res
    edited.value = result.value.draft
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}

async function save() {
  try {
    const item = await saveItem({ id: savedId.value, alias, formId: FORM_ID, title: `활동보고서 ${no.value}회차`, sessionNo: no.value, inputs: payload, draft: edited.value,
      extra: { assignedHomework: { lecture: q.nextLecture.trim(), task: q.nextTask.trim() }, quick: { ...q } } })
    savedId.value = item.id
    // 지금 회차를 저장했으면 다음 회차(마지막 회차였으면 완료보고서)로 넘어간다
    const step = profile.value ? afterReport(profile.value, no.value) : {}
    if (Object.keys(step).length) {
      const { _id, ...rest } = profile.value
      await saveItem({ id: _id, alias, formId: 'mentee_profile', title: '멘티 정보', draft: { ...rest, ...step } })
    }
    toast(step.stage ? '저장했습니다. 마지막 회차라 완료보고서 단계로 넘어갑니다.' : step.currentRound ? `저장했습니다. 다음은 ${step.currentRound}회차입니다.` : '저장했습니다.')
    emit('saved')
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div :class="{ shell: !embedded }">
    <template v-if="!embedded">
      <MenteeHeader :alias="alias" :title="`활동보고서 ${no}회차`" />
      <h1>{{ no }}회차 활동보고서</h1>
    </template>
    <p class="muted">고르고 짧게 적으면 보고서 문장으로 정리해 드립니다. 적지 않은 내용은 만들지 않습니다. 멘토링 후 7일 이내에 제출합니다.</p>
    <div v-if="error" class="box error">{{ error }}</div>
    <p v-if="savedId && result" class="box ask" data-test="reopened">저장해 둔 {{ no }}회차 보고서를 다시 열었습니다. 아래에서 고쳐 다시 저장하거나, 입력을 바꿔 새로 만들 수 있습니다.</p>

    <form v-if="form" class="card" @submit.prevent="submit()">
      <section class="form-section">
        <h3>기본 정보 (자동으로 채움)</h3>
        <div class="form-grid">
          <label class="field"><span class="name">회차 상태</span><select v-model="q.status" data-q="status"><option v-for="s in STATUS" :key="s">{{ s }}</option></select></label>
          <label class="field"><span class="name">진행일</span><input v-model="q.date" type="date" required data-q="date" /></label>
          <label class="field"><span class="name">진행시간 (실제 접속시간)</span><input v-model="q.time" placeholder="예: 17:03~18:05" data-q="time" />
            <span class="notice">계획한 일정으로 채웠습니다. 플랫폼 접속 기록과 같은 실제 시작~종료 시간으로 고쳐 주세요.</span></label>
          <label class="field"><span class="name">과목 · 수강 강좌</span>
            <span class="row"><input v-model="q.subject" style="flex: 1" aria-label="과목" data-q="subject" /><input v-model="q.course" style="flex: 2" aria-label="수강 강좌" data-q="course" /></span></label>
        </div>
        <p v-if="absent" class="notice">결석한 회차는 학습 내용 칸을 비워 두고 필요한 증빙을 안내해 드립니다.</p>
      </section>

      <template v-if="!absent">
        <section class="form-section">
          <h3>지난 회차 과제 확인</h3>
          <p v-if="prevHw" class="mini" data-test="prev-homework">
            <span class="t">지난 회차에 낸 것</span>인강: {{ prevHw.lecture || '-' }} · 과제: {{ prevHw.task || '-' }}
          </p>
          <p v-else class="notice">지난 회차에 낸 과제 기록이 없습니다. 해당하는 것만 골라 주세요.</p>
          <div class="form-grid">
            <div class="field"><span class="name">인강 수강</span>
              <span class="choices"><label v-for="x in LECTURE" :key="x"><input v-model="q.lectureDone" type="radio" :value="x" name="lecture" />{{ x }}</label></span></div>
            <div class="field"><span class="name">과제 수행</span>
              <span class="choices"><label v-for="x in TASK" :key="x"><input v-model="q.taskDone" type="radio" :value="x" name="task" />{{ x }}</label></span></div>
          </div>
        </section>

        <section class="form-section">
          <h3>이번 회차 학습</h3>
          <div v-if="plan" class="field">
            <span class="choices" data-test="as-planned">
              <label><input v-model="q.asPlanned" type="radio" :value="true" name="planned" />계획대로 진행</label>
              <label><input v-model="q.asPlanned" type="radio" :value="false" name="planned" />계획과 다르게 진행</label>
            </span>
            <span class="notice">종합계획서의 {{ no }}주차 계획을 채웠습니다. 다르게 진행했다면 아래를 고쳐 주세요.</span>
          </div>
          <div class="form-grid">
            <label class="field"><span class="name">학습 범위(혹은 목차)</span><input v-model="q.scope" :readonly="!!plan && q.asPlanned" placeholder="예: 3~4강 지수법칙" data-q="scope" /></label>
            <label class="field"><span class="name">학습 목표</span><input v-model="q.goal" :readonly="!!plan && q.asPlanned && !!q.goal" placeholder="예: 지수법칙 개념 이해와 기본 문제 풀이" data-q="goal" /></label>
            <label class="field"><span class="name">학습 진도(성실성) 평가</span><select v-model="q.progress" data-q="progress"><option value="">선택해 주세요</option><option v-for="s in scales" :key="s">{{ s }}</option></select></label>
            <label class="field"><span class="name">학습 이해도 평가</span><select v-model="q.understanding" data-q="understanding"><option value="">선택해 주세요</option><option v-for="s in scales" :key="s">{{ s }}</option></select></label>
          </div>
        </section>

        <section class="form-section">
          <h3>한 줄 메모 (선택)</h3>
          <div class="form-grid">
            <label class="field"><span class="name">잘한 점</span><input v-model="q.good" placeholder="예: 예제는 혼자 풀어냄" data-q="good" /></label>
            <label class="field"><span class="name">아쉬운 점</span><input v-model="q.lacking" placeholder="예: 서술형에서 풀이 과정을 건너뜀" data-q="lacking" /></label>
            <label class="field wide"><span class="name">특이사항</span><input v-model="q.special" placeholder="예: 다음 주 시험으로 일정 조정 논의" data-q="special" /></label>
          </div>
          <p class="notice">멘티 이름·연락처·학교는 쓰지 마세요. 적혀 있으면 AI에 보내기 전에 가립니다. 정서·가정 이야기는 보고서에 넣지 않습니다.</p>
        </section>
      </template>

      <section class="form-section">
        <h3>다음 회차 과제</h3>
        <div class="form-grid">
          <label class="field"><span class="name">인강 범위</span><input v-model="q.nextLecture" placeholder="예: 5~6강" data-q="nextLecture" /></label>
          <label class="field"><span class="name">과제</span><input v-model="q.nextTask" placeholder="예: 5강 예제 풀기" data-q="nextTask" /></label>
        </div>
        <p class="notice">다음 회차 보고서의 '지난 회차 과제 확인'에 다시 나옵니다. 이 브라우저에만 저장됩니다.</p>
        <label class="field"><span class="name">건의사항 (선택)</span><input v-model="q.requests" data-q="requests" /></label>
      </section>
      <button class="primary" :disabled="!!busy" data-test="draft">{{ busy === 'all' ? '초안을 만드는 중입니다…' : result ? '초안 다시 만들기' : '초안 만들기' }}</button>
    </form>

    <template v-if="result">
      <h2>플랫폼에 옮길 내용</h2>
      <DraftResult :form="form" :result="result" :fill="fill" regen :busy-key="busy === 'all' ? '' : busy" @change="edited = $event" @regen="submit" />
      <div class="card row">
        <button type="button" class="primary" data-test="save" @click="save">저장</button>
        <router-link v-if="!embedded" :to="menteePath(alias)"><button type="button">멘티 화면으로 돌아가기</button></router-link>
        <span class="notice" style="margin: 0">저장하면 {{ profile && no === profile.currentRound && profile.stage === 'ACTIVITY' ? (no >= totalRounds(profile) ? '완료보고서 단계' : `${no + 1}회차`) + '(으)로 넘어가고, ' : '' }}완료보고서와 인계 요약을 만들 때 쓰입니다.</span>
      </div>
    </template>
  </div>
</template>
