<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/client'

// 관리자 화면: 매뉴얼로 답하지 못한 질문 모음. 가린 질문 문장만 있고 질문한 사람 정보는 없다.
const rows = ref([])
const error = ref('')
const LABEL = { no: '답 없음', partial: '일부만 답함' }

async function load() {
  error.value = ''
  try {
    rows.value = await api.unanswered()
  } catch (e) {
    error.value = e.message
  }
}
onMounted(load)

async function remove(id) {
  if (!window.confirm('이 항목을 지울까요?')) return
  try {
    await api.deleteUnanswered(id)
  } catch (e) {
    return (error.value = e.message)
  }
  await load()
}
</script>

<template>
  <div class="shell">
    <h1>답 못 한 질문</h1>
    <p class="muted">매뉴얼로 답하지 못한 질문을 모은 목록입니다. 매뉴얼과 공지를 보완할 때 참고합니다. 개인정보는 가린 문장만 저장하고, 누가 물었는지는 저장하지 않습니다.</p>
    <div v-if="error" class="box error" role="alert">{{ error }}</div>
    <div class="row">
      <a v-if="rows.length" href="/api/admin/unanswered/export.csv" class="linkbutton">CSV로 내려받기</a>
      <span class="muted">{{ rows.length }}건 (최근 1,000건까지)</span>
    </div>
    <div class="card">
      <p v-if="!rows.length" class="muted">모인 질문이 없습니다.</p>
      <table v-else>
        <thead><tr><th>날짜</th><th>분류</th><th>문의처</th><th>질문</th><th></th></tr></thead>
        <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td class="nowrap">{{ r.createdOn }}</td><td class="nowrap">{{ LABEL[r.answerable] || r.answerable }}</td>
          <td class="nowrap">{{ r.route || '-' }}</td><td>{{ r.question }}</td>
          <td><button type="button" class="small danger" :aria-label="`${r.createdOn} 질문 지우기`" @click="remove(r.id)">지우기</button></td>
        </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
