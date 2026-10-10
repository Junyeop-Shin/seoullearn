<script setup>
import { computed, ref } from 'vue'
import { latestOf } from '../../lib/reports'
import PlanStage from './PlanStage.vue'
import PrePlanStage from './PrePlanStage.vue'

// 종합계획서 단계: 1회차 전의 종합계획서① → 1회차 후의 종합계획서②를 한 단계에서 차례로 한다.
// 오프라인 멘토링의 장소와 일정은 이 단계가 아니라 '오프라인 일정·장소' 화면에서 이음단에 요청한다.
defineOptions({ inheritAttrs: false })   // 멘티 화면이 모든 단계에 같은 값을 넘긴다: 안 쓰는 값이 화면 요소에 붙지 않게 한다
const props = defineProps({ alias: { type: String, required: true }, profile: { type: Object, required: true }, items: { type: Array, required: true },
  update: { type: Function, required: true } })
const pre = computed(() => latestOf(props.items, 'plan_initial'))
const STEPS = computed(() => [
  { id: 'pre', label: '종합계획서① (1회차 전)', done: !!pre.value },
  { id: 'file', label: '종합계획서② (1회차 후)', done: !!latestOf(props.items, 'plan_file') },
])
// 처음 열 때는 아직 하지 않은 첫 순서를 보여 준다
const tab = ref((STEPS.value.find((s) => !s.done) || STEPS.value.at(-1)).id)
</script>

<template>
  <div>
    <div class="tabs" role="tablist" data-test="plan-tabs">
      <button v-for="s in STEPS" :key="s.id" type="button" role="tab" :aria-selected="tab === s.id" :class="{ on: tab === s.id }" :data-tab="s.id" @click="tab = s.id">
        {{ s.label }}<span v-if="s.done" class="ok"> ✓</span>
      </button>
    </div>
    <p v-if="profile.mode === '오프라인' && !profile.venue" class="box ask" data-test="venue-hint">
      오프라인 멘토링은 이음단이 장소를 예약한 뒤에 종합계획서①을 입력합니다. 장소와 일정은
      <router-link :to="{ path: '/schedule', query: { mentee: alias } }">오프라인 일정·장소</router-link>에서 이음단에 요청해 주세요.
    </p>
    <!-- 탭을 오가도 저장하지 않은 글이 남게 두 화면을 살려 둔다. 종합계획서①을 다시 저장하면 ②는 그 내용을 새로 가져오도록 다시 그린다 -->
    <KeepAlive>
      <PrePlanStage v-if="tab === 'pre'" :alias="alias" :profile="profile" :items="items" :update="update" />
      <PlanStage v-else :key="pre?.savedAt || 'none'" :alias="alias" :profile="profile" :items="items" :update="update" />
    </KeepAlive>
  </div>
</template>
