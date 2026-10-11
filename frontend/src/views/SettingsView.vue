<script setup>
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { auth, withdraw } from '../stores/auth'
import { MENTOR_TYPES, loadSettings, saveSettings } from '../stores/settings'

// 멘토 설정: 처음 한 번 적어 두면 사전 연락 문구와 보고서의 멘토 칸에 자동으로 채워진다. 이 브라우저에만 저장한다.
const s = reactive(loadSettings())
const status = ref('')
watch(s, () => { status.value = '' })   // 고친 뒤에는 '저장했습니다'를 남겨 두지 않는다

function save() {
  saveSettings({ ...s })
  status.value = '저장했습니다.'
}

// 회원 탈퇴(동의 철회): 서버의 계정을 바로 지운다. 멘티 자료와 멘토 설정은 이 브라우저에 있어 따로 지워야 한다
const router = useRouter()
const error = ref('')
async function leave() {
  if (!window.confirm('탈퇴하면 서버의 계정 정보(아이디, 비밀번호, 동의 기록)를 바로 지우고 되돌릴 수 없습니다. 이 브라우저에 저장한 멘티 자료와 멘토 설정은 지워지지 않으니, 함께 지우려면 취소하고 백업·복원 화면에서 먼저 지워 주세요. 탈퇴할까요?')) return
  try {
    await withdraw()
    router.replace('/login')
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <h1>멘토 설정</h1>
    <p class="muted">멘토링 문서를 쓸 때 이 정보를 자동으로 넣어 드립니다. 이 브라우저에만 저장하고 서버와 AI로 보내지 않습니다.</p>
    <form class="card" @submit.prevent="save">
      <div class="form-grid">
        <label class="field"><span class="name">이름</span><input v-model="s.name" maxlength="30" data-set="name" /></label>
        <label class="field"><span class="name">연락처</span><input v-model="s.phone" type="tel" inputmode="tel" autocomplete="tel" placeholder="010-0000-0000" maxlength="20" data-set="phone" />
          <span class="notice">사전 연락 문자에 회신받을 번호로 들어갑니다.</span></label>
        <label class="field"><span class="name">멘토링 유형</span>
          <select v-model="s.mentoringType" data-set="mentoringType"><option value="">선택해 주세요</option><option v-for="t in MENTOR_TYPES" :key="t">{{ t }}</option></select></label>
        <span></span>
        <label class="field"><span class="name">대학교</span><input v-model="s.university" maxlength="30" data-set="university" /></label>
        <label class="field"><span class="name">전공</span><input v-model="s.major" maxlength="30" data-set="major" /></label>
      </div>
      <div class="row"><button class="primary" data-test="save-settings">저장</button><span class="ok" role="status" data-test="settings-status">{{ status }}</span>
        <router-link v-if="status" to="/mentees" class="linkbutton small">내 멘티로 가기</router-link></div>
    </form>

    <h2>계정과 개인정보</h2>
    <div class="card" data-test="account">
      <p class="flush">서버에는 아이디({{ auth.user?.username }}), 암호화한 비밀번호, 전자우편 주소, 가입할 때의 동의 기록만 있습니다. 자세한 내용은 <router-link to="/privacy">개인정보 처리방침</router-link>에서 볼 수 있습니다.</p>
      <div v-if="error" class="box error">{{ error }}</div>
      <div v-if="auth.user?.role !== 'ADMIN'" class="row gap-top">
        <button type="button" class="danger" data-test="withdraw" @click="leave">회원 탈퇴</button>
        <span class="notice">탈퇴하면 계정 정보를 바로 지웁니다. 멘티 자료는 이 브라우저에 남습니다.</span>
      </div>
    </div>
  </div>
</template>
