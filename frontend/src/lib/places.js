// 협약 장소 목록과 카카오맵. 장소 정보만 카카오에 전달되고 멘티·멘토 정보는 보내지 않는다.

export function districts(places) {
  return [...new Set(places.map((p) => p.district))].sort((a, b) => a.localeCompare(b, 'ko'))
}

export function filterPlaces(places, { district = '' } = {}) {
  return places.filter((p) => !district || p.district === district)
}

/** 카카오맵에서 이 위치를 여는 주소 (키 없이도 열린다). */
export function kakaoLink(place) {
  return `https://map.kakao.com/link/map/${encodeURIComponent(place.name)},${place.lat},${place.lng}`
}

let sdk = null
/** 카카오맵 SDK를 한 번만 불러온다. 키가 없거나 불러오지 못하면 거절한다. */
export function loadKakao(key) {
  if (!key) return Promise.reject(new Error('지금은 지도를 보여 드릴 수 없습니다.'))
  if (window.kakao?.maps?.LatLng) return Promise.resolve(window.kakao)
  if (!sdk) {
    sdk = new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(key)}&autoload=false`
      s.onload = () => {
        if (!window.kakao?.maps) return (sdk = null), reject(new Error('지도를 불러오지 못했습니다.'))
        window.kakao.maps.load(() => resolve(window.kakao))
      }
      s.onerror = () => {
        sdk = null
        reject(new Error('지도를 불러오지 못했습니다.'))
      }
      document.head.appendChild(s)
    })
  }
  return sdk
}
