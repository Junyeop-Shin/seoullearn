<script setup>
import { reactive, ref } from 'vue'
import { api } from '../api/client'
import AliasInput from '../components/AliasInput.vue'
import { copyText } from '../lib/copy'
import { saveItem } from '../stores/vault'

// 사전 연락: 확인할 질문 목록과 문자 초안. 받은 답변은 보관함에 두었다가 종합계획서①에 쓴다.
const mode = ref('온라인')
const callTime = ref('')
const res = ref(null)
const answers = reactive({})
const alias = ref('')
const status = ref('')
const error = ref('')
const copied = ref(-1)

async function build() {
  error.value = ''
  try {
    res.value = await api.preContact(mode.value, callTime.value)
  } catch (e) {
    error.value = e.message
  }
}

async function copy(text, i) {
  copied.value = (await copyText(text)) ? i : -1
}

async function save() {
  try {
    await saveItem({ alias: alias.value, formId: 'pre_contact', title: '사전 연락 답변', inputs: { mode: mode.value }, draft: { ...answers } })
    status.value = '보관함에 저장했습니다. 종합계획서① 화면에서 불러올 수 있습니다.'
  } catch (e) {
    status.value = e.message
  }
}
</script>

<template>
  <div class="shell">
    <h1>사전 연락</h1>
    <form class="card" @submit.prevent="build">
      <label class="field"><span class="name">멘토링 유형</span>
        <select v-model="mode"><option>온라인</option><option>오프라인</option></select>
      </label>
      <label class="field"><span class="name">전화할 시각 (선택)</span><input v-model="callTime" placeholder="예: 19시" maxlength="20" /></label>
      <button class="primary">질문지와 문자 초안 만들기</button>
    </form>
    <div v-if="error" class="box error">{{ error }}</div>
    <template v-if="res">
      <h2>문자 초안 ({{ res.sms.length }}자)</h2>
      <div class="card">
        <p class="muted">[멘토명], [멘티명]은 보내기 전에 직접 채워 주세요. 90자 단위로 나눠 보여 드립니다.</p>
        <div v-for="(p, i) in res.sms.parts" :key="i" class="mini" style="margin: 6px 0">
          <span class="t">{{ i + 1 }} / {{ res.sms.parts.length }} ({{ p.length }}자)</span>{{ p }}
        </div>
        <div class="row">
          <button type="button" class="small" @click="copy(res.sms.text, 0)">전체 복사</button>
          <span v-if="copied === 0" class="ok">복사했습니다</span>
        </div>
      </div>
      <h2>통화에서 확인할 것</h2>
      <div class="card">
        <p class="muted">{{ res.call_script }}</p>
        <label v-for="q in res.questions" :key="q.key" class="field">
          <span class="name">{{ q.ask }}</span>
          <span v-if="q.pii" class="notice">{{ q.note }}</span>
          <textarea v-else v-model="answers[q.key]" placeholder="통화에서 들은 내용을 짧게 적어 주세요"></textarea>
          <span v-if="!q.pii && q.note" class="notice">{{ q.note }}</span>
        </label>
        <AliasInput v-model="alias" />
        <div class="row"><button type="button" @click="save">답변을 보관함에 저장</button><span>{{ status }}</span></div>
      </div>
      <div class="box warn"><ul><li v-for="n in res.notes" :key="n">{{ n }}</li></ul></div>
    </template>
  </div>
</template>
