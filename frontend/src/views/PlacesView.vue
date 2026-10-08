<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { api } from '../api/client'
import { districts, filterPlaces, kakaoLink, loadKakao } from '../lib/places'

// 협약 장소 지도 (오프라인 멘토링). 장소는 이음단을 통해 예약한다. 이 화면은 위치를 찾아보는 용도다.
const data = ref({ places: [], sample: false })
const district = ref('')
const error = ref('')
const mapNote = ref('')
const mapEl = ref(null)
const selected = ref('')
const shown = computed(() => filterPlaces(data.value.places, { district: district.value }))
let kakao = null
let map = null
let markers = []
let info = null

function draw() {
  if (!map) return
  markers.forEach((m) => m.setMap(null))
  markers = []
  if (!shown.value.length) return
  const bounds = new kakao.maps.LatLngBounds()
  for (const p of shown.value) {
    const pos = new kakao.maps.LatLng(p.lat, p.lng)
    const marker = new kakao.maps.Marker({ map, position: pos, title: p.name })
    kakao.maps.event.addListener(marker, 'click', () => focus(p))
    markers.push(marker)
    bounds.extend(pos)
  }
  map.setBounds(bounds)
}

function focus(p) {
  selected.value = p.id
  if (!map) return
  const pos = new kakao.maps.LatLng(p.lat, p.lng)
  map.setLevel(4)
  map.panTo(pos)
  info?.close()
  const el = document.createElement('div')
  el.style.cssText = 'padding:6px 10px;font-size:13px;white-space:nowrap'
  el.textContent = p.name // 글자로만 넣는다 (HTML로 해석하지 않는다)
  info = new kakao.maps.InfoWindow({ content: el, position: pos })
  info.open(map)
}

onMounted(async () => {
  try {
    const [places, config] = await Promise.all([api.places(), api.config()])
    data.value = places
    await nextTick()
    try {
      kakao = await loadKakao(config.kakaoMapJsKey)
      map = new kakao.maps.Map(mapEl.value, { center: new kakao.maps.LatLng(37.5665, 126.978), level: 8 })
      draw()
    } catch (e) {
      mapNote.value = `${e.message} 아래 목록의 '카카오맵에서 보기'로 위치를 확인할 수 있습니다.`
    }
  } catch (e) {
    error.value = e.message
  }
})
watch(shown, draw)
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
    <div v-show="!mapNote" ref="mapEl" data-test="map" style="width: 100%; height: 380px; border: 1px solid var(--line); border-radius: 10px"></div>
    <p v-if="mapNote" class="notice" data-test="map-note">{{ mapNote }}</p>
    <div v-for="p in shown" :key="p.id" class="card" :style="selected === p.id ? 'border-color: var(--primary)' : ''" data-test="place">
      <div class="row">
        <strong>{{ p.name }}</strong><span class="tag">{{ p.type }}</span><span style="flex: 1"></span>
        <button type="button" class="small" @click="focus(p)">지도에서 보기</button>
        <a :href="kakaoLink(p)" target="_blank" rel="noopener noreferrer"><button type="button" class="small">카카오맵에서 보기</button></a>
      </div>
      <div class="muted">{{ p.address }} · {{ p.hours }}</div>
      <div class="notice">{{ p.note }}</div>
    </div>
    <router-link to="/ieumdan"><button type="button" class="primary">이음단에 장소 요청하기</button></router-link>
  </div>
</template>
