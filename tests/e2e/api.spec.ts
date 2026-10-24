import { test, expect, type APIRequestContext } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { defaults } from '../../frontend/src/types'

const origin = 'http://127.0.0.1:32149'
let editor: APIRequestContext
let output: string
let bootstrap: string
test.beforeAll(async ({ playwright }) => {
  editor = await playwright.request.newContext({
    baseURL: origin,
    extraHTTPHeaders: { Origin: origin },
  })
  bootstrap = new URL(readFileSync('.cache/editor-32149.txt', 'utf8')).hash.slice(
    '#bootstrap='.length,
  )
  expect(
    (
      await editor.post('/api/session', { headers: { Authorization: `Bearer ${bootstrap}` } })
    ).status(),
  ).toBe(204)
  output = (await (await editor.get('/api/editor')).json()).overlayUrl.replace(
    '/overlay/',
    '/api/overlay/',
  )
})
test.afterAll(async () => {
  await editor.dispose()
})
test.beforeEach(async () => {
  expect((await editor.put('/api/settings', { data: defaults })).status()).toBe(200)
})

test('embedded HTML, JS, CSS and game assets are served with correct types', async ({
  request,
}) => {
  const response = await request.get('/settings')
  expect(response.status()).toBe(200)
  const html = await response.text()
  const script = html.match(/src="([^\"]+\.js)"/)![1]
  const css = html.match(/href="([^\"]+\.css)"/)![1]
  const js = await request.get(script)
  expect(js.status()).toBe(200)
  expect(js.headers()['content-type']).toMatch(/javascript/)
  expect((await request.get(css)).headers()['content-type']).toMatch(/css/)
  expect((await request.get('/ranks/19.png')).headers()['content-type']).toBe('image/png')
  expect((await request.get('/agents/add6443a-41bd-e414-f6ad-e58d267f4e95.png')).status()).toBe(200)
  expect((await request.get('/missing.js')).status()).toBe(404)
})

test('settings, sample calculation and recent strip use independent windows', async () => {
  const result = await editor.put('/api/settings', {
    data: { ...defaults, matchCount: 1, recentCount: 5 },
  })
  const value = await result.json()
  expect(value.stats.games).toBe(1)
  expect(value.stats.kd).toBeCloseTo(21 / 12)
  expect(value.recentMatches).toHaveLength(5)
  expect((await (await editor.get('/api/editor')).json()).snapshot.settings.matchCount).toBe(1)
})

test('all available matches and weighted ACS are calculated on real service path', async () => {
  const value = await (
    await editor.put('/api/settings', { data: { ...defaults, matchCount: null } })
  ).json()
  expect(value.stats.games).toBe(100)
  expect(value.stats.isComplete).toBe(true)
  expect(value.stats.rrCovered).toBe(100)
  const matches = await (await editor.get('/api/matches')).json()
  const score = matches.reduce((sum: number, match: { score: number }) => sum + match.score, 0)
  const rounds = matches.reduce((sum: number, match: { rounds: number }) => sum + match.rounds, 0)
  expect(value.stats.acs).toBeCloseTo(score / rounds)
})

test('read-only OBS key cannot mutate settings or expose credentials', async ({ request }) => {
  expect((await request.get('/api/editor')).status()).toBe(401)
  expect((await request.get(output)).status()).toBe(200)
  expect(
    (await request.put('/api/settings', { data: defaults, headers: { Origin: origin } })).status(),
  ).toBe(401)
  expect((await request.get('/api/overlay/bad-key')).status()).toBe(404)
  expect(await (await request.get(output)).text()).not.toMatch(
    /accessToken|entitlementsToken|password|overlayKey/,
  )
})

test('origin, host and one-time bootstrap protections are enforced', async ({ request }) => {
  expect(
    (
      await editor.put('/api/settings', {
        data: defaults,
        headers: { Origin: 'https://example.com' },
      })
    ).status(),
  ).toBe(403)
  expect(
    (await request.get('/api/health', { headers: { Host: 'evil.example:32149' } })).status(),
  ).toBe(403)
  expect(
    (
      await editor.post('/api/session', { headers: { Authorization: `Bearer ${bootstrap}` } })
    ).status(),
  ).toBe(401)
})

test('invalid sizes, metric slots and CSS values are rejected without changing saved state', async () => {
  for (const patch of [
    { layout: 'mini' },
    { matchCount: 0 },
    { accent: 'url(https://example.com)' },
    { opacity: 9 },
    { metrics: ['kd', 'kd'] },
    { metrics: null },
  ])
    expect((await editor.put('/api/settings', { data: { ...defaults, ...patch } })).status()).toBe(
      400,
    )
  expect((await (await editor.get('/api/editor')).json()).snapshot.settings).toEqual(defaults)
})

test('SSE delivers an initial snapshot then a changed complete snapshot', async () => {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 5000)
  const response = await fetch(`${output}/events`, { signal: controller.signal })
  expect(response.headers.get('content-type')).toMatch(/^text\/event-stream/)
  const reader = response.body!.getReader()
  let buffer = ''
  const next = async () => {
    while (!buffer.includes('\n\n')) buffer += new TextDecoder().decode((await reader.read()).value)
    const end = buffer.indexOf('\n\n')
    const message = buffer.slice(0, end)
    buffer = buffer.slice(end + 2)
    return JSON.parse(
      message
        .split('\n')
        .find((line) => line.startsWith('data: '))!
        .slice(6),
    )
  }
  try {
    const initial = await next()
    await editor.put('/api/settings', { data: { ...defaults, title: 'SSE TEST', matchCount: 1 } })
    const updated = await next()
    expect(updated.revision).toBeGreaterThan(initial.revision)
    expect(updated.settings.title).toBe('SSE TEST')
    expect(updated.stats.games).toBe(1)
  } finally {
    clearTimeout(timer)
    await reader.cancel()
    controller.abort()
  }
})
