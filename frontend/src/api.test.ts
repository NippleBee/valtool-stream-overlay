// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'

afterEach(() => vi.unstubAllGlobals())
it('consumes the editor bootstrap once when StrictMode initializes twice', async () => {
  vi.resetModules()
  history.replaceState(null, '', '/settings#bootstrap=once-only')
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(new Response(null, { status: 204 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ version: 'test' }), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  const { loadEditor } = await import('./api')
  const [first, second] = await Promise.all([loadEditor(), loadEditor()])
  expect(first).toEqual(second)
  expect(fetchMock).toHaveBeenCalledTimes(2)
  expect(fetchMock.mock.calls.filter((call) => call[0] === '/api/session')).toHaveLength(1)
  expect(location.hash).toBe('')
})
