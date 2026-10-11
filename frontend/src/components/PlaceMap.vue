<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { api } from '../api/client'
import { kakaoLink, loadKakao } from '../lib/places'

// 협약 장소 지도와 목록. 지도는 카카오맵이고, 키가 없거나 주소가 등록되지 않았으면 목록만 보여 준다.
// pickable이면 목록에서 장소를 고를 수 있다 (picked: 고른 장소 이름). 카카오에는 장소 이름과 좌표만 전달된다.
const props = defineProps({ places: { type: Array, required: true }, pickable: { type: Boolean, default: false }, picked: { type: String, default: '' } })
const emit = defineEmits(['update:picked'])
const mapEl = ref(null)
const mapNote = ref('')
const selected = ref('')
let kakao = null
let map = null
let markers = []
let info = null

function draw() {
  if (!map) return
  markers.forEach((m) => m.setMap(null))
  markers = []
  info?.close()   // 자치구를 바꾸면 열려 있던 말풍선을 닫는다
  if (!props.places.length) return
  const bounds = new kakao.maps.LatLngBounds()
  for (const p of props.places) {
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

function pick(p) {
  emit('update:picked', p.name)
  focus(p)
}

onMounted(async () => {
  await nextTick()
  try {
    const config = await api.config()
    kakao = await loadKakao(config.kakaoMapJsKey)
    map = new kakao.maps.Map(mapEl.value, { center: new kakao.maps.LatLng(37.5665, 126.978), level: 8 })
    draw()
  } catch (e) {
    mapNote.value = `${e.message} 아래 목록의 [카카오맵 열기]로 위치를 확인할 수 있습니다.`
  }
})
watch(() => props.places, draw)
</script>

<template>
  <div>
    <div v-show="!mapNote" ref="mapEl" class="map" data-test="map"></div>
    <p v-if="mapNote" class="notice" data-test="map-note">{{ mapNote }}</p>
    <div v-for="p in places" :key="p.id" class="place" :class="{ on: selected === p.id || (pickable && picked === p.name) }" data-test="place">
      <div class="row">
        <label v-if="pickable" class="check flush"><input type="radio" name="place" :checked="picked === p.name" :data-pick="p.id" @change="pick(p)" /><strong>{{ p.name }}</strong></label>
        <strong v-else>{{ p.name }}</strong>
        <span class="tag">{{ p.type }}</span><span class="grow"></span>
        <button v-if="!mapNote" type="button" class="small" :aria-label="`${p.name} 위 지도에 표시`" @click="focus(p); mapEl.scrollIntoView?.({ block: 'nearest' })">위 지도에 표시</button>
        <a :href="kakaoLink(p)" target="_blank" rel="noopener noreferrer" class="linkbutton small" :aria-label="`${p.name} 카카오맵 열기 (새 창)`">카카오맵 열기</a>
      </div>
      <div class="muted">{{ [p.address, p.hours].filter(Boolean).join(' · ') }}</div>
      <div v-if="p.note" class="notice">{{ p.note }}</div>
    </div>
  </div>
</template>
