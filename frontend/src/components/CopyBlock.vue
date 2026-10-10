<script setup>
import { copyText } from '../lib/copy'

// 붙여 넣을 글 한 덩어리: 고칠 수 있는 글 상자와 [복사] 버튼.
const props = defineProps({ label: { type: String, default: '' }, modelValue: { type: String, default: '' }, rows: { type: Number, default: 0 },
  placeholder: { type: String, default: '' }, field: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])
const copy = () => copyText(props.modelValue, props.label)
</script>

<template>
  <div class="card copy-block">
    <div class="row">
      <strong class="grow"><template v-if="label">{{ label }}</template><span class="tag">{{ modelValue.length }}자</span></strong>
      <button type="button" class="small primary" data-test="copy" :disabled="!modelValue.trim()" @click="copy">복사</button>
    </div>
    <textarea :value="modelValue" :rows="rows || Math.min(14, Math.max(3, modelValue.split('\n').length + 1, Math.ceil(modelValue.length / 55)))" :aria-label="label || undefined" data-test="copy-text" :data-field="field || undefined" :placeholder="placeholder"
      @input="emit('update:modelValue', $event.target.value)"></textarea>
  </div>
</template>
