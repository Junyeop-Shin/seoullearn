// 자치구별 이음단 카카오톡 채널 (public/data/eumdan_channels.json). 이음단과는 자치구마다 다른 카카오톡 채널로 연락한다.
// 누구나 볼 수 있는 채널 주소라 화면 자료로 함께 싣고 서버로는 보내지 않는다. 주소를 받지 못한 자치구는 목록에 없다.
const CHANNEL = /^https:\/\/pf\.kakao\.com\/_[A-Za-z0-9]+$/

/** 자료에서 카카오톡 채널 주소만 남긴다 (다른 주소가 섞여 있어도 바로가기 버튼이 되지 않게). */
export const validChannels = (data) => Object.fromEntries(Object.entries(data || {}).filter(([, url]) => typeof url === 'string' && CHANNEL.test(url)))

let cache = null
/** 자치구 → 채널 주소. 못 읽으면 빈 목록 (다음에 다시 읽는다). */
export async function loadChannels() {
  if (cache) return cache
  try {
    const res = await fetch('/data/eumdan_channels.json')
    if (res.ok) cache = validChannels(await res.json())
  } catch { /* 채널 목록이 없어도 화면은 쓸 수 있다 */ }
  return cache || {}
}
