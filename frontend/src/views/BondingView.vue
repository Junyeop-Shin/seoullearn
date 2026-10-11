<script setup>
import { computed, reactive, ref, watch } from 'vue'
import MenteePick from '../components/MenteePick.vue'
import { BONDING_FORM, BONDING_TYPES } from '../lib/reports'
import { downloadZip, monthDay, namedZip } from '../lib/photos'
import { toast } from '../lib/toast'
import { saveItem } from '../stores/vault'

// 친화·성장활동 기록: 신청(구글폼)에 적은 내용과 결과보고서에 적은 내용을 이 브라우저에 적어 두고 다시 본다.
// 초안을 만들지 않는다 (AI 미사용, 서버로 보내지 않음). 적어 둔 내용은 완료보고서 초안을 쓸 때 참고 자료가 된다.
// 결과보고서에 내는 증빙사진 3종은 이름을 바꿔 한 파일로 압축해 준다 (공지: 하나의 파일로 압축하여 제출).
const PLAN = [['content', '활동 내용', '예: 대학 캠퍼스를 함께 둘러보고 희망 학과 건물과 도서관 방문'], ['goal', '활동 목표', '예: 희망 전공을 구체적으로 알아보고 학습 동기 높이기']]
const RESULT = [['actual', '실제 활동 내용', '실제로 한 일을 적어 주세요.'], ['mentor_note', '멘토 활동 소감', ''], ['mentee_note', '멘티 활동 소감', '']]
const SLOTS = [['start', '활동 시작 인증 사진', '장소·날짜·시각과 멘토·멘티 얼굴이 보이게'], ['content', '활동 내용 확인 사진', '활동 장면이나 결과물. 여러 장 넣을 수 있습니다'], ['end', '활동 종료 인증 사진', '장소·날짜·시각과 멘토·멘티 얼굴이 보이게']]
const LINKS = { apply: 'https://forms.gle/V4pU7Lbg9ShGNkjR8', result: 'https://forms.gle/KrGoSG4iKY8Jw4LM7' }   // 서울런 공지의 구글폼 (2026)
const mentee = ref(null)       // 고른 멘티 {alias, items, profile}
const type = ref(BONDING_TYPES[0])
const f = reactive({ date: '', time: '', content: '', goal: '', actual: '', mentor_note: '', mentee_note: '' })
const photos = reactive({ start: [], content: [], end: [] })
const error = ref('')
let savedId

// 활동 유형마다 회기에 한 번이다: 유형을 바꾸면 그 유형으로 적어 둔 기록을 연다
function open() {
  const mine = mentee.value?.items.find((x) => x.formId === BONDING_FORM && x.draft?.type === type.value)
  savedId = mine?.id
  for (const k of Object.keys(f)) f[k] = mine?.draft?.[k] || ''
  for (const k of Object.keys(photos)) photos[k] = []
}
watch([mentee, type], open)

async function save() {
  error.value = ''
  try {
    const m = mentee.value
    const item = await saveItem({ id: savedId, alias: m.alias, formId: BONDING_FORM, title: type.value, draft: { type: type.value, ...f } })
    savedId = item.id
    m.items = [item, ...m.items.filter((x) => x.id !== item.id)]
    toast(`${type.value} 기록을 저장했습니다.`)
  } catch (e) {
    error.value = e.message
  }
}

// ---- 증빙사진: '멘티이름 친화활동 10.11.zip' 안에 '활동 시작 인증 사진', '활동 내용 확인 사진 (1)', …, '활동 종료 인증 사진'
const zipName = computed(() => [mentee.value?.profile.name || mentee.value?.alias, type.value, monthDay(f.date)].filter(Boolean).join(' '))
function addPhotos(key, list) {
  const files = [...list].filter((x) => x.type.startsWith('image/'))
  if (files.length !== list.length) toast('사진 파일만 넣을 수 있습니다.')
  photos[key] = key === 'content' ? [...photos[key], ...files] : files.slice(0, 1)
}
async function download() {
  const pairs = [...photos.start.map((x) => ['활동 시작 인증 사진', x]), ...photos.content.map((x, i) => [`활동 내용 확인 사진 (${i + 1})`, x]), ...photos.end.map((x) => ['활동 종료 인증 사진', x])]
  toast(`${downloadZip(await namedZip(pairs), zipName.value)} 파일을 내려받았습니다.`)
}
</script>

