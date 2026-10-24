import { type Editor, type Match, type Settings, type Snapshot } from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: 'same-origin', ...init })
  if (!response.ok) {
    if (response.status === 401) throw new Error('Open settings from the running app.')
    let message = 'Could not save changes. Make sure the app is running.'
    try {
      message = (await response.json()).error ?? message
    } catch {
      /* An unavailable local host can return a non-JSON page. */
    }
    throw new Error(message)
  }
  return response.status === 204 || response.status === 202 ? (undefined as T) : response.json()
}
let initialEditor: Promise<Editor> | undefined
export function loadEditor(): Promise<Editor> {
  // React StrictMode may mount twice; the one-time bootstrap must be consumed once.
  return (initialEditor ??= readEditor())
}
async function readEditor(): Promise<Editor> {
  const bootstrap = new URLSearchParams(location.hash.slice(1)).get('bootstrap')
  if (bootstrap) {
    history.replaceState(null, '', location.pathname + location.search)
    await request('/api/session', {
      method: 'POST',
      headers: { Authorization: `Bearer ${bootstrap}` },
    })
  }
  return request('/api/editor')
}
export async function saveSettings(settings: Settings): Promise<Snapshot> {
  return request('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
}
export function subscribe(
  key: string,
  update: (snapshot: Snapshot) => void,
  connected?: (value: boolean) => void,
  previewDemo = false,
) {
  const events = new EventSource(
    `/api/overlay/${encodeURIComponent(key)}/events${previewDemo ? '?preview=demo' : ''}`,
  )
  events.onmessage = (event) => {
    update(JSON.parse(event.data))
    connected?.(true)
  }
  events.onerror = () => connected?.(false)
  return () => events.close()
}
export async function loadOverlay(key: string, previewDemo = false): Promise<Snapshot> {
  return request(`/api/overlay/${encodeURIComponent(key)}${previewDemo ? '?preview=demo' : ''}`)
}
export async function loadMatches(): Promise<Match[]> {
  return request('/api/matches')
}
export async function refresh() {
  await request('/api/refresh', { method: 'POST' })
}
export async function shutdown() {
  await request('/api/shutdown', { method: 'POST' })
}
