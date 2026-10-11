<script setup>
import { ref } from 'vue'
import ExtensionCheck from '../components/ExtensionCheck.vue'
import MenteePick from '../components/MenteePick.vue'

// 시간확대 신청 요건 확인 (도구). 멘티를 고르면 그 멘티 자치구의 이음단 채널을 함께 보여 준다.
const mentee = ref(null)
</script>

<template>
  <div class="shell">
    <h1>시간확대 요건 확인</h1>
    <p class="muted">멘토링을 2시간으로 늘리는 시간확대는 멘티가 직접 신청합니다. 멘티가 신청할 수 있는지 여기서 확인해 주세요.</p>
    <MenteePick v-model="mentee" />
    <ExtensionCheck v-if="mentee" :key="mentee.alias" :district="mentee.profile.district" />
  </div>
</template>
