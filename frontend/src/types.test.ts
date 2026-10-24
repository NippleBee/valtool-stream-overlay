import { describe, expect, it } from 'vitest'
import { defaults, dimensions, metricValue, type Snapshot } from './types'
import fixture from './fixtures/snapshot.json'
const snapshotFixture = () => structuredClone(fixture) as Snapshot

describe('overlay contract', () => {
  it('reserves exactly the reported OBS canvas including the recent strip', () => {
    expect(dimensions(defaults)).toEqual({ width: 300, height: 178 })
    expect(dimensions({ ...defaults, showMatches: false })).toEqual({ width: 300, height: 134 })
    expect(dimensions({ ...defaults, layout: 'mini', showMatches: true })).toEqual({
      width: 220,
      height: 70,
    })
  })
  it('does not turn missing data or pending RR into zero', () => {
    const snapshot = snapshotFixture()
    snapshot.stats.lastDelta = null
    expect(metricValue('lastDelta', snapshot)).toBe('—')
    snapshot.stats.games = 0
    expect(metricValue('kd', snapshot)).toBe('—')
    expect(metricValue('leaderboard', snapshot)).toBe('—')
  })
  it('labels the K/D/A triplet separately from the KDA ratio', () => {
    const snapshot = snapshotFixture()
    expect(metricValue('kda', snapshot)).toBe('21/12/4')
    expect(metricValue('kdaRatio', snapshot)).toBe('2.08')
  })
})
