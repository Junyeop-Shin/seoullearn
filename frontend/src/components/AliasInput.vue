<script setup>
import { onMounted, ref } from 'vue'
import { getCurrentAlias, setCurrentAlias } from '../lib/mentee'
import { listAliases } from '../stores/vault'

// 멘티 고르기. 별칭은 보관함에서 자료를 묶는 이름이며 이 브라우저에만 저장된다.
// 한 번 고르면 다른 화면으로 옮겨 가도 같은 멘티가 선택돼 있다.
const props = defineProps({ modelValue: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])
const aliases = ref([])

function update(value) {
  setCurrentAlias(value)
  emit('update:modelValue', value)
}

onMounted(async () => {
  try {
    aliases.value = await listAliases()
  } catch {
    aliases.value = []
  }
  if (!props.modelValue && getCurrentAlias()) emit('update:modelValue', getCurrentAlias())
})
</script>

<template>
  <label class="field">
    <span class="name">멘티 별칭</span>
    <input :value="modelValue" list="alias-list" placeholder="예: 수학 고2 A" maxlength="30" @input="update($event.target.value)" />
    <datalist id="alias-list"><option v-for="a in aliases" :key="a" :value="a" /></datalist>
    <span class="notice">실명을 쓰지 마세요. 과목처럼 본인만 알아볼 수 있는 이름을 씁니다. 이 브라우저에만 저장됩니다.
      <router-link to="/mentees">멘티 정보 관리</router-link></span>
  </label>
</template>
