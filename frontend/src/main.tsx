import React from 'react'
import ReactDOM from 'react-dom/client'
import '@fontsource-variable/inter'
import '@fontsource/barlow-condensed/600.css'
import '@fontsource/barlow-condensed/700.css'
import './styles.css'
import { App } from './App'
import { OverlayPage } from './Overlay'

const match = location.pathname.match(/^\/overlay\/([^/]+)\/?$/)
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {match ? <OverlayPage token={decodeURIComponent(match[1])} /> : <App />}
  </React.StrictMode>,
)
