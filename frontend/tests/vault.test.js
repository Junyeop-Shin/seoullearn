import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import { reactive } from 'vue'
import { FORMAT, clearAll, exportAll, importAll, listAliases, listItems, removeItem, saveItem } from '../src/stores/vault'

describe('브라우저 보관함', () => {
  beforeEach(clearAll)

  it('별칭별로 저장하고 불러온다', async () => {
    const a = await saveItem({ alias: ' 수학 고2 A ', formId: 'activity_report', title: '활동보고서 1회차', sessionNo: 1, draft: reactive({ goal: '지수법칙' }) })
    await saveItem({ alias: '수학 고2 A', formId: 'activity_report', title: '활동보고서 2회차', sessionNo: 2 })
    await saveItem({ alias: '영어 중2 B', formId: 'plan_initial', title: '종합계획서①' })
    expect(a.alias).toBe('수학 고2 A')
    expect(await listAliases()).toEqual(['수학 고2 A', '영어 중2 B'])
    const items = await listItems('수학 고2 A')
    expect(items).toHaveLength(2)
    expect(items.find((x) => x.sessionNo === 1).draft).toEqual({ goal: '지수법칙' })
    await removeItem(a.id)
    expect(await listItems('수학 고2 A')).toHaveLength(1)
  })

  it('별칭이나 양식이 없으면 저장하지 않는다', async () => {
    await expect(saveItem({ alias: '  ', formId: 'activity_report' })).rejects.toThrow('멘티 별칭')
    await expect(saveItem({ alias: '수학 고2 A' })).rejects.toThrow('양식')
    expect(await listItems()).toHaveLength(0)
  })

  it('파일로 내보내고 다시 가져온다', async () => {
    await saveItem({ alias: '수학 고2 A', formId: 'activity_report', title: '활동보고서 1회차', draft: { goal: '지수법칙' } })
    await saveItem({ alias: '영어 중2 B', formId: 'pre_contact', title: '사전 연락 답변', draft: { goal: '문법' } })
    const file = JSON.parse(JSON.stringify(await exportAll()))
    expect(file.format).toBe(FORMAT)
    expect(file.version).toBe(1)
    expect(file.items).toHaveLength(2)
    await clearAll()
    expect(await listItems()).toHaveLength(0)
    expect(await importAll(file)).toBe(2)
    expect(await importAll(file)).toBe(2) // 같은 파일을 다시 가져와도 늘지 않는다
    expect(await listItems()).toHaveLength(2)
  })

  it('다른 파일은 받지 않는다', async () => {
    await expect(importAll({ items: [] })).rejects.toThrow('보관함 파일이 아닙니다')
    await expect(importAll({ format: FORMAT, version: 99, items: [] })).rejects.toThrow('더 새로운 버전')
    expect(await importAll({ format: FORMAT, version: 1, items: [{ id: 'x' }, null, { id: 'ok', alias: 'A', formId: 'f' }] })).toBe(1)
  })
})
