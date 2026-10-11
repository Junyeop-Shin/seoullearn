<script setup>
import { computed, reactive } from 'vue'
import { COLLECTED, CONSENTS, OVERSEAS, VERSION } from '../lib/privacy'

// 회원가입 전에 알리는 것과 받는 것. 계정 정보처럼 서비스 제공에 꼭 필요한 정보는 동의를 받지 않고 알리기만 한다 (항목, 목적, 근거, 보유 기간).
// 동의는 국외 이전 하나만 따로 받고(개인정보 보호법 제22조, 제28조의8), 미리 체크해 두지 않는다. 나이 확인과 이용 수칙은 동의가 아니라 확인이다.
const emit = defineEmits(['agreed', 'cancel'])
const checked = reactive(Object.fromEntries(CONSENTS.map((c) => [c.id, false])))
const all = computed(() => CONSENTS.every((c) => checked[c.id]))
const BOLD = ['이전받는 자', '이전되는 국가', '보유·이용 기간']   // 중요한 내용은 굵게 보여 준다
</script>

<template>
  <form class="consent" data-test="consent" @submit.prevent="emit('agreed', { version: VERSION, items: CONSENTS.map((c) => c.id) })">
    <h2>가입 전 안내와 동의</h2>
    <p class="muted">꼭 필요한 정보만 받습니다. 이름, 전화번호, 학교는 받지 않습니다.</p>

    <section class="term" data-test="collect-notice">
      <strong>처리하는 개인정보 (안내)</strong>
      <p class="notice">아래 정보는 서비스를 제공하는 데 꼭 필요해 동의 없이 처리합니다.</p>
      <div class="scroll"><table class="terms">
        <thead><tr><th>항목</th><th>처리 목적</th><th>처리 근거</th><th>보유·이용 기간</th></tr></thead>
        <tbody><tr v-for="r in COLLECTED" :key="r.items"><td><strong>{{ r.items }}</strong></td><td>{{ r.purpose }}</td><td>{{ r.basis }}</td><td><strong>{{ r.period }}</strong></td></tr></tbody>
      </table></div>
      <p class="notice">비밀번호는 되돌릴 수 없게 암호화해 저장합니다. 멘토 설정(이름, 연락처, 대학교, 전공)과 멘티 정보, 작성한 문서는 이 브라우저에만 저장하고 서버로 보내지 않습니다. 탈퇴는 멘토 설정 화면에서 바로 할 수 있고, 탈퇴하면 계정 정보를 즉시 지웁니다.</p>
    </section>

    <section v-for="c in CONSENTS" :key="c.id" class="term">
      <label class="check"><input v-model="checked[c.id]" type="checkbox" required :data-consent="c.id" /><span>{{ c.label }} <span class="tag">{{ c.tag }}</span></span></label>

      <p v-if="c.id === 'age14'" class="notice">만 14세 미만은 법정대리인의 동의가 필요하지만 이 서비스에는 그 절차가 없어 가입할 수 없습니다.</p>

      <template v-else-if="c.id === 'overseas'">
        <p class="notice">답변과 초안 문장은 국외의 AI 제공사가 만듭니다. 보내기 전에 이름, 전화번호, 학교명 같은 정보를 가립니다.</p>
        <dl class="terms"><template v-for="[k, v] in OVERSEAS" :key="k"><dt>{{ k }}</dt><dd><strong v-if="BOLD.includes(k)">{{ v }}</strong><template v-else>{{ v }}</template></dd></template></dl>
        <p class="notice">동의를 거부할 권리가 있습니다. 다만 AI로 답변과 초안을 만드는 것이 이 서비스의 기능이라, 동의하지 않으면 가입할 수 없습니다.</p>
      </template>

      <p v-else-if="c.id === 'mentee'" class="notice">멘티는 미성년자입니다. 멘티의 실명, 연락처, 학교, 주소와 건강·가정 사정처럼 멘티를 알아볼 수 있거나 민감한 내용을 질문과 보고서 칸에 적지 않습니다. 적혀 있으면 가려서 보내지만 가리는 규칙이 모든 표현을 잡지는 못합니다. 멘티 이름 칸에 적은 이름은 이 브라우저에만 저장하고, 질문과 보고서에 그 이름이 나오면 보내기 전에 브라우저에서 가립니다.</p>
    </section>

    <div class="row">
      <button type="button" data-test="consent-cancel" @click="emit('cancel')">취소</button>
      <span class="grow"></span>
      <button class="primary" :disabled="!all" data-test="consent-ok">확인하고 계속</button>
    </div>
    <p class="muted switch"><a href="/privacy" target="_blank" rel="noopener">개인정보 처리방침 전문 보기</a> · 시행일 {{ VERSION }}</p>
  </form>
</template>
