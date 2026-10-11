<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { loadChannels } from '../lib/channels'

// 시간확대(120분) 신청 요건 확인. 신청은 멘티가 직접 하므로(2026.8.10. 신청 건부터, 공지) 멘토는 요건이 되는지만 본다. 규칙만 쓰고 저장하지 않는다.
// 요건: 활동가이드 5-1(p.55~56)과 '2026 시간확대 멘토링 운영 및 신청 안내' 공지
const props = defineProps({ district: { type: String, default: '' } })
const ITEMS = [
  ['course', '고등과정 학습사이트를 수강하고 있다', '이투스, 메가스터디, 밀크T 고등, 대성마이맥, 에듀윌(검정고시)'],
  ['term', '서울런 멘토링을 1회기 이상 마쳤다', ''],
  ['rules', '이번 회기에 무단결석, 잦은 지각, 임박취소 같은 규칙 미준수가 없었다', ''],
  ['progress', '종합계획서②에서 목표한 인강 수강(진도)률이 60% 이상이다', '멘티가 월 1회 이상 PC로 로그인해야 수강 기록이 반영됩니다.'],
]
const checked = reactive({})
const channel = ref('')
const all = computed(() => ITEMS.every(([k]) => checked[k]))
const any = computed(() => ITEMS.some(([k]) => checked[k]))
onMounted(async () => { channel.value = (await loadChannels())[props.district] || '' })
</script>

<template>
  <div class="card checks" data-test="extension-check">
    <p class="muted flush">시간확대는 멘티가 직접 신청합니다. 아래 네 가지가 모두 맞으면 신청할 수 있습니다.</p>
    <label v-for="[key, label, hint] in ITEMS" :key="key" class="check"><input v-model="checked[key]" type="checkbox" :data-ext="key" />
      <span>{{ label }}<small v-if="hint" class="notice">{{ hint }}</small></span></label>
    <div v-if="all" class="box ask" data-test="extension-ok">
      <strong>신청할 수 있습니다. 멘티에게 알려 주세요.</strong>
      <ul>
        <li>멘티가 서울런 공지사항의 구글폼으로 직접 신청합니다. 새 회기 시작 2주 전부터 신청하기를 권장합니다.</li>
        <li>회기가 시작되기 전에 신청해 승인받아야 합니다. 승인 전에 2시간으로 진행하면 인정되지 않습니다.</li>
        <li>신청하기 전에 자치구 이음단에 미리 알려 주세요.</li>
        <li>요건을 채워도 출결과 수강 시간을 함께 검토해 반려될 수 있습니다.</li>
      </ul>
    </div>
    <div v-else-if="any" class="box warn" data-test="extension-no">
      <strong>아직 요건을 모두 채우지 못했습니다.</strong>
      그래도 시간확대가 꼭 필요하다면 자치구 이음단과 먼저 상의해 주세요. 수강률이 조금 모자라도 실제 수강 시간 등을 보고 승인되는 경우가 있습니다.
    </div>
    <div v-if="any" class="row">
      <a v-if="channel" :href="channel" target="_blank" rel="noopener noreferrer" class="linkbutton small" data-test="extension-channel">{{ district }} 이음단 카카오톡 채널 열기</a>
      <router-link v-else to="/ieumdan" class="linkbutton small">이음단 연락처 보기</router-link>
    </div>
  </div>
</template>