<template>
  <div class="shell">
    <h1>친화·성장활동</h1>
    <p class="muted">신청서와 결과보고서는 구글폼으로 냅니다. 낸 내용을 여기에 적어 두면 다시 볼 수 있고, 완료보고서 초안을 쓸 때 참고합니다. 이 브라우저에만 저장합니다.</p>
    <div class="row">
      <a :href="LINKS.apply" target="_blank" rel="noopener noreferrer" class="linkbutton" data-test="bonding-apply">신청서 제출 (구글폼)</a>
      <a :href="LINKS.result" target="_blank" rel="noopener noreferrer" class="linkbutton" data-test="bonding-result">결과보고서 제출 (구글폼)</a>
    </div>
    <div v-if="error" class="box error">{{ error }}</div>
    <MenteePick v-model="mentee" />
    <template v-if="mentee">
    <div class="tabs" role="group" aria-label="활동 유형">
      <button v-for="t in BONDING_TYPES" :key="t" type="button" :aria-pressed="type === t" :class="{ on: type === t }" :data-type="t" @click="type = t">{{ t }}</button>
    </div>
    <p class="box ask">4회차 이상 학습 멘토링을 마친 그룹이 신청할 수 있고, 신청 전에 보호자 사전동의를 받아야 합니다. 활동 5일 전까지 신청하고 승인을 받은 뒤 진행해 주세요. 회기마다 유형별로 한 번이며 학습 멘토링과 같은 날에는 할 수 없습니다.</p>

    <form class="card plan-form" data-test="bonding-form" @submit.prevent="save">
      <h3 class="flush">신청할 때 적은 내용</h3>
      <div class="form-grid">
        <label class="field"><span class="name">활동 일자</span><input v-model="f.date" type="date" data-bond="date" /></label>
        <label class="field"><span class="name">활동 시간</span><input v-model="f.time" placeholder="예: 14:00~16:00 (2시간)" data-bond="time" /></label>
      </div>
      <label v-for="[key, label, hint] in PLAN" :key="key" class="field"><span class="name">{{ label }}</span>
        <textarea v-model="f[key]" rows="3" :placeholder="hint" :data-bond="key"></textarea></label>

      <h3>결과보고서에 적은 내용</h3>
      <p class="notice flush">활동을 마친 뒤 7일 이내에 결과보고서를 냅니다.</p>
      <label v-for="[key, label, hint] in RESULT" :key="key" class="field"><span class="name">{{ label }}</span>
        <textarea v-model="f[key]" rows="3" :placeholder="hint" :data-bond="key"></textarea></label>
      <div class="row"><button class="primary" data-test="save-bonding">저장</button></div>
    </form>

    <h2>증빙사진</h2>
    <div class="card" data-test="bonding-photos">
      <div class="photo-slots">
        <label v-for="[key, label, hint] in SLOTS" :key="key" class="drop" :class="{ on: photos[key].length }" @dragover.prevent @drop.prevent="addPhotos(key, $event.dataTransfer.files)">
          <strong>{{ label }}</strong>
          <span>{{ photos[key].length ? photos[key].map((x) => x.name).join(', ') : `${hint}. 끌어다 놓거나 눌러서 고르기` }}</span>
          <input type="file" accept="image/*" :multiple="key === 'content'" :data-photo="key" @change="addPhotos(key, $event.target.files); $event.target.value = ''" />
        </label>
      </div>
      <div class="row gap-top">
        <button type="button" :disabled="!photos.start.length || !photos.content.length || !photos.end.length" data-test="bonding-zip" @click="download">압축 파일 내려받기</button>
        <button v-if="photos.content.length" type="button" class="small" @click="photos.content = []">내용 확인 사진 비우기</button>
        <span class="notice">사진 이름을 바꿔 '{{ zipName }}.zip'으로 묶습니다. 사진은 저장하지 않고 서버로 보내지 않습니다.</span>
      </div>
    </div>
    </template>
  </div>
</template>
