export type Layout = 'large' | 'compact' | 'mini'
export interface Settings {
  layout: Layout
  renderScale: number
  theme: 'midnight' | 'pastel'
  accent: string
  background: string
  textColor: string
  opacity: number
  radius: number
  glow: number
  title: string
  metrics: string[]
  matchCount: number | null
  scope: 'available' | 'act'
  showMatches: boolean
  recentCount: number
  showLastDelta: boolean
  showWatermark: boolean
  hideWhenOffline: boolean
}
export interface Match {
  id: string
  startedAt: number
  seasonId: string
  queue: string
  map: string
  agent: string
  outcome: 'win' | 'loss' | 'draw' | 'unknown'
  kills: number
  deaths: number
  assists: number
  score: number
  rounds: number
  ratingDelta: number | null
  isFinal: boolean
  isRemake: boolean
  agentId?: string | null
}
export interface Rank {
  name: string
  tier: number
  rr: number | null
  leaderboard: number | null
  seasonId: string | null
  seasonName?: string | null
}
export interface Stats {
  games: number
  wins: number
  losses: number
  draws: number
  kills: number
  deaths: number
  assists: number
  kd: number | null
  kdaRatio: number | null
  acs: number | null
  winrate: number | null
  rrGain: number | null
  rrLoss: number | null
  rrNet: number | null
  lastDelta: number | null
  rrCovered: number
  requested: number | null
  available: number
  isComplete: boolean
}
export interface Snapshot {
  revision: number
  settings: Settings
  connection: {
    phase: string
    message: string
    riotClientAvailable: boolean
    valorantRunning: boolean
    authenticated: boolean
    account?: string | null
    loopState?: string | null
    updatedAt?: string | null
    error?: string | null
  }
  rank: Rank | null
  stats: Stats
  recentMatches: Match[]
  mode: 'live' | 'demo'
  loaded: number
  total: number | null
  syncing: boolean
  syncError?: string | null
}
export interface Editor {
  overlayUrl: string
  snapshot: Snapshot
  version: string
}

export const defaults: Settings = {
  layout: 'compact',
  renderScale: 2,
  theme: 'midnight',
  accent: '#c4b5fd',
  background: '#14151f',
  textColor: '#f5f5fa',
  opacity: 0.94,
  radius: 18,
  glow: 25,
  title: 'CURRENT RANK',
  metrics: ['kd', 'winsLosses', 'winrate'],
  matchCount: 20,
  scope: 'available',
  showMatches: true,
  recentCount: 5,
  showLastDelta: true,
  showWatermark: true,
  hideWhenOffline: false,
}

export const metricList = [
  { id: 'kd', label: 'K/D', description: 'Kills / deaths' },
  { id: 'kda', label: 'K/D/A', description: 'Kills / deaths / assists' },
  { id: 'kdaRatio', label: 'KDA', description: '(Kills + assists) / deaths' },
  { id: 'acs', label: 'ACS', description: 'Average combat score per round' },
  { id: 'winrate', label: 'WINRATE', description: 'Wins / all included matches' },
  { id: 'winsLosses', label: 'W/L', description: 'Wins / losses' },
  { id: 'rrGain', label: '+RR', description: 'RR gained in the selected matches' },
  { id: 'rrLoss', label: '−RR', description: 'RR lost in the selected matches' },
  { id: 'rrNet', label: 'RR NET', description: 'Net RR change in the selected matches' },
  { id: 'lastDelta', label: 'LAST RR', description: 'RR change in the latest match' },
  { id: 'leaderboard', label: 'TOP', description: 'Leaderboard position' },
]
export const limits: Record<Layout, number> = { large: 6, compact: 3, mini: 1 }
export function layoutDimensions(settings: Settings) {
  const extra = settings.showMatches && settings.layout !== 'mini' ? 44 : 0
  return settings.layout === 'large'
    ? { width: 420, height: 266 + extra }
    : settings.layout === 'compact'
      ? { width: 300, height: 134 + extra }
      : { width: 220, height: 70 }
}
export function dimensions(settings: Settings) {
  const size = layoutDimensions(settings)
  const scale = settings.renderScale ?? 2
  return { width: size.width * scale, height: size.height * scale }
}
export function signed(value: number | null) {
  return value === null ? '—' : `${value > 0 ? '+' : ''}${value}`
}
export function matchLabel(value: number) {
  return value === 1 ? 'match' : 'matches'
}
export function metricValue(id: string, snapshot: Snapshot) {
  const s = snapshot.stats
  if (!s.games && id !== 'leaderboard') return '—'
  switch (id) {
    case 'kd':
      return s.kd?.toFixed(2) ?? '—'
    case 'kda':
      return `${s.kills}/${s.deaths}/${s.assists}`
    case 'kdaRatio':
      return s.kdaRatio?.toFixed(2) ?? '—'
    case 'acs':
      return s.acs === null ? '—' : Math.round(s.acs).toString()
    case 'winrate':
      return s.winrate === null ? '—' : `${Math.round(s.winrate)}%`
    case 'winsLosses':
      return `${s.wins}/${s.losses}${s.draws ? `/${s.draws}` : ''}`
    case 'rrGain':
      return signed(s.rrGain)
    case 'rrLoss':
      return signed(s.rrLoss)
    case 'rrNet':
      return signed(s.rrNet)
    case 'lastDelta':
      return signed(s.lastDelta)
    case 'leaderboard':
      return snapshot.rank?.leaderboard ? `#${snapshot.rank.leaderboard}` : '—'
    default:
      return '—'
  }
}
