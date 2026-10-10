<script setup>
import { onMounted, reactive, ref } from 'vue'
import { DISTRICTS, profileFromVault } from '../lib/mentee'
import { COURSE_ALIAS } from '../lib/reports'
import { MENTOR_TYPES, loadSettings, saveSettings } from '../stores/settings'
import { listAliases, listItems } from '../stores/vault'

// 멘토 설정: 처음 한 번 적어 두면 사전 연락 문구와 보고서의 멘토 칸에 자동으로 채워진다. 이 브라우저에만 저장한다.
const s = reactive(loadSettings())
const status = ref('')
const districts = ref([])   // 내 멘티가 있는 자치구 (이음단 채널 주소를 적을 칸)
const more = ref('')

onMounted(async () => {
  const set = new Set(Object.keys(s.ieumdanChats))
  for (const a of (await listAliases()).filter((x) => x !== COURSE_ALIAS)) {
    const d = profileFromVault(await listItems(a))?.district
    if (d) set.add(d)
  }
  districts.value = [...set].sort((a, b) => a.localeCompare(b, 'ko'))
})

function addDistrict() {
  if (more.value && !districts.value.includes(more.value)) districts.value.push(more.value)
  more.value = ''
}

function save() {
  status.value = saveSettings({ ...s }) ? '저장했습니다.' : '이음단 주소는 카카오톡 오픈채팅 주소(https://open.kakao.com/...)만 저장할 수 있습니다.'
}
</script>

<template>
  <div class="shell">
    <h1>멘토 설정</h1>
    <p class="muted">처음 한 번만 적어 두면 됩니다. 이 브라우저에만 저장되고 서버와 AI로는 보내지 않습니다. 초안의 [멘토명] 같은 자리를 화면에서 채우는 데만 씁니다.</p>
    <form class="card" @submit.prevent="save">
      <div class="form-grid">
        <label class="field"><span class="name">이름</span><input v-model="s.name" maxlength="30" data-set="name" /></label>
        <label class="field"><span class="name">연락처</span><input v-model="s.phone" placeholder="010-0000-0000" maxlength="20" data-set="phone" />
          <span class="notice">사전 연락 문자에 회신받을 번호로 들어갑니다.</span></label>
        <label class="field"><span class="name">멘토링 유형</span>
          <select v-model="s.mentoringType" data-set="mentoringType"><option value="">선택해 주세요</option><option v-for="t in MENTOR_TYPES" :key="t">{{ t }}</option></select>
          <span class="notice">종합계획서①의 기본값입니다.</span></label>
        <span></span>
        <label class="field"><span class="name">대학교</span><input v-model="s.university" maxlength="30" data-set="university" /></label>
        <label class="field"><span class="name">전공</span><input v-model="s.major" maxlength="30" data-set="major" />
          <span class="notice">종합계획서②와 활동보고서의 '멘토(대학교·전공)' 칸에 씁니다.</span></label>
      </div>
      <section class="form-section">
        <h3>이음단 카카오톡 채널</h3>
        <label v-for="d in districts" :key="d" class="field"><span class="name">{{ d }} 이음단 오픈채팅 주소</span>
          <input v-model="s.ieumdanChats[d]" placeholder="https://open.kakao.com/o/..." maxlength="200" :data-chat="d" /></label>
        <div class="row">
          <select v-model="more" style="width: 180px" aria-label="자치구"><option value="">자치구 추가</option><option v-for="d in DISTRICTS.filter((x) => !districts.includes(x))" :key="d">{{ d }}</option></select>
          <button type="button" class="small" :disabled="!more" @click="addDistrict">추가</button>
        </div>
        <label class="field"><span class="name">기본 주소 (자치구별 주소가 없을 때)</span>
          <input v-model="s.ieumdanChatUrl" placeholder="https://open.kakao.com/o/..." maxlength="200" data-set="ieumdanChatUrl" />
          <span class="notice">문의처가 이음단인 답변과 장소·일정 문구에 채널 바로가기 버튼을 만드는 데만 씁니다.</span></label>
      </section>
      <div class="row"><button class="primary" data-test="save-settings">저장</button><span data-test="settings-status">{{ status }}</span></div>
    </form>
  </div>
</template>
