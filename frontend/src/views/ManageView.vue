<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MenteeHeader from '../components/MenteeHeader.vue'
import { PROFILE_FIELDS, PROFILE_FORM, docStatus, emptyProfile, menteePath, profileFromVault, sessionRows } from '../lib/mentee'
import { todayText, WEEKDAYS } from '../lib/schedule'
import { toast } from '../lib/toast'
import { downloadJson, exportAll, listItems, removeAlias, saveItem } from '../stores/vault'

// 멘티 설정: 단계와 무관한 일을 모았다. 멘티 정보 수정, 지난 보고서 다시 열기, 인계 요약, 종료 표시, 자료 내려받기·삭제.
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
  const data = await exportAll(alias)
  downloadJson(data, `seoullearn-${(saved.value?.name || alias).replace(/\s+/g, '_')}-${todayText()}.json`)
  toast(`${data.items.length}건을 백업 파일로 내려받았습니다.`)
}

async function removeAll() {
  if (!window.confirm(`'${saved.value?.name || alias}'의 모든 자료를 이 브라우저에서 지웁니다. 백업 파일을 내려받지 않았다면 되돌릴 수 없습니다. 지울까요?`)) return
  await removeAlias(alias)
  router.replace('/mentees')
}
</script>

<template>
  <div class="shell">
    <MenteeHeader :alias="alias" :name="saved?.name" title="멘티 설정" />
    <h1>멘티 설정</h1>
    <template v-if="saved">
      <h2>멘티 정보</h2>
      <form class="card" data-test="profile-form" @submit.prevent="saveProfile">
        <p class="muted">이름과 학년은 서버와 AI로 보내지 않고 화면에서만 채웁니다. 학교, 연락처, 가정 사정은 적지 마세요.</p>
        <div class="form-grid">
          <label v-for="f in PROFILE_FIELDS" :key="f.key" class="field" :class="{ wide: f.wide }">
            <span class="name">{{ f.label }}</span>
            <select v-if="f.control === 'select'" v-model="edit[f.key]" :data-profile="f.key">
              <option value="">선택해 주세요</option><option v-for="o in f.options" :key="o" :value="o">{{ f.optionLabels?.[o] || o }}</option>
            </select>
            <input v-else v-model="edit[f.key]" :type="f.control" :placeholder="f.example ? `예: ${f.example}` : ''" :data-profile="f.key" />
            <span v-if="f.help" class="notice">{{ f.help }}</span>
          </label>
          <div class="field wide"><span class="name">정규 일정</span>
            <div v-for="(r, i) in edit.regularSchedule" :key="i" class="row schedule-row">
              <select v-model="r.weekday" class="narrow" :aria-label="`${i + 1}번째 요일`"><option value="">요일</option><option v-for="d in WEEKDAYS" :key="d">{{ d }}</option></select>
              <input v-model="r.startTime" type="time" class="narrow" :aria-label="`${i + 1}번째 시작 시각`" />
              <button v-if="edit.regularSchedule.length > 1" type="button" class="small" :aria-label="`${i + 1}번째 요일 빼기`" @click="edit.regularSchedule.splice(i, 1)">빼기</button>
            </div>
            <button type="button" class="small" @click="edit.regularSchedule.push({ weekday: '', startTime: '' })">요일 추가</button>
            <span class="notice">비워 두면 1회차 일시의 요일과 시각을 씁니다. '오프라인 일정·장소'에서 다음 달 날짜를 채우는 기준입니다.</span>
          </div>
        </div>
        <!-- 회기와 회차는 저장할 때마다 저절로 넘어간다: 어긋났을 때만 고치도록 접어 둔다 -->
        <details data-test="round-fix" @invalid.capture="$event.currentTarget.open = true">
          <summary>회기나 회차 번호가 맞지 않을 때</summary>
          <div class="form-grid gap-top">
            <label class="field"><span class="name">현재 회기</span><input v-model.number="edit.term" type="number" min="1" data-profile="term" /></label>
            <label class="field"><span class="name">현재 회차</span><input v-model.number="edit.currentRound" type="number" min="1" :max="rows.length" data-profile="currentRound" /></label>
          </div>
        </details>
        <div class="row gap-top"><button class="primary" data-test="save-profile">멘티 정보 저장</button></div>
      </form>

      <h2>활동보고서 <span class="tag">{{ status.reports }} / {{ rows.length }}</span></h2>
      <div class="card">
        <div class="sessions" data-test="sessions">
          <router-link v-for="r in rows" :key="r.no" :to="to(`/report/${r.no}`)" class="session" :class="{ done: r.saved, now: !r.saved && r.no === saved.currentRound }" :data-session="r.no">
            <strong>{{ r.no }}회차</strong>
            <span>{{ r.saved ? `${r.status && r.status !== '출석' ? r.status : r.date} · 저장함` : r.no === saved.currentRound ? '지금 쓸 회차' : `예정 ${r.expected || '-'}` }}</span>
          </router-link>
        </div>
        <p class="notice">'저장함'이 붙은 회차는 저장한 보고서가 있습니다. 누르면 다시 열어 고치거나 복사할 수 있습니다.</p>
        <div v-if="saved.mode === '오프라인'" class="row gap-top">
          <router-link :to="{ path: '/schedule', query: { mentee: alias } }" class="linkbutton small">오프라인 일정·장소</router-link>
        </div>
      </div>

      <h2>멘토 교체</h2>
      <div class="card row">
        <span class="notice grow">멘토가 바뀔 때 다음 멘토에게 넘길 인계 요약을 만듭니다. 출석 패턴, 과제 수행, 학습 태도, 수강 진도 네 가지만 담습니다.</span>
        <router-link :to="to('/handover')" class="linkbutton" data-test="doc-handover">인계 요약 만들기{{ status.handover_summary ? ` (저장함 ${status.handover_summary})` : '' }}</router-link>
      </div>

      <h2>자료 관리</h2>
      <div class="card">
        <p class="muted">이 멘티의 자료는 이 브라우저에만 있습니다. 브라우저 데이터를 지우거나 다른 기기에서 쓰려면 백업 파일로 내려받은 뒤 <router-link to="/vault">백업·복원</router-link>에서 복원해 주세요.</p>
        <div class="row">
          <button type="button" @click="exportFile">이 멘티 자료 내려받기</button>
          <button type="button" data-test="archive" @click="update({ archived: !saved.archived }, saved.archived ? '진행 중인 멘티로 되돌렸습니다.' : '종료한 멘티로 표시했습니다. 자료는 그대로 남습니다.')">{{ saved.archived ? '진행 중으로 되돌리기' : '종료한 멘티로 표시' }}</button>
          <span class="grow"></span>
          <button type="button" class="danger" data-test="remove-all" @click="removeAll">이 멘티 자료 모두 지우기</button>
        </div>
      </div>
    </template>
    <p v-else-if="loaded" class="card">등록되지 않은 멘티입니다. <router-link to="/mentees">내 멘티</router-link>에서 다시 골라 주세요.</p>
  </div>
</template>
