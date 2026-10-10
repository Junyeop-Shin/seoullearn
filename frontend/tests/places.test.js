import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { districts, filterPlaces, kakaoLink, loadKakao } from '../src/lib/places'

const data = JSON.parse(readFileSync(resolve(process.cwd(), '..', 'synthetic', 'places.json'), 'utf-8'))

describe('협약 장소', () => {
  it('예시 데이터는 모두 가상 표시가 있고 서울 안의 좌표다', () => {
    expect(data.sample).toBe(true)
    expect(data.places.length).toBeGreaterThan(5)
    for (const p of data.places) {
      expect(p.name.startsWith('(가상)')).toBe(true)
      expect(p.lat).toBeGreaterThan(37.4)
      expect(p.lat).toBeLessThan(37.7)
      expect(p.lng).toBeGreaterThan(126.7)
      expect(p.lng).toBeLessThan(127.2)
    }
  })

  it('임시 스터디카페 자료: 25개 자치구마다 5곳 이상이고, 임시 자료라는 안내가 있다', () => {
    const temp = JSON.parse(readFileSync(resolve(process.cwd(), '..', 'data', 'places', 'study_cafes_temp.json'), 'utf-8'))
    expect(temp.sample).toBe(true)                       // 화면이 '실제 협약 장소가 아님'을 알린다
    expect(temp.notice).toContain('실제 협약 장소가 아니')
    const ds = districts(temp.places)
    expect(ds).toHaveLength(25)
    for (const d of ds) expect(filterPlaces(temp.places, { district: d }).length, d).toBeGreaterThanOrEqual(5)
    expect(new Set(temp.places.map((x) => x.id)).size).toBe(temp.places.length)
    for (const x of temp.places) {
      expect(x.address.startsWith(`서울 ${x.district} `), x.id).toBe(true)
      expect(x.lat).toBeGreaterThan(37.4); expect(x.lat).toBeLessThan(37.72)
      expect(x.lng).toBeGreaterThan(126.75); expect(x.lng).toBeLessThan(127.2)
      expect(x.name.trim() && x.type, x.id).toBeTruthy()
      expect(x.note, x.id).toBe('')   // 임시라는 안내는 위의 notice 한 번이면 된다 (장소마다 되풀이하지 않는다)
    }
  })

  it('자치구로 거른다', () => {
    const ds = districts(data.places)
    expect(ds).toContain('마포구')
    expect(new Set(ds).size).toBe(ds.length)
    const mapo = filterPlaces(data.places, { district: '마포구' })
    expect(mapo.length).toBeGreaterThan(0)
    expect(mapo.every((p) => p.district === '마포구')).toBe(true)
    expect(filterPlaces(data.places)).toHaveLength(data.places.length)
    expect(filterPlaces(data.places, { district: '없는구' })).toEqual([])
  })

  it('카카오맵 링크에는 장소 이름과 좌표만 들어간다', () => {
    const link = kakaoLink({ name: '(가상) 마포 스터디카페', lat: 37.56, lng: 126.9 })
    expect(link).toBe(`https://map.kakao.com/link/map/${encodeURIComponent('(가상) 마포 스터디카페')},37.56,126.9`)
  })

  it('키가 없으면 지도를 불러오지 않는다', async () => {
    await expect(loadKakao('')).rejects.toThrow('지도 키가 설정되지 않았습니다.')
    expect(document.querySelector('script[src*="dapi.kakao.com"]')).toBeNull()
  })
})
