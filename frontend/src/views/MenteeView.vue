<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import StageBar from '../components/StageBar.vue'
import NavIcon from '../components/NavIcon.vue'
import { KEEP_AFTER_TERM, PROFILE_FORM, facts, menteePath, profileFromVault, regularSchedule, setCurrentAlias } from '../lib/mentee'
import { TERM_SUMMARY_FORM, termSummary } from '../lib/reports'
import { flow, nextStage, nextTerm, prevStage, totalRounds } from '../lib/stage'
import { toast } from '../lib/toast'
import { listItems, removeAlias, saveItem } from '../stores/vault'
import CompletionView from './CompletionView.vue'
import ReportView from './ReportView.vue'
import PlanningStage from './stages/PlanningStage.vue'
import PreContactStage from './stages/PreContactStage.vue'

// 멘티 화면: 멘티 한 명의 업무를 단계 순서대로 진행한다 (사전 연락 → 종합계획서 → 회차별 활동보고서 → 완료보고서). 위에는 단계 진행바, 가운데는 지금 단계의 화면,
// 아래에는 [이전] [다음 단계]가 있다. 단계와 무관한 일(정보 수정, 지난 보고서, 자료 관리)은 이름 옆의 설정 버튼으로 가는 멘티 설정 화면에 있다.
const STAGE_VIEW = { PRE_CONTACT: PreContactStage, PLAN: PlanningStage, ACTIVITY: ReportView, COMPLETION: CompletionView }
const NEXT_LABEL = { PRE_CONTACT: '사전 연락 완료', PLAN: '종합계획서 작성 완료' }
const route = useRoute()
const alias = String(route.params.alias)
const items = ref([])
const loaded = ref(false)
const viewing = ref('')
const termMinutes = ref('60')
const saved = computed(() => profileFromVault(items.value))
const stages = computed(() => flow(saved.value))
const viewKey = ref(0)

async function refresh() {
  items.value = await listItems(alias)
  loaded.value = true
  const p = saved.value
  if (!p) return
  termMinutes.value = String(p.duration || '60')
  if (!flow(p).some((s) => s.id === viewing.value)) viewing.value = p.stage
}

onMounted(async () => {
  setCurrentAlias(alias)
  await refresh()
})

/** 멘티 정보의 일부를 바꿔 저장한다. 단계 화면들이 함께 쓴다. */
async function update(patch, message = '') {
  const { _id, ...rest } = saved.value
  await saveItem({ id: _id, alias, formId: PROFILE_FORM, title: '멘티 정보', draft: { ...rest, ...patch } })
  if (message) toast(message)
  await refresh()
}

async function go(stage) {
  // 종합계획서②를 쓰지 않고 넘어가려 하면 한 번 묻는다 (①을 저장한 뒤 바로 눈에 띄는 버튼이 '다음 단계'다)
  if (saved.value.stage === 'PLAN' && stage === 'ACTIVITY' && !items.value.some((x) => x.formId === 'plan_file')
    && !window.confirm('종합계획서②를 아직 저장하지 않았습니다. 활동보고서로 넘어갈까요?')) return
  await update({ stage })
  viewing.value = stage
  viewKey.value += 1
  window.scrollTo({ top: 0 })
}

// 단계 화면에서 저장한 뒤: 활동보고서는 다음 회차로 넘어갔으므로 화면을 새로 그린다
async function afterSave() {
  const before = saved.value?.stage
  await refresh()
  viewKey.value += 1
  if (saved.value.stage !== before) viewing.value = saved.value.stage
}

const nextCourse = ref('')   // 다음 회기에 들을 강좌: 다음 회기 종합계획서의 수강 목표와 멘티 정보의 강좌에 들어간다
async function startNextTerm() {
  if (!window.confirm('다음 회기를 시작하면 이번 회기의 종합계획서와 활동보고서를 이 브라우저에서 지웁니다. 멘티 정보, 완료보고서, 인계 요약, 회기 요약은 남습니다. 활동비 계산에서도 이번 회기 회차가 빠지니 지급 전이면 먼저 확인해 주세요. 시작할까요?')) return
  // 지난 회기의 계획서·활동보고서·완료보고서에서 요약을 추려 남긴다: 새 회기의 종합계획서를 이어서 쓰는 재료다
  await saveItem({ alias, formId: TERM_SUMMARY_FORM, title: `${saved.value.term}회기 요약`, draft: termSummary(items.value, saved.value, nextCourse.value) })
  await removeAlias(alias, KEEP_AFTER_TERM)
  const { _id, ...rest } = saved.value
  await saveItem({ id: _id, alias, formId: PROFILE_FORM, title: '멘티 정보', draft: { ...nextTerm(rest, termMinutes.value), regularSchedule: regularSchedule(rest), course: nextCourse.value.trim() || rest.course || '' } })
  await refresh()
  viewing.value = saved.value.stage
  viewKey.value += 1
  toast(`${saved.value.term}회기를 시작했습니다.`)
}

