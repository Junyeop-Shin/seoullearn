<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MenteeHeader from '../components/MenteeHeader.vue'
import { KEEP_AFTER_TERM, PROFILE_FIELDS, PROFILE_FORM, docStatus, emptyProfile, menteePath, nextStep, profileFromVault, sessionRows, setCurrentAlias } from '../lib/mentee'
import { toast } from '../lib/toast'
import { downloadJson, exportAlias, listItems, removeAlias, saveItem } from '../stores/vault'

// 멘티 작업 공간: 한 멘티의 기본 정보와 회기 문서(계획서, 회차별 보고서, 완료보고서, 인계 요약)를 한 화면에서 다룬다.
const route = useRoute()
const router = useRouter()
const alias = String(route.params.alias)
const items = ref([])
const profile = reactive(emptyProfile())
const profileId = ref(undefined)
const editing = ref(false)
const saved = computed(() => profileFromVault(items.value))
const rows = computed(() => sessionRows(items.value, saved.value))
const status = computed(() => docStatus(items.value))
const next = computed(() => nextStep(items.value, saved.value))
const to = (rest) => menteePath(alias, rest)

async function refresh() {
  items.value = await listItems(alias)
  const p = saved.value
  Object.assign(profile, emptyProfile(), p || {})
  delete profile._id
  profileId.value = p?._id
  if (!p?.subject) editing.value = true
}

onMounted(async () => {
  setCurrentAlias(alias)
  await refresh()
})

async function saveProfile() {
  await saveItem({ id: profileId.value, alias, formId: PROFILE_FORM, title: '멘티 정보', draft: { ...profile } })
  toast('기본 정보를 저장했습니다.')
  editing.value = false
  await refresh()
}

async function exportFile() {
  const data = await exportAlias(alias)
  downloadJson(data, `seoullearn-${alias.replace(/\s+/g, '_')}-${data.exportedAt.slice(0, 10)}.json`)
  toast(`${data.items.length}건을 파일로 내보냈습니다.`)
}

async function closeTerm() {
  if (!window.confirm('회기 정리: 종합계획서와 회차별 활동보고서를 이 브라우저에서 지우고, 기본 정보·완료보고서·인계 요약만 남깁니다. 되돌릴 수 없습니다. 계속할까요?')) return
  const n = await removeAlias(alias, KEEP_AFTER_TERM)
  toast(`${n}건을 지웠습니다.`)
  await refresh()
}

async function removeAll() {
  if (!window.confirm(`'${alias}'의 모든 자료를 이 브라우저에서 지웁니다. 되돌릴 수 없습니다. 계속할까요?`)) return
  await removeAlias(alias)
  router.replace('/mentees')
}
</script>

