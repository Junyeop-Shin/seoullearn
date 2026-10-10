<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MenteeHeader from '../components/MenteeHeader.vue'
import { PROFILE_FIELDS, PROFILE_FORM, docStatus, emptyProfile, menteePath, profileFromVault, sessionRows } from '../lib/mentee'
import { WEEKDAYS } from '../lib/schedule'
import { toast } from '../lib/toast'
import { downloadJson, exportAlias, listItems, removeAlias, saveItem } from '../stores/vault'

// 멘티 설정: 단계와 무관한 일을 모았다. 멘티 정보 수정, 지난 보고서 다시 열기, 인계 요약, 보관, 자료 내보내기·삭제.
const route = useRoute()
const router = useRouter()
const alias = String(route.params.alias)
const items = ref([])
const loaded = ref(false)
const edit = reactive(emptyProfile())
const saved = computed(() => profileFromVault(items.value))
const rows = computed(() => sessionRows(items.value, saved.value))
const status = computed(() => docStatus(items.value))
const to = (rest) => menteePath(alias, rest)

async function refresh() {
  items.value = await listItems(alias)
  loaded.value = true
  if (!saved.value) return
  Object.assign(edit, emptyProfile(), saved.value)
  if (!edit.regularSchedule.length) edit.regularSchedule = [{ weekday: '', startTime: '' }]
}
onMounted(refresh)

async function update(patch, message) {
  const { _id, ...rest } = saved.value
  await saveItem({ id: _id, alias, formId: PROFILE_FORM, title: '멘티 정보', draft: { ...rest, ...patch } })
  toast(message)
  await refresh()
}

async function saveProfile() {
  const p = { ...edit, regularSchedule: edit.regularSchedule.filter((r) => r.weekday) }
  delete p._id
  await update(p, '멘티 정보를 저장했습니다.')
}

async function exportFile() {
  const data = await exportAlias(alias)
  downloadJson(data, `seoullearn-${alias.replace(/\s+/g, '_')}-${data.exportedAt.slice(0, 10)}.json`)
  toast(`${data.items.length}건을 파일로 내보냈습니다.`)
}

async function removeAll() {
  if (!window.confirm(`'${alias}'의 모든 자료를 이 브라우저에서 지웁니다. 되돌릴 수 없습니다. 계속할까요?`)) return
  await removeAlias(alias)
  router.replace('/mentees')
}
</script>

<template>
  <div class="shell">
    <MenteeHeader :alias="alias" title="멘티 설정" />
    <h1>멘티 설정</h1>
    <template v-if="saved">
      <h2>멘티 정보</h2>
      <form class="card" data-test="profile-form" @submit.prevent="saveProfile">
        <p class="muted">이 브라우저에만 저장됩니다. 이름과 학년은 서버와 AI로 보내지 않고 화면에서만 채웁니다. 학교, 연락처, 가정 사정은 적지 마세요.</p>
        <div class="form-grid">
          <label v-for="f in PROFILE_FIELDS" :key="f.key" class="field" :class="{ wide: f.wide }">
            <span class="name">{{ f.label }}</span>
            <select v-if="f.control === 'select'" v-model="edit[f.key]" :data-profile="f.key">
              <option value="">선택해 주세요</option><option v-for="o in f.options" :key="o" :value="o">{{ o }}</option>
            </select>
            <textarea v-else-if="f.control === 'textarea'" v-model="edit[f.key]" rows="2" :data-profile="f.key"></textarea>
            <input v-else v-model="edit[f.key]" :type="f.control" :placeholder="f.example ? `예: ${f.example}` : ''" :data-profile="f.key" />
            <span v-if="f.help" class="notice">{{ f.help }}</span>
          </label>
          <div class="field wide"><span class="name">정규 일정</span>
            <div v-for="(r, i) in edit.regularSchedule" :key="i" class="row" style="margin-bottom: 6px">
              <select v-model="r.weekday" style="width: 120px" aria-label="요일"><option value="">요일</option><option v-for="d in WEEKDAYS" :key="d">{{ d }}</option></select>
              <input v-model="r.startTime" type="time" style="width: 140px" aria-label="시작 시각" />
              <button v-if="edit.regularSchedule.length > 1" type="button" class="small" @click="edit.regularSchedule.splice(i, 1)">삭제</button>
            </div>
            <button type="button" class="small" @click="edit.regularSchedule.push({ weekday: '', startTime: '' })">요일 추가</button>
            <span class="notice">비워 두면 1회차 일시의 요일과 시각을 씁니다. 오프라인 일정·장소 화면에서 다음달 날짜를 채우는 기준입니다.</span>
          </div>
          <label class="field"><span class="name">현재 회기</span><input v-model.number="edit.term" type="number" min="1" data-profile="term" /></label>
          <label class="field"><span class="name">현재 회차</span><input v-model.number="edit.currentRound" type="number" min="1" data-profile="currentRound" /></label>
        </div>
        <button class="primary" data-test="save-profile">멘티 정보 저장</button>
      </form>

      <h2>지난 보고서 <span class="tag">{{ status.reports }} / {{ rows.length }}</span></h2>
      <div class="card">
        <div class="sessions" data-test="sessions">
          <router-link v-for="r in rows" :key="r.no" :to="to(`/report/${r.no}`)" class="session" :class="{ done: r.saved }" :data-session="r.no">
            <strong>{{ r.no }}회차</strong>
            <span>{{ r.saved ? (r.status && r.status !== '출석' ? r.status : r.date || '저장함') : r.expected || '미작성' }}</span>
          </router-link>
        </div>
        <p class="notice">색이 채워진 회차는 저장한 보고서가 있습니다. 누르면 다시 열어 고치거나 복사할 수 있습니다.</p>
        <div class="row" style="margin-top: 8px">
          <router-link :to="to('/handover')"><button type="button" class="small" data-test="doc-handover">멘토 교체 인계 요약 만들기{{ status.handover_summary ? ` (저장함 ${status.handover_summary})` : '' }}</button></router-link>
          <router-link v-if="saved.mode === '오프라인'" to="/ieumdan"><button type="button" class="small">이음단 일정·장소 변경 요청</button></router-link>
        </div>
      </div>

      <h2>자료 관리</h2>
      <div class="card">
        <p class="muted">이 멘티의 자료는 이 브라우저에만 있습니다. 브라우저 데이터를 지우거나 다른 기기에서 쓰려면 파일로 내보낸 뒤, 백업·복원에서 가져오세요.</p>
        <div class="row">
          <button type="button" @click="exportFile">이 멘티 자료 내보내기</button>
          <button type="button" data-test="archive" @click="update({ archived: !saved.archived }, saved.archived ? '진행 중인 멘티로 되돌렸습니다.' : '종료한 멘티로 보관했습니다.')">{{ saved.archived ? '보관 해제' : '멘티 보관(종료)' }}</button>
          <span style="flex: 1"></span>
          <button type="button" class="danger" data-test="remove-all" @click="removeAll">이 멘티 자료 모두 지우기</button>
        </div>
      </div>
    </template>
    <p v-else-if="loaded" class="card">등록되지 않은 멘티입니다. <router-link to="/mentees">내 멘티</router-link>에서 다시 골라 주세요.</p>
  </div>
</template>
