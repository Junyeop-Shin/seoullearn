<script setup>
import { ref, watch } from 'vue'
import { checklist } from '../lib/checklist'

// 보고서 체크리스트 팝업. 종합계획서②·활동보고서·완료보고서를 저장한 뒤 한 번 뜨고 [닫기]로 닫는다. 참고용이라 아무것도 막지 않는다.
const MARKS = { o: ['○', '작성함'], tri: ['△', '확인 필요'], x: ['✕', '빠짐'] }
const box = ref(null)
// showModal: 뒤 화면을 막고 Esc로 닫히는 브라우저 기본 팝업 (테스트 환경처럼 없는 곳에서는 open 속성으로 연다)
watch(() => checklist.items, (items) => {
  const el = box.value
  if (!el || !!items === el.open) return
  if (items) el.showModal ? el.showModal() : el.setAttribute('open', '')
  else el.close ? el.close() : el.removeAttribute('open')
}, { flush: 'post' })
</script>

<template>
  <dialog ref="box" class="checklist" aria-labelledby="checklist-title" data-test="checklist" @close="checklist.items = null">
    <h2 id="checklist-title">{{ checklist.title }} 체크리스트</h2>
    <p class="notice">저장했습니다. 아래는 활동가이드의 보고서 체크리스트를 화면에 적은 내용으로 살펴본 참고용 결과입니다. 모두 ○가 아니어도 제출할 수 있고, 모두 ○여도 승인이 보장되지는 않습니다.</p>
    <ul>
      <li v-for="i in checklist.items || []" :key="i.no" :data-check="i.no" :data-mark="i.mark">
        <span class="mark" :class="i.mark" role="img" :aria-label="MARKS[i.mark][1]">{{ MARKS[i.mark][0] }}</span>
        <span class="no">{{ i.no }}</span>
        <span>{{ i.text }}<small v-if="i.note">{{ i.note }}</small></span>
      </li>
    </ul>
    <div class="row">
      <span class="notice grow">○ 작성함 · △ 일부만 작성했거나 직접 확인이 필요함 · ✕ 빠짐</span>
      <button type="button" class="primary" data-test="checklist-ok" @click="checklist.items = null">닫기</button>
    </div>
  </dialog>
</template>
