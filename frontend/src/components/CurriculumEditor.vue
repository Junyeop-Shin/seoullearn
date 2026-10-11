<script setup>
import { watch } from 'vue'
import { weeklyDates } from '../lib/schedule'

// 주차별 커리큘럼 표. 일시는 1회차 일시에서 매주 같은 요일·같은 시각으로 채우고, 회차마다 고칠 수 있다 (고친 회차는 다시 계산하지 않는다).
// full이면 종합계획서②처럼 온라인 강의(몇 강)와 멘토링 내용을 따로 적는다. 종합계획서①은 학습 내용만 대략 적는다. 상담 내용은 넣지 않는다.
// 강좌가 여럿이면(courses) 주차마다 어느 강좌인지 고를 수 있다. 내용을 채워 주는 기능은 이 표를 쓰는 화면이 맡는다.
const props = defineProps({
  modelValue: { type: Array, required: true },   // [{week, date, content, online, mentoring, extras}]
  rounds: { type: Number, required: true },
  start: { type: String, default: '' },          // 1회차 일시 'YYYY-MM-DDTHH:MM'
  full: { type: Boolean, default: false },
  courses: { type: Array, default: () => [] },   // 종합계획서②의 수강 강좌 [{lecture, instructor}]
  hints: { type: Array, default: () => [] },     // 주차마다 칸에 흐리게 보여 줄 예시 (그 주차에 맞는 내용)
})
const emit = defineEmits(['update:modelValue'])

function sized() {
  const dates = weeklyDates(props.start.slice(0, 10), props.rounds)
  const time = props.start.slice(11, 16)
  return Array.from({ length: props.rounds }, (_, i) => {
    const old = props.modelValue[i] || {}
    const keep = old.edited   // 멘토가 직접 고친 회차의 일시는 건드리지 않는다
    return { week: i + 1, date: keep ? old.date : dates[i] || old.date || '', time: keep ? old.time : time || old.time || '', edited: !!old.edited,
      content: old.content || '', online: old.online || '', course: old.course || 0,
      mentoring: old.mentoring ?? (props.full && i === 0 ? '오리엔테이션(OT), 학습 계획 협의' : '') }
  })
}
// 회차 수나 시작일이 바뀌면 줄 수와 날짜를 다시 맞춘다 (적어 둔 내용은 남긴다)
// 값을 하나씩 견준다: 한 배열로 묶어 돌려주면 표를 고칠 때마다 다르다고 보아 끝없이 되풀이된다
watch([() => props.rounds, () => props.start, () => props.modelValue.length], () => emit('update:modelValue', sized()), { immediate: true })

function set(i, key, value) {
  emit('update:modelValue', props.modelValue.map((r, k) => (k === i ? { ...r, [key]: value } : r)))
}
function setWhen(i, key, value) {
  emit('update:modelValue', props.modelValue.map((r, k) => (k === i ? { ...r, [key]: value, edited: true } : r)))
}
</script>

<template>
  <div data-test="curriculum">
    <table class="curriculum">
      <thead><tr><th>주차</th><th>일시</th><th>{{ full ? '온라인 강의와 멘토링 내용' : '학습 내용' }}</th></tr></thead>
      <tbody>
      <tr v-for="(r, i) in modelValue" :key="r.week">
        <td>{{ r.week }}</td>
        <td class="when">
          <input type="date" :value="r.date" :data-date="r.week" :aria-label="`${r.week}주차 날짜`" @input="setWhen(i, 'date', $event.target.value)" />
          <input type="time" :value="r.time" :data-time="r.week" :aria-label="`${r.week}주차 시각`" @input="setWhen(i, 'time', $event.target.value)" />
        </td>
        <td v-if="full" class="cells">
          <select v-if="courses.length > 1" :value="r.course || 0" :aria-label="`${r.week}주차 강좌`" @change="set(i, 'course', Number($event.target.value))">
            <option v-for="(c, ci) in courses" :key="ci" :value="ci">{{ c.lecture || `강좌 ${ci + 1}` }}</option>
          </select>
          <label><span>온라인 강의</span><input :value="r.online" :data-online="r.week" :placeholder="`예: 강의 제목 (${2 * i + 1}~${2 * i + 2}강)`" @input="set(i, 'online', $event.target.value)" /></label>
          <label><span>멘토링 내용</span><input :value="r.mentoring" :data-mentoring="r.week" @input="set(i, 'mentoring', $event.target.value)" /></label>
        </td>
        <td v-else data-label="학습 내용">
          <input :value="r.content" :data-content="r.week" :aria-label="`${r.week}주차 학습 내용`" :placeholder="hints[i] ? `예: ${hints[i]}` : ''" @input="set(i, 'content', $event.target.value)" />
        </td>
      </tr>
      </tbody>
    </table>
    <p class="notice">일시는 1회차 일시에서 매주 같은 요일·같은 시각으로 채웠습니다. 일정이 다른 회차는 그 줄의 날짜와 시각을 고쳐 주세요.</p>
  </div>
</template>
