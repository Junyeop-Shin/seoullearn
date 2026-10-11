<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { menteeFacts, menteesFromVault } from '../lib/mentee'

// 도구 화면에서 멘티 한 명 고르기. 진행 중인 멘티만 보여 주고, 주소의 ?mentee= 값이나 첫 멘티를 먼저 고른다.
// v-model은 고른 멘티 {alias, items, profile} (없으면 null)
const model = defineModel({ type: Object, default: null })
const route = useRoute()
const mentees = ref([])
const loaded = ref(false)
onMounted(async () => {
  mentees.value = (await menteesFromVault().catch(() => [])).filter((m) => !m.profile.archived)
  model.value = mentees.value.find((m) => m.alias === route.query.mentee) || mentees.value[0] || null
  loaded.value = true
})
</script>

<template>
  <p v-if="loaded && !mentees.length" class="card muted" data-test="no-mentee">등록한 멘티가 없습니다. <router-link to="/mentees/new">멘티를 등록</router-link>한 뒤 써 주세요.</p>
  <div v-else class="chips" role="group" aria-label="멘티 선택" data-test="mentee-pick">
    <button v-for="m in mentees" :key="m.alias" type="button" :aria-pressed="model?.alias === m.alias" :class="{ on: model?.alias === m.alias }" :data-mentee="m.alias" @click="model = m">
      <strong>{{ m.profile.name || m.alias }}</strong><small>{{ menteeFacts(m.profile) }}</small>
    </button>
  </div>
</template>
