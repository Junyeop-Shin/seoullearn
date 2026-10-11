<script setup>
import { onMounted, ref } from 'vue'
import { loadChannels } from '../lib/channels'
import { DISTRICTS, menteesFromVault } from '../lib/mentee'

// 이음단 연락처: 자치구 이음단과는 카카오톡 채널로 연락한다. 자치구별 채널을 바로 열 수 있게 모았다.
// 진행 중인 내 멘티가 있는 자치구를 위에 따로 보여 준다. 채널 주소는 화면 자료이고, 멘티 정보는 이 브라우저에서만 읽는다.
const channels = ref({})
const mine = ref([])   // [{district, names}]
const loaded = ref(false)

onMounted(async () => {
  channels.value = await loadChannels()
  const by = new Map()
  for (const { alias, profile: p } of await menteesFromVault().catch(() => [])) {   // 보관함을 못 읽어도 자치구 목록은 보여 준다
    if (p.district && !p.archived) by.set(p.district, [...(by.get(p.district) || []), p.name || alias])
  }
  mine.value = [...by].map(([district, names]) => ({ district, names })).sort((a, b) => a.district.localeCompare(b.district, 'ko'))
  loaded.value = true
})
</script>

<template>
  <div class="shell">
    <h1>이음단 연락처</h1>
    <p class="muted">자치구 이음단과는 카카오톡 채널로 연락합니다. 활동보고서 승인, 멘토링 장소와 일정 변경처럼 매칭 이후의 운영에 관한 일은 멘티가 속한 자치구의 이음단에 문의해 주세요.</p>
    <p class="box ask">오프라인 멘토링의 일정이나 장소를 바꾸려면 예약된 일정의 최소 3일 전, 이음단 근무 시간 안에 요청해야 합니다.</p>

    <template v-if="mine.length">
      <h2>내 멘티의 자치구</h2>
      <div class="card contacts" data-test="my-channels">
        <div v-for="m in mine" :key="m.district" class="contact">
          <div><strong>{{ m.district }} 이음단</strong><small>{{ m.names.join(', ') }}</small></div>
          <a v-if="channels[m.district]" :href="channels[m.district]" target="_blank" rel="noopener noreferrer" class="linkbutton" :data-channel="m.district">카카오톡 채널 열기</a>
          <span v-else class="notice">카카오톡 채널 주소가 아직 등록되지 않았습니다.</span>
        </div>
      </div>
    </template>

    <h2>모든 자치구</h2>
    <div v-if="loaded" class="card districts" data-test="all-channels">
      <template v-for="d in DISTRICTS" :key="d">
        <a v-if="channels[d]" :href="channels[d]" target="_blank" rel="noopener noreferrer" class="district" :data-channel-all="d">{{ d }}</a>
        <span v-else class="district none" :title="`${d} 이음단 채널 주소가 아직 등록되지 않았습니다`">{{ d }}<small>주소 없음</small></span>
      </template>
    </div>
    <p class="notice">자치구를 누르면 카카오톡 채널이 새 창으로 열립니다.</p>
  </div>
</template>
