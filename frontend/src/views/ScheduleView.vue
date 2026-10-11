<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import CopyBlock from '../components/CopyBlock.vue'
import PlaceMap from '../components/PlaceMap.vue'
import { PROFILE_FORM, menteeFacts, menteesFromVault, regularSchedule } from '../lib/mentee'
import { filterPlaces } from '../lib/places'
import { WEEKDAYS, monthDates, monthlyText, nextMonth, thisMonth, todayText } from '../lib/schedule'
import { toast } from '../lib/toast'
import { loadChannels } from '../lib/channels'
import { loadSettings } from '../stores/settings'
import { saveItem } from '../stores/vault'
import TEMPLATE from '../templates/monthly_schedule.md?raw'

// 오프라인 일정·장소: 오프라인 멘토링은 매월 20일쯤 다음달 일정과 장소를 자치구 이음단에 알려야 한다.
// 새로 매칭된 멘티의 첫 장소 요청도 여기서 한다 (종합계획서 단계에 따로 두지 않는다).
// 멘티를 한 명 고르면 그 멘티의 일정과 자치구의 협약 장소가 나온다. 문구는 규칙과 템플릿으로만 만든다 (AI 미사용, 서버로 보내지 않음).
const route = useRoute()
const mentor = loadSettings()
const today = todayText()
const MONTHS = { next: nextMonth(today), this: thisMonth(today) }
const mentees = ref([])         // 진행 중인 오프라인 멘티 [{alias, profile}]
const loaded = ref(false)
const picked = ref('')          // 고른 멘티
const which = ref('next')       // 어느 달: next | this
const regular = ref([])         // 정규 요일과 시각 [{weekday, startTime}]
const rows = ref([])            // 그 달의 일정 [{date, start}]
const venue = ref('')
const places = ref({ places: [], sample: false })
const channels = ref({})
const text = ref('')
const current = computed(() => mentees.value.find((m) => m.alias === picked.value))
const ym = computed(() => MONTHS[which.value])
const nearby = computed(() => filterPlaces(places.value.places, { district: current.value?.profile.district }))
const channel = computed(() => channels.value[current.value?.profile.district] || '')   // 고른 멘티의 자치구 이음단 카카오톡 채널

onMounted(async () => {
  channels.value = await loadChannels()
  try {
    places.value = await api.places()
  } catch {
    places.value = { places: [], sample: false }   // 장소 목록을 못 받아도 일정 문구는 만들 수 있다
  }
  const out = (await menteesFromVault().catch(() => [])).filter((m) => m.profile.mode === '오프라인' && !m.profile.archived)
  mentees.value = out
  loaded.value = true
  picked.value = out.some((m) => m.alias === route.query.mentee) ? String(route.query.mentee) : out[0]?.alias || ''
})

// 이번 달을 고르면 이미 지난 날짜는 넣지 않는다 (오늘부터)
const fillDates = () => {
  rows.value = monthDates(regular.value.filter((r) => r.weekday), ym.value.year, ym.value.month).filter((r) => which.value !== 'this' || r.date >= today)
}

// 멘티를 고르면 그 멘티의 정규 요일과 장소로 채운다
watch(picked, () => {
  const p = current.value?.profile
  if (!p) return
  const saved = regularSchedule(p).map((r) => ({ ...r }))
  regular.value = saved.length ? saved : [{ weekday: '', startTime: '' }]
  venue.value = p.venue || ''
  text.value = ''
  fillDates()
})
watch(which, fillDates)
// 일정이나 장소를 고치면 앞서 만든 문구는 지운다 (고치기 전의 일정이 이음단에 가지 않게 다시 만들게 한다)
watch([rows, venue], () => { text.value = '' }, { deep: true })
const lastDay = computed(() => new Date(ym.value.year, ym.value.month, 0).getDate())
const bound = (day) => `${ym.value.year}-${String(ym.value.month).padStart(2, '0')}-${String(day).padStart(2, '0')}`

async function build() {
  const m = current.value
  const sorted = rows.value.filter((r) => r.date).sort((a, b) => (a.date + a.start < b.date + b.start ? -1 : 1))
  text.value = monthlyText(TEMPLATE, { month: ym.value.month, mentorName: mentor.name, menteeName: m.profile.name || m.alias, venue: venue.value.trim(),
    rows: sorted, minutes: m.profile.duration })
  // 다음 달에도 그대로 쓰도록 장소와 정규 요일을 멘티 정보에 저장해 둔다
  const days = regular.value.filter((r) => r.weekday).map((r) => ({ ...r }))
  const { _id, ...rest } = m.profile
  const next = { ...rest, venue: venue.value.trim() || rest.venue || '', regularSchedule: days.length ? days : rest.regularSchedule || [] }
  if (next.venue !== (rest.venue || '') || JSON.stringify(next.regularSchedule) !== JSON.stringify(rest.regularSchedule || [])) {
    await saveItem({ id: _id, alias: m.alias, formId: PROFILE_FORM, title: '멘티 정보', draft: next })
    m.profile = { ...next, _id }
    toast('장소와 정규 요일을 이 멘티의 정보에 저장했습니다.')
  }
}
</script>

