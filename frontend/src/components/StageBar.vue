<script setup>
// 단계 진행바: 지나온 단계, 지금 단계, 남은 단계. 누르면 그 단계 화면을 볼 수 있다 (자료는 그대로 남는다).
const props = defineProps({ stages: { type: Array, required: true }, current: { type: String, required: true }, viewing: { type: String, required: true } })
defineEmits(['view'])
const index = (id) => props.stages.findIndex((s) => s.id === id)
</script>

<template>
  <ol class="stagebar" aria-label="단계">
    <li v-for="(s, i) in stages" :key="s.id" :class="{ done: i < index(current), now: s.id === current, viewing: s.id === viewing }">
      <button type="button" :data-stage="s.id" :aria-current="s.id === current ? 'step' : undefined" :aria-pressed="s.id === viewing" @click="$emit('view', s.id)">
        <span class="n" :aria-label="i < index(current) ? `${i + 1}단계 마침` : undefined">{{ i < index(current) ? '✓' : i + 1 }}</span>{{ s.label }}
      </button>
    </li>
  </ol>
</template>
