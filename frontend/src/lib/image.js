// 이미지를 서버로 보내기 전에 브라우저에서 줄인다. 앞단의 요청 한도(1MB) 안에 들어가야 하고, 글자를 읽는 데는 큰 이미지가 필요 없다.
export const MAX_DATA_URL = 900_000   // 서버의 한도(950,000자)보다 조금 작게

/** 이미지 파일 → JPEG data URL. 긴 쪽을 max 픽셀로 줄이고, 그래도 크면 화질을 낮춘다. 끝내 못 맞추면 오류. */
export async function shrinkImage(file, max = 1800) {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, max / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#fff'   // 투명한 PNG가 검게 바뀌지 않게
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  for (const quality of [0.85, 0.7, 0.5]) {
    const url = canvas.toDataURL('image/jpeg', quality)
    if (url.length <= MAX_DATA_URL) return url
  }
  if (max > 1000) return shrinkImage(file, 1000)
  throw new Error('이미지가 너무 큽니다. 강의 목록 부분만 잘라서 올려 주세요.')
}
