<script setup>
import { reactive, ref, watch } from 'vue'
import { copyText } from '../lib/copy'
import { draftFields, toText } from '../lib/formFields'

// 초안 결과: 되물을 질문(위), 경고 상자, 필드별 편집·복사, 제출 안내.
const props = defineProps({
  form: { type: Object, required: true },
  result: { type: Object, required: true },
  // 복사 전에 한 번 더 확인할 문구 (종합계획서①: 등록 후 수정 불가)
  confirmBeforeCopy: { type: String, default: '' },
})
const emit = defineEmits(['change'])

const fields = draftFields(props.form)
const text = reactive({})
const copied = ref('')
let confirmed = false

watch(() => props.result, (r) => {
  for (const f of fields) text[f.key] = toText(r.draft?.[f.key])
  confirmed = false
}, { immediate: true })

function edited() {
  const draft = {}
  for (const f of fields) draft[f.key] = f.list ? text[f.key].split('\n').filter((x) => x.trim()) : text[f.key]
  emit('change', draft)
}

async function copy(key) {
  if (props.confirmBeforeCopy && !confirmed) {
    if (!window.confirm(props.confirmBeforeCopy)) return
    confirmed = true
  }
  copied.value = (await copyText(text[key])) ? key : ''
}
</script>

<template>
  <div>
    <div v-if="result.missing_questions?.length" class="box ask" data-test="missing">
      <strong>아래 내용을 알려 주시면 초안을 더 채울 수 있습니다.</strong>
      <ul><li v-for="q in result.missing_questions" :key="q.key">{{ q.question }}</li></ul>
    </div>
    <div v-if="result.warnings?.length" class="box warn" data-test="warnings">
      <strong>확인해 주세요</strong>
      <ul><li v-for="w in result.warnings" :key="w">{{ w }}</li></ul>
    </div>
    <p v-if="result.pii_masked?.length" class="notice" data-test="pii">
      AI에 보내기 전에 가린 정보: {{ result.pii_masked.join(', ') }}
    </p>
    <p class="muted">초안입니다. 내용을 확인하고 고친 뒤 플랫폼에 옮겨 주세요. [멘티명] 같은 자리표시는 플랫폼에서 직접 채웁니다.</p>

    <div v-for="f in fields" :key="f.key" class="card">
      <div class="row">
        <strong>{{ f.label }}</strong>
        <span v-if="f.pii" class="tag">직접 입력</span>
        <span class="spacer" style="flex: 1"></span>
        <span v-if="copied === f.key" class="ok">복사했습니다</span>
        <button v-if="!f.pii" type="button" class="small" :data-copy="f.key" @click="copy(f.key)">플랫폼에 복사</button>
      </div>
      <p v-if="f.pii" class="muted">{{ text[f.key] }}</p>
      <textarea v-else v-model="text[f.key]" :data-draft="f.key" :rows="f.list ? Math.min(16, Math.max(3, text[f.key].split('\n').length)) : 3"
        @input="edited"></textarea>
    </div>

    <div v-if="result.reminders?.length" class="card" data-test="reminders">
      <strong>제출 전에 확인할 것</strong>
      <ul><li v-for="r in result.reminders" :key="r">{{ r }}</li></ul>
    </div>
  </div>
</template>
