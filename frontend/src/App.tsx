import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import {
  Activity,
  ArrowDown,
  ArrowUp,
  ArrowUpRight,
  Check,
  ChevronDown,
  CircleHelp,
  Clipboard,
  Copy,
  Download,
  ExternalLink,
  Eye,
  Code2,
  Layers3,
  LayoutDashboard,
  Monitor,
  Paintbrush,
  Plus,
  Radio,
  RefreshCw,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Upload,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import * as api from './api'
import {
  dimensions,
  limits,
  matchLabel,
  metricList,
  signed,
  type Editor,
  type Match,
  type Settings,
  type Snapshot,
} from './types'
import { AgentPortrait, RankEmblem } from './Overlay'

type Category = 'appearance' | 'metrics' | 'data'
function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled = false,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  label: string
  description?: string
  disabled?: boolean
}) {
  return (
    <label className={`toggle-row ${disabled ? 'disabled' : ''}`}>
      <span>
        <strong>{label}</strong>
        {description && <small>{description}</small>}
      </span>
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
      />
      <span className="switch-track" aria-hidden="true" />
    </label>
  )
}
function Field({
  title,
  children,
  trailing,
}: {
  title: string
  children: ReactNode
  trailing?: ReactNode
}) {
  return (
    <div className="field">
      <div className="field-heading">
        <label>{title}</label>
        {trailing}
      </div>
      {children}
    </div>
  )
}
function Slider({
  title,
  value,
  min = 0,
  max,
  unit = '',
  onChange,
}: {
  title: string
  value: number
  min?: number
  max: number
  unit?: string
  onChange: (value: number) => void
}) {
  return (
    <Field
      title={title}
      trailing={
        <span className="field-value">
          {value}
          {unit}
        </span>
      }
    >
      <input
        type="range"
        aria-label={title}
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ '--range': `${((value - min) / (max - min)) * 100}%` } as CSSProperties}
      />
    </Field>
  )
}
const presets = ['#c4b5fd', '#ff677e', '#83d9ca', '#a6d9fa', '#f1c38c', '#e9a9d5']

