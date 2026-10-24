import { useEffect, useState, type CSSProperties } from 'react'
import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { dimensions, metricList, metricValue, signed, type Snapshot } from './types'
import { loadOverlay, subscribe } from './api'

export function RankEmblem({ tier = 0, name = 'Unranked' }: { tier?: number; name?: string }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [tier])
  return (
    <div className="rank-emblem" aria-label={name}>
      {tier >= 3 && tier <= 27 && !failed ? (
        <img src={`/ranks/${tier}.png`} alt={name} onError={() => setFailed(true)} />
      ) : (
        <svg viewBox="0 0 100 110" aria-hidden="true">
          <path
            d="M50 5 84 22 96 64 76 95 50 107 24 95 4 64 16 22Z"
            fill="currentColor"
            opacity=".22"
          />
          <path
            d="m50 16 29 14 10 32-16 25-23 11-23-11-16-25 10-32Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="5"
          />
          <path d="m50 32 23 30-23 25-23-25Z" fill="currentColor" />
        </svg>
      )}
    </div>
  )
}
export function AgentPortrait({ agentId, name }: { agentId?: string | null; name: string }) {
  const [failed, setFailed] = useState(false)
  return agentId && !failed ? (
    <img src={`/agents/${agentId}.png`} alt={name} onError={() => setFailed(true)} />
  ) : (
    <span className="agent-initial">{name.slice(0, 1)}</span>
  )
}

export function OverlayCard({ snapshot }: { snapshot: Snapshot }) {
  const { settings: settings, rank, stats } = snapshot
  const size = dimensions(settings)
  const color = settings.textColor
  const style = {
    '--ov-accent': settings.accent,
    '--ov-bg': settings.background,
    '--ov-text': color,
    '--ov-alpha': settings.opacity,
    '--ov-radius': `${settings.radius}px`,
    '--ov-glow': `${settings.glow}px`,
    width: size.width,
    height: size.height,
  } as CSSProperties
  const showBar = rank?.rr !== null && rank?.rr !== undefined && rank.tier >= 3 && rank.tier < 24
  if (settings.hideWhenOffline && !snapshot.connection.authenticated && snapshot.mode !== 'demo')
    return <div style={{ width: size.width, height: size.height }} />
  return (
    <article
      className={`overlay-card ${settings.layout} ${settings.theme}`}
      style={style}
      data-testid="overlay-card"
    >
      <div className="overlay-surface">
        {settings.layout === 'large' && (
          <div className="overlay-heading">
            <span>
              <i /> {settings.title || 'COMPETITIVE'}
            </span>
            <span>{snapshot.mode === 'demo' ? 'DEMO' : 'COMPETITIVE'}</span>
          </div>
        )}
        <div className="rank-section">
          <RankEmblem tier={rank?.tier} name={rank?.name} />
          <div className="rank-info">
            {settings.layout !== 'large' && (
              <div className="rank-eyebrow">
                {snapshot.mode === 'demo' && <span>DEMO · </span>}
                {settings.title || 'COMPETITIVE'}
              </div>
            )}
            <div className="rank-name">{rank?.name ?? 'NO DATA'}</div>
            <div className="rr-line">
              <span>{settings.layout === 'mini' ? '' : 'RR'}</span>
              <strong>
                {rank?.rr ?? '—'}
                {showBar && <small> / 100</small>}
                {!showBar && rank?.rr !== null && rank?.rr !== undefined && <small> RR</small>}
              </strong>
            </div>
            {showBar && (
              <div className="rr-track">
                <div style={{ width: `${Math.max(0, Math.min(100, rank.rr!))}%` }} />
              </div>
            )}
          </div>
        </div>
        <div
          className="overlay-metrics"
          style={{
            gridTemplateColumns: `repeat(${settings.layout === 'large' ? Math.min(3, settings.metrics.length) : settings.metrics.length}, minmax(0,1fr))`,
          }}
        >
          {settings.metrics.map((id) => (
            <div className="overlay-stat" key={id}>
              <span>{metricList.find((m) => m.id === id)?.label}</span>
              <strong>{metricValue(id, snapshot)}</strong>
            </div>
          ))}
        </div>
        {settings.layout === 'large' && (
          <div className="overlay-footer">
            <span>
              {stats.games} {stats.games === 1 ? 'MATCH' : 'MATCHES'}
            </span>
            {settings.showLastDelta && (
              <span>
                LAST MATCH{' '}
                <b className={(stats.lastDelta ?? 0) >= 0 ? 'positive' : 'negative'}>
                  {signed(stats.lastDelta)} RR
                </b>
              </span>
            )}
          </div>
        )}
      </div>
      {settings.showMatches && settings.layout !== 'mini' && (
        <div className="recent-strip">
          {snapshot.recentMatches.map((match) => (
            <div
              className={`recent-agent ${match.outcome}`}
              key={match.id}
              title={`${match.agent} · ${match.map} · ${signed(match.ratingDelta)} RR`}
            >
              <AgentPortrait agentId={match.agentId} name={match.agent} />
              <span>
                {match.outcome === 'win' ? (
                  <ArrowUpRight size={10} />
                ) : match.outcome === 'loss' ? (
                  <ArrowDownRight size={10} />
                ) : (
                  '—'
                )}
              </span>
            </div>
          ))}
          {!snapshot.recentMatches.length && <span className="recent-empty">NO MATCHES YET</span>}
        </div>
      )}
    </article>
  )
}

export function OverlayPage({ token }: { token: string }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [error, setError] = useState(false)
  const preview = new URLSearchParams(location.search).get('preview') === 'demo'
  useEffect(() => {
    document.documentElement.classList.add('overlay-document')
    let alive = true
    const accept = (value: Snapshot) => {
      if (alive) {
        setSnapshot(value)
        setError(false)
      }
    }
    void loadOverlay(token, preview)
      .then(accept)
      .catch(() => {
        if (alive) setError(true)
      })
    const unsubscribe = subscribe(token, accept, undefined, preview)
    return () => {
      alive = false
      unsubscribe()
      document.documentElement.classList.remove('overlay-document')
    }
  }, [token, preview])
  if (!snapshot)
    return error ? (
      <div className="overlay-unavailable" role="status">
        Waiting for the app…
      </div>
    ) : null
  return <OverlayCard snapshot={snapshot} />
}
