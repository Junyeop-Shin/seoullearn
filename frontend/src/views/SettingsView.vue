<script setup>
import { reactive, ref, watch } from 'vue'
import { MENTOR_TYPES, loadSettings, saveSettings } from '../stores/settings'

// 멘토 설정: 처음 한 번 적어 두면 사전 연락 문구와 보고서의 멘토 칸에 자동으로 채워진다. 이 브라우저에만 저장한다.
const s = reactive(loadSettings())
const status = ref('')
watch(s, () => { status.value = '' })   // 고친 뒤에는 '저장했습니다'를 남겨 두지 않는다

function save() {
  saveSettings({ ...s })
  status.value = '저장했습니다.'
}
</script>

<template>
  <div class="shell">
    <h1>멘토 설정</h1>
    <p class="muted">문서의 멘토 칸과 사전 연락 문자를 채우는 데 씁니다. 이 브라우저에만 저장하고 서버와 AI로 보내지 않습니다.</p>
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
      <div class="row"><button class="primary" data-test="save-settings">저장</button><span class="ok" data-test="settings-status">{{ status }}</span>
        <router-link v-if="status" to="/mentees" class="linkbutton small">내 멘티로 가기</router-link></div>
    </form>
  </div>
</template>