export function App() {
  const [editor, setEditor] = useState<Editor | null>(null)
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loadError, setLoadError] = useState('')
  const [category, setCategory] = useState<Category>('appearance')
  const [page, setPage] = useState<'editor' | 'matches' | 'connection'>('editor')
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'error'>('saved')
  const [saveError, setSaveError] = useState('')
  const [demoPreview, setDemoPreview] = useState(false)
  const [backdrop, setBackdrop] = useState<'checker' | 'scene'>('checker')
  const [zoom, setZoom] = useState(1.25)
  const [hostConnected, setHostConnected] = useState(true)
  const [toast, setToast] = useState('')
  const [guide, setGuide] = useState(false)
  const [matches, setMatches] = useState<Match[]>([])
  const [matchesError, setMatchesError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const queue = useRef<Promise<unknown>>(Promise.resolve())
  const generation = useRef(0)
  const fileInput = useRef<HTMLInputElement>(null)
  const settingsRef = useRef<Settings | null>(null)
  const previewStage = useRef<HTMLDivElement>(null)
  const [previewSize, setPreviewSize] = useState({ width: 600, height: 389 })

  useEffect(() => {
    let alive = true
    void api
      .loadEditor()
      .then((value) => {
        if (!alive) return
        setEditor(value)
        setSnapshot(value.snapshot)
        setSettings(value.snapshot.settings)
        settingsRef.current = value.snapshot.settings
        setDemoPreview(value.snapshot.rank === null || value.snapshot.mode === 'demo')
      })
      .catch((error) => {
        if (alive) setLoadError(error.message)
      })
    return () => {
      alive = false
      clearTimeout(timer.current)
    }
  }, [])
  useEffect(() => {
    if (!editor) return
    const key = new URL(editor.overlayUrl).pathname.split('/').pop()!
    return api.subscribe(key, setSnapshot, setHostConnected)
  }, [editor])
  useEffect(() => {
    const element = previewStage.current
    if (!element) return
    const observer = new ResizeObserver((entries) => {
      const bounds = entries[0].contentRect
      setPreviewSize({ width: bounds.width, height: bounds.height })
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [editor, page])
  useEffect(() => {
    if (toast) {
      const id = setTimeout(() => setToast(''), 4200)
      return () => clearTimeout(id)
    }
  }, [toast])
  useEffect(() => {
    if (!guide) return
    const previous = document.activeElement as HTMLElement | null
    const oldOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.querySelector<HTMLButtonElement>('.modal-close')?.focus()
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setGuide(false)
      if (event.key !== 'Tab') return
      const items = [
        ...document.querySelectorAll<HTMLElement>(
          '.guide-modal button:not(:disabled), .guide-modal a[href]',
        ),
      ]
      const first = items[0],
        last = items.at(-1)
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last?.focus()
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first?.focus()
      }
    }
    window.addEventListener('keydown', keyboard)
    return () => {
      window.removeEventListener('keydown', keyboard)
      document.body.style.overflow = oldOverflow
      previous?.focus()
    }
  }, [guide])
  useEffect(() => {
    if (page !== 'matches') return
    let alive = true
    void api
      .loadMatches()
      .then((value) => {
        if (alive) {
          setMatches(value)
          setMatchesError('')
        }
      })
      .catch((error) => {
        if (alive) setMatchesError(error.message)
      })
    return () => {
      alive = false
    }
  }, [page, snapshot?.revision])

  const update = useCallback((patch: Partial<Settings>) => {
    const previous = settingsRef.current
    if (previous) {
      const next = { ...previous, ...patch }
      settingsRef.current = next
      setSettings(next)
      const current = ++generation.current
      setSaveStatus('saving')
      setSaveError('')
      clearTimeout(timer.current)
      timer.current = setTimeout(() => {
        queue.current = queue.current
          .catch(() => undefined)
          .then(async () => {
            if (current !== generation.current) return
            try {
              const result = await api.saveSettings(next)
              if (current === generation.current) {
                setSnapshot(result)
                setSaveStatus('saved')
              }
            } catch (error) {
              if (current === generation.current) {
                setSaveStatus('error')
                setSaveError(error instanceof Error ? error.message : 'Could not save settings')
              }
            }
          })
      }, 250)
    }
  }, [])
  async function copy(value: string, message: string) {
    try {
      await navigator.clipboard.writeText(value)
      setToast(message)
    } catch {
      setToast('Clipboard access was blocked. Select and copy the URL manually.')
    }
  }
  async function refreshData() {
    setRefreshing(true)
    try {
      await api.refresh()
      setToast('Statistics refresh requested')
    } catch (error) {
      setToast((error as Error).message)
    } finally {
      setRefreshing(false)
    }
  }
  function exportPreset() {
    if (!settings) return
    const preset = settings
    const blob = new Blob(
      [
        JSON.stringify(
          { schemaVersion: 1, name: 'My ValTool Stream Overlay', settings: preset },
          null,
          2,
        ),
      ],
      { type: 'application/json' },
    )
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'valtool-overlay.json'
    link.click()
    URL.revokeObjectURL(url)
    setToast('Preset exported')
  }
  async function importPreset(file?: File) {
    if (!file || !settings) return
    try {
      if (file.size > 16000) throw new Error('Preset file is too large')
      const data = JSON.parse(await file.text())
      const value = data.settings
      if (
        data.schemaVersion !== 1 ||
        !value ||
        !['large', 'compact', 'mini'].includes(value.layout) ||
        !['midnight', 'pastel'].includes(value.theme) ||
        !Array.isArray(value.metrics) ||
        value.metrics.length < 1 ||
        value.metrics.length > limits[value.layout as keyof typeof limits] ||
        value.metrics.some((id: string) => !metricList.some((m) => m.id === id)) ||
        new Set(value.metrics).size !== value.metrics.length ||
        ['accent', 'background', 'textColor'].some(
          (key) => !/^#[a-f0-9]{6}$/i.test(value[key] ?? ''),
        ) ||
        typeof value.opacity !== 'number' ||
        value.opacity < 0 ||
        value.opacity > 1 ||
        typeof value.radius !== 'number' ||
        value.radius < 0 ||
        value.radius > 36 ||
        typeof value.glow !== 'number' ||
        value.glow < 0 ||
        value.glow > 60 ||
        typeof value.title !== 'string' ||
        value.title.length > 40 ||
        (value.matchCount !== null &&
          (!Number.isInteger(value.matchCount) ||
            value.matchCount < 1 ||
            value.matchCount > 100000)) ||
        !['act', 'available'].includes(value.scope) ||
        !Number.isInteger(value.recentCount) ||
        value.recentCount < 1 ||
        value.recentCount > 10 ||
        ['showMatches', 'showLastDelta', 'hideWhenOffline'].some(
          (key) => typeof value[key] !== 'boolean',
        )
      )
        throw new Error('Invalid preset format')
      const { autoStart: _legacyAutoStart, ...preset } = value
      update(preset)
      setToast('Preset imported')
    } catch (error) {
      setToast(error instanceof Error ? error.message : 'Could not import preset')
    }
    if (fileInput.current) fileInput.current.value = ''
  }

  if (!editor || !snapshot || !settings)
    return (
      <div className="startup">
        <img className="brand-logo" src="/logo.svg" alt="ValTool Stream Overlay" />
        {loadError ? (
          <>
            <h1>Open ValTool Stream Overlay</h1>
            <p>{loadError}</p>
            <button className="button" onClick={() => location.reload()}>
              <RefreshCw size={15} />
              Retry
            </button>
          </>
        ) : (
          <>
            <div className="loading-line" />
            <p>Opening ValTool Stream Overlay…</p>
          </>
        )}
      </div>
    )

  const size = dimensions(settings)
  const previewZoom = Math.max(
    0.1,
    Math.min(zoom, (previewSize.width - 48) / size.width, (previewSize.height - 90) / size.height),
  )
  const overlayPath = new URL(editor.overlayUrl).pathname
  const connection = snapshot.connection
  const isConnected = connection.authenticated && hostConnected
  const liveKey = new URL(editor.overlayUrl).pathname.split('/').pop()!
  const capacity = limits[settings.layout]
  const statusLabel =
    snapshot.mode === 'demo' ? 'Demo mode' : isConnected ? 'Connected' : 'Waiting for connection'

  const appearance = (
    <>
      <Field title="Layout" trailing={<span className="muted text-xs">3 sizes</span>}>
        <div className="layout-options">
          {(['large', 'compact', 'mini'] as const).map((layout) => (
            <button
              key={layout}
              aria-pressed={settings.layout === layout}
              className={`layout-choice ${settings.layout === layout ? 'selected' : ''}`}
              onClick={() => update({ layout, metrics: settings.metrics.slice(0, limits[layout]) })}
            >
              <span className={`layout-icon ${layout}`}>
                <i />
                <i />
                <i />
              </span>
              <span>
                {layout === 'large' ? 'Large' : layout === 'compact' ? 'Compact' : 'Mini'}
              </span>
              {settings.layout === layout && <Check size={11} />}
            </button>
          ))}
        </div>
      </Field>
      <Field title="Theme">
        <div className="theme-options">
          {(['midnight', 'pastel'] as const).map((theme) => (
            <button
              key={theme}
              aria-pressed={settings.theme === theme}
              className={`theme-choice ${theme} ${settings.theme === theme ? 'selected' : ''}`}
              onClick={() =>
                update({
                  theme,
                  background: theme === 'pastel' ? '#d6b4d0' : '#14151f',
                  accent: theme === 'pastel' ? '#a779a1' : '#c4b5fd',
                  textColor: theme === 'pastel' ? '#664d68' : '#f5f5fa',
                })
              }
            >
              <span className="theme-sample">
                <i />
                <b />
                <small />
              </span>
              <span>{theme === 'midnight' ? 'Midnight' : 'Pastel'}</span>
              {settings.theme === theme && <Check size={12} />}
            </button>
          ))}
        </div>
      </Field>
      <Field
        title="Accent color"
        trailing={<span className="field-value uppercase">{settings.accent}</span>}
      >
        <div className="color-swatches">
          {presets.map((color) => (
            <button
              key={color}
              style={{ background: color }}
              aria-label={`Color ${color}`}
              aria-pressed={settings.accent.toLowerCase() === color}
              className={settings.accent.toLowerCase() === color ? 'active' : ''}
              onClick={() => update({ accent: color })}
            >
              {settings.accent.toLowerCase() === color && <Check size={14} />}
            </button>
          ))}
          <label className="custom-color" title="Custom color">
            <Plus size={15} />
            <input
              type="color"
              aria-label="Custom accent color"
              value={settings.accent}
              onChange={(e) => update({ accent: e.target.value })}
            />
          </label>
        </div>
      </Field>
      <div className="color-fields">
        <label>
          Background{' '}
          <span>
            <input
              type="color"
              aria-label="Background color"
              value={settings.background}
              onChange={(e) => update({ background: e.target.value })}
            />
            {settings.background.toUpperCase()}
          </span>
        </label>
        <label>
          Text{' '}
          <span>
            <input
              type="color"
              aria-label="Text color"
              value={settings.textColor}
              onChange={(e) => update({ textColor: e.target.value })}
            />
            {settings.textColor.toUpperCase()}
          </span>
        </label>
      </div>
      <Slider
        title="Background opacity"
        value={Math.round(settings.opacity * 100)}
        max={100}
        unit="%"
        onChange={(value) => update({ opacity: value / 100 })}
      />
      <Slider
        title="Corner radius"
        value={settings.radius}
        max={36}
        unit=" px"
        onChange={(radius) => update({ radius })}
      />
      <Slider
        title="Glow"
        value={settings.glow}
        max={60}
        unit=" px"
        onChange={(glow) => update({ glow })}
      />
      <Field title="Title">
        <input
          aria-label="Overlay title"
          maxLength={40}
          value={settings.title}
          onChange={(e) => update({ title: e.target.value })}
        />
      </Field>
    </>
  )
  const metrics = (
    <>
      <div className="section-note">
        <SlidersHorizontal size={15} />
        <span>Choose up to {capacity} metrics. Use the arrows to reorder them.</span>
      </div>
      <div className="metric-options">
        {metricList.map((metric) => {
          const index = settings.metrics.indexOf(metric.id)
          const enabled = index !== -1
          return (
            <div className={`metric-option ${enabled ? 'enabled' : ''}`} key={metric.id}>
              <label>
                <input
                  type="checkbox"
                  checked={enabled}
                  disabled={
                    (!enabled && settings.metrics.length >= capacity) ||
                    (enabled && settings.metrics.length === 1)
                  }
                  onChange={() =>
                    update({
                      metrics: enabled
                        ? settings.metrics.filter((id) => id !== metric.id)
                        : [...settings.metrics, metric.id],
                    })
                  }
                />
                <span>
                  <b>{metric.label}</b>
                  <small>{metric.description}</small>
                </span>
              </label>
              {enabled && (
                <div className="order-buttons">
                  <button
                    aria-label={`Move ${metric.label} up`}
                    disabled={index === 0}
                    onClick={() => {
                      const next = [...settings.metrics]
                      ;[next[index - 1], next[index]] = [next[index], next[index - 1]]
                      update({ metrics: next })
                    }}
                  >
                    <ArrowUp size={12} />
                  </button>
                  <button
                    aria-label={`Move ${metric.label} down`}
                    disabled={index === settings.metrics.length - 1}
                    onClick={() => {
                      const next = [...settings.metrics]
                      ;[next[index + 1], next[index]] = [next[index], next[index + 1]]
                      update({ metrics: next })
                    }}
                  >
                    <ArrowDown size={12} />
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>
      <Toggle
        label="Last match RR"
        description="Shown at the bottom of the large layout"
        checked={settings.showLastDelta}
        disabled={settings.layout !== 'large'}
        onChange={(showLastDelta) => update({ showLastDelta })}
      />
    </>
  )
  const data = (
    <>
      <Field title="Matches to include">
        <div className="match-presets">
          {[1, 5, 10, 20, 50, 100, null].map((count) => (
            <button
              key={count ?? 'all'}
              className={settings.matchCount === count ? 'selected' : ''}
              onClick={() => update({ matchCount: count })}
            >
              {count ?? 'All'}
            </button>
          ))}
        </div>
        <div className="custom-count">
          <label htmlFor="match-count">Custom count</label>
          <input
            id="match-count"
            type="number"
            min={1}
            max={100000}
            placeholder="All"
            value={settings.matchCount ?? ''}
            onChange={(e) => {
              const count = Number(e.target.value)
              if (Number.isInteger(count) && count >= 1 && count <= 100000)
                update({ matchCount: count })
            }}
          />
        </div>
      </Field>
      <Field title="Period">
        <div className="select-wrap">
          <select
            aria-label="Statistics period"
            value={settings.scope}
            onChange={(e) => update({ scope: e.target.value as Settings['scope'] })}
          >
            <option value="available">All available history</option>
            <option value="act">Current act</option>
          </select>
          <ChevronDown size={14} />
        </div>
      </Field>
      <div className="data-coverage">
        <Activity size={16} />
        <div>
          <strong>
            {snapshot.stats.games} {matchLabel(snapshot.stats.games)} included
          </strong>
          <span>
            {snapshot.syncing
              ? `Loading: ${snapshot.loaded}${snapshot.total ? ` of ${snapshot.total}` : ''}`
              : `${snapshot.stats.available} available in cache`}
          </span>
          {snapshot.stats.rrCovered < snapshot.stats.games && (
            <span>
              RR available for {snapshot.stats.rrCovered}/{snapshot.stats.games}
            </span>
          )}
        </div>
        {snapshot.syncing && <RefreshCw size={13} className="animate-spin" />}
      </div>
      <p className="help-text">
        “All” includes server-accessible history and locally cached matches. Draws are counted
        separately; remakes and unfinished matches are excluded.
      </p>
      <div className="divider" />
      <Toggle
        label="Recent matches"
        description="Agent strip below the card"
        checked={settings.showMatches}
        disabled={settings.layout === 'mini'}
        onChange={(showMatches) => update({ showMatches })}
      />
      <Slider
        title="Matches in strip"
        value={settings.recentCount}
        min={1}
        max={10}
        onChange={(recentCount) => update({ recentCount })}
      />
      <p className="help-text">The strip length does not change the statistics window.</p>
      <div className="divider" />
      <Toggle
        label="Hide when disconnected"
        description="Otherwise, keep the last available statistics"
        checked={settings.hideWhenOffline}
        onChange={(hideWhenOffline) => update({ hideWhenOffline })}
      />
    </>
  )

  return (
    <div className="studio-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="/settings"
          onClick={(e) => {
            e.preventDefault()
            setPage('editor')
          }}
        >
          <img className="brand-logo" src="/logo.svg" alt="ValTool Stream Overlay" />
          <span>
            VALTOOL<small>STREAM OVERLAY</small>
          </span>
          <span className="beta-label">BETA</span>
        </a>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          <button className={page === 'editor' ? 'active' : ''} onClick={() => setPage('editor')}>
            <LayoutDashboard size={17} />
            Overlay editor
            <span className="nav-indicator" />
          </button>
          <button className={page === 'matches' ? 'active' : ''} onClick={() => setPage('matches')}>
            <Activity size={17} />
            Match history
          </button>
          <button
            className={page === 'connection' ? 'active' : ''}
            onClick={() => setPage('connection')}
          >
            <Radio size={17} />
            Connection
          </button>
        </nav>
        <div className="sidebar-tip">
          <span className="tip-icon">
            <Sparkles size={17} />
          </span>
          <strong>Your stream. Your style.</strong>
          <p>Choose your metrics and make the overlay your own.</p>
          <button
            onClick={() => {
              setPage('editor')
              setCategory('appearance')
            }}
          >
            Customize appearance <ArrowUpRight size={13} />
          </button>
        </div>
        <div className="sidebar-bottom">
          <button onClick={() => setGuide(true)}>
            <CircleHelp size={16} />
            Add to OBS <ExternalLink size={12} />
          </button>
          <a
            href="https://github.com/NippleBee/valtool-stream-overlay"
            target="_blank"
            rel="noreferrer"
          >
            <Code2 size={16} />
            Open source <span>v{editor.version}</span>
          </a>
          <div className="local-note">
            <ShieldCheck size={13} />
            <span>Your data stays on your PC</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>ValTool Stream Overlay</span>
            <span>/</span>
            <strong>
              {page === 'editor'
                ? 'Overlay editor'
                : page === 'matches'
                  ? 'Match history'
                  : 'Connection'}
            </strong>
          </div>
          <div className="topbar-right">
            <span className={`local-badge ${!hostConnected ? 'disconnected' : ''}`}>
              <i />
              {hostConnected ? 'Local server' : 'Reconnecting'}
            </span>
            <button className="account-chip" onClick={() => setPage('connection')}>
              <span className="account-avatar">{connection.account?.[0] ?? 'V'}</span>
              <span>{connection.account ?? 'Local profile'}</span>
              <ChevronDown size={13} />
            </button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">MADE FOR YOUR STREAM</div>
              <h1>
                {page === 'editor'
                  ? 'Your overlay, your style.'
                  : page === 'matches'
                    ? 'Every match matters.'
                    : 'Start with a connection.'}
              </h1>
              <p>
                {page === 'editor'
                  ? 'Choose your appearance and metrics. Everything else updates automatically.'
                  : page === 'matches'
                    ? 'Match details from your local cache. History loads after connecting to Riot.'
                    : 'Check the app status and your connection to VALORANT.'}
              </p>
            </div>
            <button
              className="button secondary refresh-button"
              disabled={refreshing}
              onClick={refreshData}
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh data
            </button>
          </div>
          {!hostConnected && (
            <div className="notice warning">
              <Radio size={16} />
              Connection to the local app was lost. Reconnecting automatically.
            </div>
          )}
          {saveError && (
            <div className="notice error">
              {saveError}
              <button onClick={() => update({ ...settings })}>Retry saving</button>
            </div>
          )}
          {page === 'editor' ? (
            <>
              <div className="editor-grid">
                <section className="settings-panel panel">
                  <div className="panel-heading">
                    <div>
                      <Settings2 size={16} />
                      <h2>Overlay settings</h2>
                    </div>
                    <span className={`save-state ${saveStatus}`}>
                      {saveStatus === 'saving' ? (
                        <>
                          <span className="saving-dot" />
                          Saving
                        </>
                      ) : saveStatus === 'error' ? (
                        'Not saved'
                      ) : (
                        <>
                          <Check size={12} />
                          Saved
                        </>
                      )}
                    </span>
                  </div>
                  <div className="category-tabs" role="tablist" aria-label="Settings sections">
                    {(
                      [
                        { id: 'appearance', label: 'Appearance', Icon: Paintbrush },
                        { id: 'metrics', label: 'Metrics', Icon: SlidersHorizontal },
                        { id: 'data', label: 'Data', Icon: Layers3 },
                      ] as const
                    ).map((item) => (
                      <button
                        role="tab"
                        aria-selected={category === item.id}
                        className={category === item.id ? 'active' : ''}
                        key={item.id}
                        onClick={() => setCategory(item.id)}
                      >
                        <item.Icon size={13} />
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <div className="settings-content">
                    {category === 'appearance'
                      ? appearance
                      : category === 'metrics'
                        ? metrics
                        : data}
                  </div>
                  <div className="preset-actions">
                    <button onClick={exportPreset}>
                      <Download size={13} />
                      Export preset
                    </button>
                    <button onClick={() => fileInput.current?.click()}>
                      <Upload size={13} />
                      Import
                    </button>
                    <input
                      ref={fileInput}
                      type="file"
                      accept=".json,application/json"
                      hidden
                      onChange={(e) => {
                        void importPreset(e.target.files?.[0])
                      }}
                    />
                  </div>
                </section>
                <div className="preview-column">
                  <section className="preview-panel panel">
                    <div className="panel-heading">
                      <div>
                        <Eye size={16} />
                        <h2>Live preview</h2>
                      </div>
                      <span className="preview-label">
                        <i />
                        {demoPreview || snapshot.mode === 'demo' ? 'Demo data' : 'Live data'}
                      </span>
                    </div>
                    <div ref={previewStage} className={`preview-stage ${backdrop}`}>
                      <div className="preview-corner top-left" />
                      <div className="preview-corner top-right" />
                      <div className="preview-corner bottom-left" />
                      <div className="preview-corner bottom-right" />
                      <div className="preview-measure">
                        {size.width} × {size.height} px
                      </div>
                      <div
                        className="iframe-frame"
                        style={{
                          width: size.width * previewZoom,
                          height: size.height * previewZoom,
                        }}
                      >
                        <iframe
                          title="Overlay preview"
                          src={`${overlayPath}${demoPreview ? '?preview=demo' : ''}`}
                          width={size.width}
                          height={size.height}
                          style={{
                            width: size.width,
                            height: size.height,
                            transform: `scale(${previewZoom})`,
                            left: 0,
                            top: 0,
                          }}
                        />
                      </div>
                      <div className="preview-caption">
                        {snapshot.mode === 'demo'
                          ? 'Demo mode · preview and OBS use sample data'
                          : demoPreview
                            ? 'Sample appearance · the OBS URL uses live data'
                            : 'The same page that OBS displays'}
                      </div>
                    </div>
                    <div className="preview-toolbar">
                      <div className="backdrop-buttons">
                        <button
                          aria-label="Transparent preview background"
                          aria-pressed={backdrop === 'checker'}
                          className={backdrop === 'checker' ? 'active' : ''}
                          onClick={() => setBackdrop('checker')}
                        >
                          <span className="checker-icon" />
                        </button>
                        <button
                          aria-label="Scene background"
                          aria-pressed={backdrop === 'scene'}
                          className={backdrop === 'scene' ? 'active' : ''}
                          onClick={() => setBackdrop('scene')}
                        >
                          <Monitor size={14} />
                        </button>
                        <span>Preview background</span>
                      </div>
                      <div className="zoom-controls">
                        <button
                          aria-label="Zoom out"
                          disabled={zoom <= 0.75}
                          onClick={() => setZoom((z) => Math.max(0.75, z - 0.25))}
                        >
                          <ZoomOut size={14} />
                        </button>
                        <span>{Math.round(previewZoom * 100)}%</span>
                        <button
                          aria-label="Zoom in"
                          disabled={zoom >= 1.5}
                          onClick={() => setZoom((z) => Math.min(1.5, z + 0.25))}
                        >
                          <ZoomIn size={14} />
                        </button>
                      </div>
                    </div>
                    <div className="preview-demo-toggle">
                      <Toggle
                        label="Show sample data in preview"
                        description={
                          snapshot.mode === 'demo'
                            ? 'The app is running with sample statistics'
                            : 'This does not affect your OBS source'
                        }
                        checked={demoPreview}
                        disabled={snapshot.mode === 'demo'}
                        onChange={setDemoPreview}
                      />
                    </div>
                  </section>
                  <section className="obs-panel panel">
                    <div className="obs-heading">
                      <div className="obs-icon">
                        <Radio size={21} />
                      </div>
                      <div>
                        <h2>Add to OBS</h2>
                        <p>Connect once. Updates happen automatically.</p>
                      </div>
                      <span className="browser-source-label">BROWSER SOURCE</span>
                    </div>
                    <div className="url-row">
                      <span className="url-icon">
                        <Clipboard size={15} />
                      </span>
                      <input aria-label="OBS URL" readOnly value={editor.overlayUrl} />
                      <button
                        className="button primary"
                        onClick={() => {
                          void copy(editor.overlayUrl, 'OBS URL copied')
                        }}
                      >
                        <Copy size={14} />
                        Copy
                      </button>
                    </div>
                    <div className="obs-footer">
                      <span>
                        Source size:{' '}
                        <b>
                          {size.width} × {size.height}
                        </b>
                        <button
                          aria-label="Copy dimensions"
                          onClick={() => {
                            void copy(`${size.width} × ${size.height}`, 'Dimensions copied')
                          }}
                        >
                          <Copy size={11} />
                        </button>
                      </span>
                      <button onClick={() => setGuide(true)}>
                        Setup guide <ArrowUpRight size={13} />
                      </button>
                    </div>
                  </section>
                  <div className="under-preview">
                    <ShieldCheck size={14} />
                    <p>The overlay runs locally. Riot passwords and tokens never reach OBS.</p>
                  </div>
                </div>
              </div>
              <div className="connection-strip">
                <span className={`connection-dot ${isConnected ? 'connected' : ''}`} />
                <strong>{statusLabel}</strong>
                <span>{connection.message}</span>
                <button onClick={() => setPage('connection')}>
                  Details <ArrowUpRight size={12} />
                </button>
              </div>
            </>
          ) : page === 'connection' ? (
            <section className="connection-page panel">
              <div className="connection-hero">
                <div className="connection-symbol">
                  <Radio size={30} />
                </div>
                <span className="eyebrow">CONNECTION STATUS</span>
                <h2>{statusLabel}</h2>
                <p>{connection.message}</p>
              </div>
              <div className="connection-checks">
                {[
                  ['Local server', hostConnected ? 'Running' : 'Unavailable'],
                  ['Riot Client', connection.riotClientAvailable ? 'Detected' : 'Waiting'],
                  ['VALORANT', connection.valorantRunning ? 'Running' : 'Not running'],
                  ['Authentication', connection.authenticated ? 'Connected' : 'No active session'],
                  [
                    'Last updated',
                    connection.updatedAt
                      ? new Date(connection.updatedAt).toLocaleString('en-US')
                      : 'Not yet',
                  ],
                ].map(([label, value]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>
              {connection.error && <div className="notice warning">{connection.error}</div>}
              <p className="help-text">
                The app uses your local Riot Client session. No password sign-in is needed in
                ValTool Stream Overlay. Use the demo preview to customize your overlay without the
                game.
              </p>
              <button
                className="button secondary"
                onClick={() => {
                  setPage('editor')
                  setDemoPreview(true)
                }}
              >
                <Eye size={14} />
                Open demo preview
              </button>
              {
                <div className="mt-6 border-t border-studio-border pt-5">
                  <button
                    className="button secondary"
                    disabled={!hostConnected}
                    onClick={() => {
                      void api
                        .shutdown()
                        .then(() => setHostConnected(false))
                        .catch((error) => setToast(error.message))
                    }}
                  >
                    Stop local server
                  </button>
                  <p className="help-text">
                    OBS updates will stop. Launch the app again to restart the server.
                  </p>
                </div>
              }
            </section>
          ) : (
            <section className="matches-page panel">
              <div className="panel-heading">
                <div>
                  <Activity size={16} />
                  <h2>Recent matches</h2>
                </div>
                <span className="muted text-xs">
                  {matches.length} cached{snapshot.mode === 'demo' ? ' · demo' : ''}
                </span>
              </div>
              {matchesError ? (
                <div className="empty-state">
                  <p>{matchesError}</p>
                </div>
              ) : matches.length ? (
                <>
                  <div className="match-table-header">
                    <span>Match</span>
                    <span>Result</span>
                    <span>K/D/A</span>
                    <span>ACS</span>
                    <span>RR</span>
                  </div>
                  {matches.slice(0, 100).map((match) => (
                    <div className="match-table-row" key={match.id}>
                      <div className="match-identity">
                        <div className={`match-avatar ${match.outcome}`}>
                          <AgentPortrait agentId={match.agentId} name={match.agent} />
                        </div>
                        <span>
                          <b>{match.map}</b>
                          <small>
                            {match.agent} · {new Date(match.startedAt).toLocaleDateString('en-US')}
                          </small>
                        </span>
                      </div>
                      <span className={`match-result ${match.outcome}`}>
                        {match.outcome === 'win'
                          ? 'Win'
                          : match.outcome === 'loss'
                            ? 'Loss'
                            : match.outcome === 'draw'
                              ? 'Draw'
                              : 'No result'}
                      </span>
                      <span>
                        {match.kills} / {match.deaths} / {match.assists}
                      </span>
                      <span>{match.rounds > 0 ? Math.round(match.score / match.rounds) : '—'}</span>
                      <strong className={(match.ratingDelta ?? 0) >= 0 ? 'positive' : 'negative'}>
                        {signed(match.ratingDelta)}
                      </strong>
                    </div>
                  ))}
                </>
              ) : (
                <div className="empty-state">
                  <RankEmblem />
                  <h3>History will appear after connecting</h3>
                  <p>Try sample data in the preview to check your appearance.</p>
                  <button
                    className="button secondary"
                    onClick={() => {
                      setPage('editor')
                      setDemoPreview(true)
                    }}
                  >
                    <Eye size={14} />
                    Customize overlay
                  </button>
                </div>
              )}
            </section>
          )}
          <footer className="page-footer">
            <span>
              VALTOOL STREAM OVERLAY <i /> LOCAL & OPEN SOURCE
            </span>
            <span>
              Made for great streams <Sparkles size={12} />
            </span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <Check size={15} />
          {toast}
          <button aria-label="Dismiss notification" onClick={() => setToast('')}>
            <X size={13} />
          </button>
        </div>
      )}
      {guide && (
        <div className="modal-backdrop" onClick={() => setGuide(false)}>
          <section
            className="guide-modal panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="obs-guide-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close"
              aria-label="Close guide"
              onClick={() => setGuide(false)}
            >
              <X size={18} />
            </button>
            <div className="obs-icon">
              <Radio size={25} />
            </div>
            <h2 id="obs-guide-title">Your overlay in OBS</h2>
            <p>Setup takes less than a minute.</p>
            <ol>
              <li>
                <span>1</span>
                <div>
                  <b>Add a Browser Source</b>
                  <p>In OBS: Sources → + → Browser.</p>
                </div>
              </li>
              <li>
                <span>2</span>
                <div>
                  <b>Paste the URL</b>
                  <p>Copy the URL from “Add to OBS”. Leave “Local file” unchecked.</p>
                </div>
              </li>
              <li>
                <span>3</span>
                <div>
                  <b>
                    Set the size to {size.width} × {size.height}
                  </b>
                  <p>
                    The background is already transparent. Keep ValTool Stream Overlay running; you
                    can close the settings tab.
                  </p>
                </div>
              </li>
            </ol>
            <div className="notice">
              OBS on another computer cannot open this local URL. If the source was opened before
              ValTool Stream Overlay started, refresh it after launching the app.
            </div>
            <button
              className="button primary"
              onClick={() => {
                void copy(editor.overlayUrl, 'OBS URL copied')
              }}
            >
              <Copy size={15} />
              Copy URL
            </button>
          </section>
        </div>
      )}
      <span className="sr-only" data-testid="overlay-key">
        {liveKey}
      </span>
    </div>
  )
}
