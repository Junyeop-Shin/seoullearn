<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import PlaceMap from '../components/PlaceMap.vue'
import { districts, filterPlaces } from '../lib/places'

// 협약 장소 (오프라인 멘토링). 자치구별로 위치를 찾아보는 화면이다. 장소는 이음단을 통해 예약한다.
const data = ref({ places: [], sample: false })
const district = ref('')
const error = ref('')
const shown = computed(() => filterPlaces(data.value.places, { district: district.value }))

onMounted(async () => {
  try {
    data.value = await api.places()
  } catch (e) {
    error.value = e.message
  }
})
</script>

<template>
  <div class="shell">
    <h1>협약 장소</h1>
    <p class="muted">오프라인 멘토링 장소를 찾아보는 화면입니다. 장소는 직접 예약하지 않고 자치구 이음단에 요청해 승인받아야 합니다.</p>
    <div v-if="data.sample" class="box warn" data-test="sample">지금 보이는 장소는 모두 지어낸 예시입니다. 실제 협약 장소가 아닙니다.</div>
    <div v-if="error" class="box error">{{ error }}</div>
    <label class="field" style="max-width: 260px"><span class="name">자치구</span>
      <select v-model="district"><option value="">전체</option><option v-for="d in districts(data.places)" :key="d">{{ d }}</option></select>
    </label>
    <PlaceMap :places="shown" />
    <router-link to="/schedule"><button type="button" class="primary" style="margin-top: 12px">오프라인 일정·장소 정하러 가기</button></router-link>
  </div>
</template>
