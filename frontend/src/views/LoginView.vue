<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import ConsentStep from '../components/ConsentStep.vue'
import { login } from '../stores/auth'

const router = useRouter()
const token = String(useRoute().query.reset || '')   // 메일로 받은 재설정 주소로 들어왔다
const mode = ref(token ? 'reset' : 'login')   // login → (멘토 계정 만들기) consent → signup. 비밀번호 찾기: forgot → (메일) → reset
const TITLE = { login: '로그인', signup: '멘토 계정 만들기', forgot: '비밀번호 찾기', reset: '새 비밀번호 정하기' }
const BUTTON = { login: '로그인', signup: '가입하고 시작하기', forgot: '재설정 메일 받기', reset: '비밀번호 바꾸기' }
const email = ref('')
const done = ref('')
const consent = ref(null)   // 가입 전 동의 {version, items}
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

function go(to) {
  mode.value = to
  error.value = ''
  done.value = ''
}

async function submit() {
  error.value = ''
  done.value = ''
  busy.value = true
  try {
    if (mode.value === 'forgot') {
      await api.resetRequest(username.value, email.value)
      // 아이디와 전자우편이 맞는지는 알려 주지 않는다
      return (done.value = '아이디와 전자우편이 가입한 정보와 같으면 재설정 주소를 메일로 보냈습니다. 30분 안에 열어 주세요. 메일이 오지 않으면 스팸함을 확인하거나 다시 시도해 주세요.')
    }
    if (mode.value === 'reset') {
      await api.resetPassword(token, password.value)
      password.value = ''
      mode.value = 'login'
      router.replace('/login')
      return (done.value = '비밀번호를 바꿨습니다. 새 비밀번호로 로그인해 주세요.')
    }
    if (mode.value === 'signup') await api.signup(username.value, password.value, email.value, consent.value)
    await login(username.value, password.value)
    // 가입 직후에는 멘토 설정(이름, 연락처, 멘토링 유형)부터 적게 한다
    router.replace(mode.value === 'signup' ? '/settings' : '/mentees')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="auth">
    <section class="pitch">
      <h1>서울런 멘토 도우미</h1>
      <p>매뉴얼을 뒤지고 보고서와 계획서를 옮겨 적는 시간을 줄여, 멘티와 보내는 시간에 더 집중할 수 있게 돕습니다.</p>
      <ul>
        <li>활동가이드와 공지에서 근거와 함께 답을 찾아 드립니다.</li>
        <li>활동보고서, 종합계획서, 완료보고서의 초안을 만들어 드립니다.</li>
        <li>멘티 정보와 초안은 이 브라우저에만 보관하고, 이름은 서버와 AI로 보내지 않습니다.</li>
      </ul>
    </section>
    <section class="panel">
      <ConsentStep v-if="mode === 'consent'" @agreed="consent = $event; mode = 'signup'" @cancel="mode = 'login'" />
      <form v-else @submit.prevent="submit">
        <h2>{{ TITLE[mode] }}</h2>
        <p v-if="mode === 'forgot'" class="muted">가입할 때 적은 아이디와 전자우편을 적어 주세요. 새 비밀번호를 정할 주소를 메일로 보내 드립니다.</p>
        <p v-if="mode === 'signup'" class="notice" data-test="consent-done">가입 전 동의를 마쳤습니다. <button type="button" class="small" @click="mode = 'consent'">동의 내용 다시 보기</button></p>
        <label v-if="mode !== 'reset'" class="field"><span class="name">아이디</span>
          <input v-model="username" autocomplete="username" required :pattern="mode === 'signup' ? '[a-z0-9_]{4,20}' : undefined" :title="mode === 'signup' ? '영문 소문자·숫자·밑줄 4~20자' : undefined" />
          <span v-if="mode === 'signup'" class="notice">영문 소문자·숫자·밑줄 4~20자로 적어 주세요. 실명이나 학교명은 쓰지 마세요.</span>
        </label>
        <label v-if="mode === 'signup' || mode === 'forgot'" class="field"><span class="name">전자우편</span>
          <input v-model="email" type="email" autocomplete="email" required maxlength="100" data-test="email" />
          <span v-if="mode === 'signup'" class="notice">비밀번호를 잊었을 때 재설정 주소를 받는 데만 씁니다.</span>
        </label>
        <label v-if="mode !== 'forgot'" class="field"><span class="name">{{ mode === 'reset' ? '새 비밀번호' : '비밀번호' }}</span>
          <input v-model="password" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" required :minlength="mode === 'login' ? undefined : 8" />
          <span v-if="mode !== 'login'" class="notice">8자 이상으로 적어 주세요.</span>
        </label>
        <div v-if="done" class="box ask" role="status" data-test="auth-done">{{ done }}</div>
        <div v-if="error" class="box error" role="alert">{{ error }}</div>
        <button class="primary wide" :disabled="busy">{{ BUTTON[mode] }}</button>
        <p class="muted switch">
          {{ mode === 'login' ? '처음이신가요?' : '이미 계정이 있나요?' }}
          <button type="button" class="small" @click="go(mode === 'login' ? 'consent' : 'login')">
            {{ mode === 'login' ? '멘토 계정 만들기' : '로그인하기' }}
          </button>
          <button v-if="mode === 'login'" type="button" class="small" data-test="forgot" @click="go('forgot')">비밀번호 찾기</button>
        </p>
        <p class="muted switch"><router-link to="/privacy">개인정보 처리방침</router-link></p>
      </form>
    </section>
  </div>
</template>