</script>

<template>
  <div class="shell">
    <template v-if="saved">
      <header class="mentee-head" data-test="mentee-head">
        <div class="row">
          <h1 class="grow">{{ saved.name || alias }}</h1>
          <router-link :to="menteePath(alias, '/manage')" class="linkbutton small" data-test="manage"><NavIcon name="settings" />멘티 설정</router-link>
        </div>
        <div class="row">
          <span v-for="x in facts(saved)" :key="x" class="tag">{{ x }}</span>
          <span class="tag strong" data-test="round">{{ saved.term }}회기 {{ saved.currentRound }}회차</span>
          <span v-if="saved.archived" class="tag">종료한 멘티</span>
        </div>
      </header>
      <StageBar :stages="stages" :current="saved.stage" :viewing="viewing" @view="if ($event !== viewing) { viewing = $event; viewKey += 1 }" />
      <p v-if="viewing !== saved.stage" class="box ask" data-test="viewing-other">
        지금 단계는 '{{ stages.find((s) => s.id === saved.stage)?.label }}'입니다. 다른 단계의 화면을 보고 있습니다. 여기서 고친 내용도 저장됩니다.
        <button type="button" class="small" @click="viewing = saved.stage; viewKey += 1">지금 단계로</button>
      </p>

      <h2>{{ viewing === 'ACTIVITY' ? `${saved.currentRound}회차 활동보고서` : stages.find((s) => s.id === viewing)?.label }}</h2>
      <component :is="STAGE_VIEW[viewing]" :key="viewing + viewKey" :alias="alias" :profile="saved" :items="items" :update="update" embedded
        :round="viewing === 'ACTIVITY' ? saved.currentRound : 0" @saved="afterSave" />

      <div v-if="viewing === 'COMPLETION' && saved.stage === 'COMPLETION'" class="card" data-test="next-term">
        <strong>다음 회기로 연장한다면</strong>
        <p class="muted">완료보고서를 제출하고 승인을 확인한 뒤 눌러 주세요. 시간확대(120분)는 회기마다 멘티가 다시 신청해야 합니다. <router-link :to="{ path: '/extension', query: { mentee: alias } }">시간확대 요건 확인</router-link>에서 신청할 수 있는지 볼 수 있고, 승인되지 않았으면 <router-link :to="menteePath(alias, '/manage')">멘티 설정</router-link>에서 회당 학습시간을 60분으로 바꿔 주세요.</p>
        <label class="field"><span class="name">다음 회기에 들을 강좌 <span class="tag">선택</span></span>
          <input v-model="nextCourse" maxlength="60" :placeholder="`예: ${saved.course || '강좌 이름'} 다음 강좌. 적어 두면 다음 회기 종합계획서의 수강 목표에 넣어 드립니다`" data-test="next-course" />
        </label>
        <div class="row">
          <label class="row">회당 학습시간 <select v-model="termMinutes" class="narrow"><option value="60">60분 (16주)</option><option value="120">120분, 시간확대 (8주)</option></select></label>
          <button type="button" class="primary" @click="startNextTerm">{{ saved.term + 1 }}회기 시작</button>
          <button type="button" @click="update({ archived: !saved.archived }, saved.archived ? '진행 중인 멘티로 되돌렸습니다.' : '종료한 멘티로 보관했습니다.')">{{ saved.archived ? '보관 해제' : '멘토링 종료(보관)' }}</button>
        </div>
      </div>

      <div class="stage-nav row" data-test="stage-nav">
        <button v-if="saved.stage !== stages[0].id" type="button" data-test="prev-stage" @click="go(prevStage(saved))">이전 단계로 되돌리기</button>
        <span class="grow"></span>
        <button v-if="NEXT_LABEL[saved.stage]" type="button" class="primary" data-test="next-stage" @click="go(nextStage(saved))">{{ NEXT_LABEL[saved.stage] }} · 다음 단계</button>
        <span v-else-if="saved.stage === 'ACTIVITY'" class="notice">활동보고서를 저장하면 다음 회차로 넘어갑니다 ({{ totalRounds(saved) }}회차까지).</span>
      </div>

    </template>
    <p v-else-if="loaded" class="card">등록되지 않은 멘티입니다. <router-link to="/mentees">내 멘티</router-link>에서 다시 골라 주세요.</p>
  </div>
</template>