<template>
  <div class="shell">
    <MenteeHeader :alias="alias" />
    <h1>{{ alias }}</h1>
    <p class="box ask" data-test="next-step">{{ next }}</p>

    <h2>기본 정보</h2>
    <div v-if="!editing" class="card" data-test="profile-view">
      <div class="facts">
        <template v-for="f in PROFILE_FIELDS" :key="f.key">
          <div v-if="saved?.[f.key]"><span>{{ f.label }}</span>{{ f.key === 'start_datetime' ? saved[f.key].replace('T', ' ') : saved[f.key] }}</div>
        </template>
      </div>
      <button type="button" class="small" style="margin-top: 10px" @click="editing = true">기본 정보 수정</button>
    </div>
    <form v-else class="card" @submit.prevent="saveProfile">
      <p class="muted">한 번 적어 두면 보고서와 계획서에 자동으로 채워집니다. 이름, 학년, 학교, 연락처, 가정 사정은 적지 마세요.</p>
      <div class="form-grid">
        <label v-for="f in PROFILE_FIELDS" :key="f.key" class="field" :class="{ wide: f.wide }">
          <span class="name">{{ f.label }}</span>
          <select v-if="f.control === 'select'" v-model="profile[f.key]" :data-profile="f.key">
            <option value="">선택해 주세요</option><option v-for="o in f.options" :key="o" :value="o">{{ o }}</option>
          </select>
          <textarea v-else-if="f.control === 'textarea'" v-model="profile[f.key]" rows="2" :data-profile="f.key"></textarea>
          <input v-else v-model="profile[f.key]" :type="f.control" :placeholder="f.example ? `예: ${f.example}` : ''" :data-profile="f.key" />
          <span v-if="f.help" class="notice">{{ f.help }}</span>
        </label>
      </div>
      <div class="row"><button class="primary">기본 정보 저장</button><button v-if="saved?.subject" type="button" @click="editing = false">취소</button></div>
    </form>

    <h2>회기를 시작할 때</h2>
    <div class="card doc-list">
      <router-link :to="{ path: '/pre-contact', query: { mode: saved?.mode || undefined } }" class="doc"><strong>사전 연락 문자</strong><span class="muted">매칭 직후 보낼 문자 초안</span></router-link>
      <router-link :to="to('/plan')" class="doc" data-test="doc-plan"><strong>종합계획서 ①·②</strong>
        <span :class="status.plan_initial ? 'ok' : 'muted'">{{ status.plan_initial ? `① 저장함 (${status.plan_initial})` : '① 아직 없음' }}{{ status.plan_file ? ` · ② 저장함 (${status.plan_file})` : ' · ② 아직 없음' }}</span>
      </router-link>
      <router-link v-if="saved?.mode === '오프라인'" to="/ieumdan" class="doc"><strong>이음단 장소·일정 요청</strong><span class="muted">요청 메시지 만들기</span></router-link>
    </div>

    <h2>회차별 활동보고서 <span class="tag">{{ status.reports }} / {{ rows.length }}</span></h2>
    <div class="card">
      <div class="sessions" data-test="sessions">
        <router-link v-for="r in rows" :key="r.no" :to="to(`/report/${r.no}`)" class="session" :class="{ done: r.saved }" :data-session="r.no">
          <strong>{{ r.no }}회차</strong>
          <span>{{ r.saved ? (r.status && r.status !== '출석' ? r.status : r.date || '저장함') : r.expected || '미작성' }}</span>
        </router-link>
      </div>
      <p class="notice">색이 채워진 회차는 저장한 초안이 있습니다. 누르면 다시 열어 고칠 수 있습니다. 날짜는 1회차 일시로 계산한 예상 날짜입니다.</p>
    </div>

    <h2>회기를 마칠 때</h2>
    <div class="card doc-list">
      <router-link :to="to('/completion')" class="doc" data-test="doc-completion"><strong>완료보고서</strong>
        <span :class="status.completion_report ? 'ok' : 'muted'">{{ status.completion_report ? `저장함 (${status.completion_report})` : `활동보고서 ${status.reports}건으로 작성` }}</span>
      </router-link>
      <router-link :to="to('/handover')" class="doc" data-test="doc-handover"><strong>인계 요약</strong>
        <span :class="status.handover_summary ? 'ok' : 'muted'">{{ status.handover_summary ? `저장함 (${status.handover_summary})` : '멘토가 바뀔 때 다음 멘토에게 넘길 내용' }}</span>
      </router-link>
    </div>

    <h2>자료 관리</h2>
    <div class="card">
      <p class="muted">이 멘티의 자료는 이 브라우저에만 있습니다. 브라우저 데이터를 지우거나 다른 기기에서 쓰려면 파일로 내보낸 뒤, 설정의 백업·복원에서 가져오세요.</p>
      <div class="row">
        <button type="button" @click="exportFile">이 멘티 자료 내보내기</button>
        <button type="button" @click="closeTerm">회기 정리</button>
        <span style="flex: 1"></span>
        <button type="button" class="danger" @click="removeAll">이 멘티 자료 모두 지우기</button>
      </div>
      <p class="notice">회기 정리는 종합계획서와 회차별 활동보고서를 지우고 기본 정보, 완료보고서, 인계 요약만 남깁니다. 제출한 보고서는 서울런 플랫폼에 남아 있습니다.</p>
    </div>
  </div>
</template>
