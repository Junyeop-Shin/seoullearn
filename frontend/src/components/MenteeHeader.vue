<script setup>
import { menteePath } from '../lib/mentee'

// 멘티 작업 공간 안쪽 화면의 머리말: 내 멘티 › 별칭 › 지금 화면
defineProps({ alias: { type: String, required: true }, title: { type: String, default: '' } })
</script>

<template>
  <nav class="crumbs" aria-label="현재 위치">
    <router-link to="/mentees">내 멘티</router-link><span>›</span>
    <router-link v-if="title" :to="menteePath(alias)">{{ alias }}</router-link><strong v-else>{{ alias }}</strong>
    <template v-if="title"><span>›</span><strong>{{ title }}</strong></template>
  </nav>
</template>
