<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api/client'
import CopyBlock from '../../components/CopyBlock.vue'
import { handoverNote, parseHandoverText, receivedHandover } from '../../lib/reports'
import { fillNames } from '../../lib/schedule'
import { toast } from '../../lib/toast'
import { loadSettings } from '../../stores/settings'
import { saveItem } from '../../stores/vault'

// 사전 연락: 멘티를 처음 만나는 1회기에만 하는 단계. 등록 정보로 문자 문구를 바로 만든다 (템플릿, AI 미사용).
// 이전 멘토에게 인계받은 멘티라면 받은 글을 여기에 붙여 넣어 두고 확인한다.
defineOptions({ inheritAttrs: false })   // 멘티 화면이 모든 단계에 같은 값을 넘긴다: 안 쓰는 값이 화면 요소에 붙지 않게 한다
const props = defineProps({ alias: { type: String, required: true }, profile: { type: Object, required: true }, items: { type: Array, default: () => [] } })
const emit = defineEmits(['saved'])
const mentor = loadSettings()
const res = ref(null)
const text = ref('')
const error = ref('')
// 인계받은 글은 붙여 넣은 그대로 이 브라우저에 둔다. 종합계획서①을 쓸 때 옆에 띄워 참고한다.
// AI에는 글 전체가 아니라 그 안의 허용된 네 항목('[출석 패턴] …')만 참고 자료로 넘긴다 (lib/reports.js의 handoverForDraft)
const savedHandover = receivedHandover(props.items)
const note = ref(handoverNote(savedHandover?.draft))

async function saveHandover() {
  try {
    const text = note.value.trim()
    await saveItem({ id: savedHandover?.id, alias: props.alias, formId: 'handover_summary', title: '인계받은 내용', draft: { ...parseHandoverText(text).found, text } })
    toast('인계받은 내용을 저장했습니다.')
    emit('saved')
  } catch (e) {
    error.value = e.message
  }
}

onMounted(async () => {
  try {
    const p = props.profile
    res.value = await api.preContact(p.mode || '온라인', (p.subject === '기타' ? p.subjectEtc : p.subject) || '')
    text.value = fillNames(res.value.sms.text, { mentee: p.name, mentor: mentor.name, phone: mentor.phone })
  } catch (e) {
    error.value = e.message
  }
})
</script>

<template>
  <div>
    <p class="muted">매칭 직후 멘티(보호자)에게 보낼 문자입니다. 서울런 플랫폼의 문자 보내기로 보내면 멘토 번호가 찍히지 않으므로 회신받을 번호가 문구 안에 들어갑니다.</p>
    <div v-if="!mentor.name || !mentor.phone" class="box warn" data-test="need-mentor">
      멘토 이름과 연락처가 없어 [멘토명], [멘토 연락처]가 그대로 남습니다. <router-link to="/settings">멘토 설정</router-link>에서 적어 두면 자동으로 채워집니다.
    </div>
    <div v-if="!profile.name" class="box warn" data-test="need-mentee">멘티 이름이 없어 [멘티명]이 그대로 남습니다. 멘티 설정에서 이름을 적어 주세요.</div>
    <div v-if="error" class="box error" role="alert">{{ error }}</div>
    <template v-if="res">
      <!-- 문자 문구는 저장하지 않는 글이다: 고쳐도 '저장하지 않은 내용'으로 치지 않는다 -->
      <CopyBlock v-model="text" label="사전 연락 문자" data-nodirty />
      <div class="box"><ul><li v-for="n in res.notes" :key="n">{{ n }}</li></ul></div>
    </template>

    <!-- 인계받은 멘티에게만 필요한 칸이라 접어 둔다. 붙여 넣어 둔 글이 있으면 펼쳐 둔다 -->
    <details class="fold" :open="!!savedHandover" data-test="handover-fold">
      <summary>이전 멘토에게 인계받은 내용이 있다면</summary>
      <form data-test="handover-form" @submit.prevent="saveHandover">
        <textarea v-model="note" :rows="Math.max(5, note.split('\n').length + 1)" placeholder="이전 멘토가 보낸 글을 그대로 붙여 넣어 주세요." aria-label="이전 멘토에게 인계받은 내용" data-test="handover-note"></textarea>
        <div class="row gap-top"><button :disabled="!note.trim() && !savedHandover" data-test="save-handover">인계받은 내용 저장</button></div>
      </form>
    </details>
  </div>
</template>
