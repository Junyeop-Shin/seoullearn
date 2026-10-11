<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { login } from '../stores/auth'

const router = useRouter()
const mode = ref('login')
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    if (mode.value === 'signup') await api.signup(username.value, password.value)
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
      <form @submit.prevent="submit">
        <h2>{{ mode === 'signup' ? '멘토 계정 만들기' : '로그인' }}</h2>
        <label class="field"><span class="name">아이디</span>
          <input v-model="username" autocomplete="username" required />
          <span v-if="mode === 'signup'" class="notice">영문 소문자·숫자·밑줄 4~20자로 적어 주세요. 실명이나 학교명은 쓰지 마세요.</span>
        </label>
        <label class="field"><span class="name">비밀번호</span>
          <input v-model="password" type="password" :autocomplete="mode === 'signup' ? 'new-password' : 'current-password'" required />
          <span v-if="mode === 'signup'" class="notice">8자 이상</span>
        </label>
        <div v-if="error" class="box error">{{ error }}</div>
        <button class="primary wide" :disabled="busy">{{ mode === 'signup' ? '가입하고 시작하기' : '로그인' }}</button>
        <p class="muted switch">
          {{ mode === 'signup' ? '이미 계정이 있나요?' : '처음이신가요?' }}
          <button type="button" class="small" @click="mode = mode === 'signup' ? 'login' : 'signup'; error = ''">
            {{ mode === 'signup' ? '로그인하기' : '멘토 계정 만들기' }}
          </button>
        </p>
      </form>
    </section>
  </div>
</template>
