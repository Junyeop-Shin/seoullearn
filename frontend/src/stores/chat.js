import { ref } from 'vue'

// 매뉴얼 질문의 대화. 탭이 열려 있는 동안만 메모리에 둔다 (저장소에도 서버에도 남기지 않는다).
// 답변의 안내 버튼으로 다른 화면에 다녀와도 방금 받은 답이 남아, 같은 질문으로 AI를 다시 부르지 않아도 된다. 로그아웃하면 비운다.
export const messages = ref([])
// 답을 기다리는 중인지와 오류도 화면이 아니라 여기에 둔다: 다른 화면에 다녀와도 입력이 잠겨 있어 질문이 겹치지 않는다
export const busy = ref(false)
export const error = ref('')

/** 대화를 비운다 (대화 지우기, 로그아웃, 탈퇴). 새 배열로 바꾸므로 기다리던 답이 늦게 와도 비운 대화에 들어가지 않는다 (ChatView의 send가 같은 배열인지 본다). */
export function clearChat() {
  messages.value = []
  busy.value = false
  error.value = ''
}
