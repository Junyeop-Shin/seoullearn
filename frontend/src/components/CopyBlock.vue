<script setup>
import { ref } from 'vue'
import { copyText } from '../lib/copy'

// 붙여 넣을 글 한 덩어리: 고칠 수 있는 글 상자와 [복사] 버튼.
const props = defineProps({ label: { type: String, default: '' }, modelValue: { type: String, default: '' }, rows: { type: Number, default: 0 },
  placeholder: { type: String, default: '' }, field: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])
const copied = ref(false)

async function copy() {
  copied.value = await copyText(props.modelValue)
}
</script>

<template>
  <div class="card copy-block">
    <div class="row">
      <strong v-if="label">{{ label }}</strong><span class="tag">{{ modelValue.length }}자</span>
      <span style="flex: 1"></span>
      <span v-if="copied" class="ok">복사했습니다</span>
      <button type="button" class="small primary" data-test="copy" :disabled="!modelValue.trim()" @click="copy">복사</button>
    </div>
    <textarea :value="modelValue" :rows="rows || Math.min(14, Math.max(3, modelValue.split('\n').length + 1))" data-test="copy-text" :data-field="field || undefined" :placeholder="placeholder"
      @input="emit('update:modelValue', $event.target.value); copied = false"></textarea>
  </div>
</template>
