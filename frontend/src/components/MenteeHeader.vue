<script setup>
import { menteePath } from '../lib/mentee'

// 멘티 작업 공간 안쪽 화면의 머리말: 내 멘티 › 멘티 이름 › 지금 화면. 이름을 바꿨으면 바꾼 이름(name)을 보여 준다 (alias는 처음 등록한 이름이다)
defineProps({ alias: { type: String, required: true }, name: { type: String, default: '' }, title: { type: String, default: '' } })
</script>

<template>
  <nav class="crumbs" aria-label="현재 위치">
    <router-link to="/mentees">내 멘티</router-link><span>›</span>
    <router-link v-if="title" :to="menteePath(alias)">{{ name || alias }}</router-link><strong v-else>{{ name || alias }}</strong>
    <template v-if="title"><span>›</span><strong>{{ title }}</strong></template>
  </nav>
</template>
