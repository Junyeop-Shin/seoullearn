<script setup>
import { onMounted, ref } from 'vue'
import { listAliases } from '../stores/vault'

// 멘티 별칭. 보관함에서 초안을 묶는 이름이며 이 브라우저에만 저장된다.
defineProps({ modelValue: { type: String, default: '' } })
defineEmits(['update:modelValue'])
const aliases = ref([])
onMounted(async () => {
  try {
    aliases.value = await listAliases()
  } catch {
    aliases.value = []
  }
})
</script>

<template>
  <label class="field">
    <span class="name">멘티 별칭</span>
    <input :value="modelValue" list="alias-list" placeholder="예: 수학 고2 A" maxlength="30"
      @input="$emit('update:modelValue', $event.target.value)" />
    <datalist id="alias-list"><option v-for="a in aliases" :key="a" :value="a" /></datalist>
    <span class="notice">실명을 쓰지 마세요. 과목과 학년처럼 본인만 알아볼 수 있는 이름을 씁니다. 이 브라우저에만 저장됩니다.</span>
  </label>
</template>
