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
    router.replace('/')
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
      <p>매뉴얼을 뒤지고 보고서 문장을 다듬는 시간을 줄여, 멘티와 보내는 시간에 더 집중할 수 있게 돕습니다.</p>
      <ul>
        <li>활동가이드와 공지에서 근거와 함께 답을 찾아 드립니다.</li>
        <li>활동보고서, 종합계획서, 완료보고서의 초안을 만들어 드립니다.</li>
        <li>멘티의 이름·연락처·학교는 입력받지 않고, 초안은 이 브라우저에만 보관합니다.</li>
      </ul>
    </section>
    <section class="panel">
      <form @submit.prevent="submit">
        <h2 style="margin-top: 0; font-size: 1.3rem">{{ mode === 'signup' ? '멘토 계정 만들기' : '로그인' }}</h2>
        <label class="field"><span class="name">아이디</span>
          <input v-model="username" autocomplete="username" required />
          <span v-if="mode === 'signup'" class="notice">영문 소문자, 숫자, 밑줄로 4~20자. 실명이나 학교명은 쓰지 마세요.</span>
        </label>
        <label class="field"><span class="name">비밀번호</span>
          <input v-model="password" type="password" :autocomplete="mode === 'signup' ? 'new-password' : 'current-password'" required />
          <span v-if="mode === 'signup'" class="notice">8자 이상</span>
        </label>
        <div v-if="error" class="box error">{{ error }}</div>
        <button class="primary" style="width: 100%; padding: 12px" :disabled="busy">{{ mode === 'signup' ? '가입하고 시작하기' : '로그인' }}</button>
        <p class="muted" style="text-align: center; margin-top: 16px">
          {{ mode === 'signup' ? '이미 계정이 있나요?' : '처음이신가요?' }}
          <button type="button" class="small" style="margin-left: 6px" @click="mode = mode === 'signup' ? 'login' : 'signup'">
            {{ mode === 'signup' ? '로그인하기' : '멘토 계정 만들기' }}
          </button>
        </p>
      </form>
    </section>
  </div>
</template>
