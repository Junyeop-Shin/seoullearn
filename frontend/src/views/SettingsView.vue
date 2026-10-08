<script setup>
import { ref } from 'vue'
import { loadSettings, saveSettings } from '../stores/settings'

const url = ref(loadSettings().ieumdanChatUrl)
const status = ref('')

function save() {
  status.value = saveSettings({ ieumdanChatUrl: url.value })
    ? '저장했습니다.'
    : '카카오톡 오픈채팅 주소(https://open.kakao.com/...)만 저장할 수 있습니다.'
}
</script>

<template>
  <div class="shell">
    <h1>설정</h1>
    <form class="card" @submit.prevent="save">
      <label class="field">
        <span class="name">소속 자치구 이음단 오픈채팅 주소</span>
        <input v-model="url" placeholder="https://open.kakao.com/o/..." maxlength="200" />
        <span class="notice">이 브라우저에만 저장됩니다. 문의처가 이음단인 답변에 바로가기 버튼을 만드는 데만 쓰고, 서버에는 저장하지 않습니다.</span>
      </label>
      <div class="row"><button class="primary">저장</button><span>{{ status }}</span></div>
    </form>
  </div>
</template>