<template>
  <div class="shell">
    <h1>오프라인 일정·장소</h1>
    <p class="muted">다음 달 일정과 장소를 매월 20일쯤 자치구 이음단에 알립니다. 새 멘티의 첫 장소 요청도 여기서 만듭니다.</p>
    <p v-if="loaded && !mentees.length" class="card muted" data-test="empty">진행 중인 오프라인 멘티가 없습니다.</p>

    <template v-if="mentees.length">
      <div class="chips" role="group" aria-label="멘티 선택" data-test="mentee-chips">
        <button v-for="m in mentees" :key="m.alias" type="button" :aria-pressed="picked === m.alias" :class="{ on: picked === m.alias }" :data-mentee="m.alias" @click="picked = m.alias">
          <strong>{{ m.profile.name || m.alias }}</strong><small>{{ menteeFacts(m.profile) }}</small>
        </button>
      </div>
    </template>

    <template v-if="current">
      <div class="row" data-test="channel">
        <a v-if="channel" :href="channel" target="_blank" rel="noopener noreferrer" class="linkbutton small" data-test="channel-link">{{ current.profile.district }} 이음단 카카오톡 채널 열기</a>
        <span v-else class="notice">{{ current.profile.district ? `${current.profile.district} 이음단의 채널 주소가 아직 등록되지 않았습니다.` : '멘티 설정에서 자치구를 적으면 이음단 채널 바로가기가 나옵니다.' }} <router-link to="/ieumdan">이음단 연락처</router-link></span>
      </div>
      <h2>일정</h2>
      <div class="card" data-test="schedule">
        <div class="choices" role="radiogroup" aria-label="일정을 만들 달">
          <label><input v-model="which" type="radio" value="next" name="which" data-month="next" />다음 달 ({{ MONTHS.next.month }}월)</label>
          <label><input v-model="which" type="radio" value="this" name="which" data-month="this" />이번 달 ({{ MONTHS.this.month }}월)</label>
        </div>
        <div class="field" role="group" aria-label="정규 요일과 시작 시각"><span class="name">정규 요일과 시작 시각</span>
          <div v-for="(r, i) in regular" :key="i" class="row schedule-row">
            <select v-model="r.weekday" class="narrow" aria-label="요일" :data-regular="`weekday-${i}`"><option value="">요일</option><option v-for="d in WEEKDAYS" :key="d">{{ d }}</option></select>
            <input v-model="r.startTime" type="time" class="narrow" aria-label="시작 시각" :data-regular="`time-${i}`" />
            <button v-if="regular.length > 1" type="button" class="small" :aria-label="`${i + 1}번째 요일 삭제`" @click="regular.splice(i, 1)">삭제</button>
          </div>
          <div class="row">
            <button type="button" class="small" @click="regular.push({ weekday: '', startTime: '' })">요일 추가</button>
            <button type="button" class="small" data-test="fill-dates" @click="fillDates">이 요일로 {{ ym.month }}월 날짜 채우기</button>
          </div>
        </div>
        <div class="field" role="group" :aria-label="`${ym.month}월 일정`"><span class="name">{{ ym.month }}월 일정 <span class="tag">{{ rows.filter((r) => r.date).length }}회</span></span>
          <div v-for="(r, i) in rows" :key="i" class="row schedule-row" data-test="date-row">
            <input v-model="r.date" type="date" :min="bound(1)" :max="bound(lastDay)" :aria-label="`${i + 1}번째 날짜`" />
            <input v-model="r.start" type="time" class="narrow" :aria-label="`${i + 1}번째 시작 시각`" />
            <button type="button" class="small" :aria-label="`${i + 1}번째 날짜 삭제`" @click="rows.splice(i, 1)">삭제</button>
          </div>
          <button type="button" class="small" @click="rows.push({ date: '', start: rows[0]?.start || regular[0]?.startTime || '' })">날짜 추가</button>
          <span class="notice">달을 바꾸면 정규 요일로 날짜를 다시 채웁니다. 빠지는 날은 삭제하고, 보강일은 [날짜 추가]로 넣어 주세요.</span>
        </div>
      </div>

      <h2>장소 <span class="tag">{{ current.profile.district || '자치구 미입력' }}</span></h2>
      <div class="card" data-test="venue">
        <label class="field flush"><span class="name">멘토링 장소</span>
          <input v-model="venue" placeholder="예: ○○ 스터디카페" maxlength="60" data-test="venue-input" />
          <span class="notice">아래 목록에서 고르거나 직접 적어 주세요. 비워 두면 이음단에 장소 안내를 부탁하는 문구가 들어갑니다.</span>
        </label>
        <div v-if="places.sample" class="box warn" data-test="places-notice">{{ places.notice || '지금 보이는 장소는 모두 지어낸 예시입니다. 실제 협약 장소 목록을 받으면 바뀝니다.' }}</div>
        <PlaceMap v-if="nearby.length" :key="current.profile.district" v-model:picked="venue" :places="nearby" pickable />
        <p v-else class="notice">이 자치구의 장소 목록이 아직 없습니다. <router-link to="/places">전체 협약 장소</router-link>를 참고해 주세요.</p>
      </div>

      <button type="button" class="primary" :disabled="!rows.some((r) => r.date)" data-test="build" @click="build">이음단에 보낼 문구 만들기</button>
      <template v-if="text">
        <CopyBlock v-model="text" :label="`${current.profile.district || ''} 이음단에 보낼 문구`" />
        <div class="row">
          <a v-if="channel" :href="channel" target="_blank" rel="noopener noreferrer" class="linkbutton primary" data-test="channel-send">{{ current.profile.district }} 이음단 카카오톡 채널 열기</a>
          <span v-else class="notice">이음단 채널 주소가 아직 등록되지 않았습니다. <router-link to="/ieumdan">이음단 연락처</router-link>를 확인해 주세요.</span>
        </div>
        <p class="notice">문구를 복사해 채널에 직접 보내 주세요. 장소와 일정은 이음단의 승인이 있어야 확정됩니다.</p>
      </template>
    </template>
  </div>
</template>
