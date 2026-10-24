# ValTool Stream Overlay

A local VALORANT statistics overlay for OBS, configured in your browser. The project has two packages: React + Vite + TypeScript + Tailwind in `frontend/`, and Python + FastAPI + Uvicorn + httpx + SQLite in `backend/`. A single Python process serves the API, SSE updates, and the production frontend.

Features include three card sizes, Midnight and Pastel themes, configurable metrics and match windows, match history, preset import/export, a live preview, and a separate transparent OBS source. Python calculates all statistics, including demo previews. The application and documentation use English.

Every card size shows the number of matches used in its statistics. The optional ValTool logo and name watermark is enabled by default and can be switched off under Appearance → Show watermark. Its setting is saved and included in presets; older settings and presets remain compatible. Overlay dimensions stay the same when the watermark is toggled.

Appearance → OBS render size selects 100%, 200%, or 300% native rendering; 200% is the default. Text labels, metrics, match counts, and branding use larger fonts and higher contrast. Copy the source dimensions shown in Add to OBS into the Browser Source's Width and Height properties, then use Transform → Reset Transform and position the source. At 200%, Compact uses **600 × 268** without the recent strip or **600 × 356** with it; Mini uses **440 × 140**. Smaller existing viewports fit the card without cropping, but use the full reported dimensions for the larger native render. Width and Height set the browser viewport, as described in the [OBS Browser Source documentation](https://obsproject.com/kb/browser-source). The OBS scene preview can itself be scaled below 100%, which affects the on-screen preview.

Current version: **1.0.0**. See the [Windows release notes](docs/releases/v1.0.0.md) for download, launch, and upgrade instructions.

## Run from source

Requirements: Python 3.12+ and Node.js 22.12+ (CI uses Node 24). Run these commands from the repository root:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
npm ci
npm run build
npm start -- --demo
```

On Windows, create the environment with `py -3 -m venv backend/.venv`, then run `backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt`. The npm scripts find this environment automatically. Set `VALTOOL_PYTHON` to use a different Python executable.

The server opens settings in your browser. In OBS, add a **Browser Source**, paste the **OBS URL**, and set the displayed source width and height. The URL survives restarts as long as the data directory is preserved. OBS and the app must run on the same computer.

`--demo` explicitly enables sample data in both settings and OBS. Without this flag, Windows automatically detects Riot Client using its standard lockfile and verifies the matching process ID. Launch VALORANT once to obtain its deployment region. The game process determines whether VALORANT is running; the local token endpoint is rechecked every two seconds to detect account changes. You can enable sample data only in the preview without changing the regular OBS source. `--lockfile /path/to/lockfile` overrides automatic discovery. Other development operating systems wait for an explicitly configured session.

The player-platform claim in the current access token supplies the shard when the launch arguments omit it; deployment and shard remain separate values. The installed game log supplies `X-Riot-ClientVersion`, with the public catalog as fallback. Existing catalog metadata survives temporary catalog outages. A live Windows check verified local authentication and TLS-verified reads of MMR, competitive updates, history, and match details. Full exit/relaunch/account-switch and OBS acceptance checks still require manual validation.

## Windows executable

Build on Windows with Python 3.12+ after installing the frontend dependencies:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-build.txt
npm ci
npm run build
backend/.venv/Scripts/python.exe -m PyInstaller --noconfirm packaging/windows.spec
```

Distribute the complete `dist/ValTool Stream Overlay/` folder and launch `ValTool Stream Overlay.exe`. The onedir build bundles Python, the frontend, local fonts/game assets, TLS CA certificates, and license notices. Users do not need Python or Node. Keep the `_internal` folder next to the executable. The build and tray use the ValTool logo. The editor opens automatically and the app stays in the Windows notification area when its browser tab is closed. Right-click the tray icon to open the editor again, refresh statistics, or quit. Windows may place it under the notification area's hidden-icons arrow. Each editor launch gets a fresh authenticated URL. **Quit app** in the editor explains that OBS updates will stop; closing only the browser tab keeps the overlay running. Startup errors appear in a Windows dialog when no console is present; another launch with the same data directory is rejected before opening storage. A clean Windows VM and OBS remain manual release checks.

The bundle locates assets inside PyInstaller's runtime directory, following its [runtime path documentation](https://pyinstaller.org/en/stable/runtime-information.html). Run `backend/.venv/Scripts/python.exe scripts/smoke-windows.py "dist/ValTool Stream Overlay/ValTool Stream Overlay.exe"` for an isolated startup/assets/SSE/restart check; add `--live` to check the signed-in Riot session. Windows CI runs the demo bundle check automatically.

For a credential-free diagnostic summary, run `backend/.venv/Scripts/python.exe scripts/check-windows-session.py` while signed in. It reads current rank and match history without printing tokens, passwords, player IDs, or bootstrap URLs.

Completed matches with valid player statistics and team results are displayed and cached normally. New metadata such as `hasTempValues` and `tempValueT` is ignored; it does not indicate whether statistics are usable. Missing statistics, incomplete matches, and unknown results are retried rather than cached as final. HTTP 429 pauses and resumes the current request, preserving pagination; account and selection changes can cancel the wait. Normal mode opens a live preview; sample data is an explicit preview option.

## Development and checks

```sh
npm run dev -- --demo   # Python API + Vite HMR; settings open on port 5173
npm run build          # Production frontend only
npm start              # Python serves frontend/dist in normal waiting mode
npm test               # pytest, followed by Vitest
npm run check          # TypeScript
npm run test:api        # Production build + HTTP/SSE integration tests
npx playwright install chromium
npm run test:e2e        # Production build + browser tests
npm run format:check
```

Python dependencies are pinned in `backend/requirements-dev.txt`. Runtime dependencies without test tools are in `backend/requirements.txt`. The backend also provides a `pyproject.toml` for package installation. Browser tests start temporary servers on ports 32146/32147; API integration tests use 32149. Their data directories are removed when the test host exits.

## Data and API

Defaults: port **32145** and `%LOCALAPPDATA%/ValTool Stream Overlay/` on Windows (source and packaged builds); other systems use `backend/.data/`. Data stays outside the executable and temporary extraction directory. Override with `npm start -- --data-dir /absolute/path --port 32145`. To migrate, stop the old server, then copy the complete old data directory to the new location, including any `matches.db-wal` and `matches.db-shm` files, or keep using the old directory with `--data-dir`. Preserve `settings.json` to keep the OBS URL. No automatic migration or key reset occurs. Do not run two processes against the same database. The `settings.json` format (schemaVersion 1), `matches`/`contexts` tables, OBS key, and camelCase fields remain compatible with the prototype. The obsolete `autoStart` field is ignored. Unreadable settings are not overwritten; saves create a `.bak` backup.

Matches are isolated by `puuid:shard`. Tokens and the lockfile password remain in backend memory. The server binds only to `127.0.0.1`, validates Host/Origin, and issues a one-time editor URL. The OBS key permits reading prepared data; the editor uses a separate HttpOnly cookie. After a restart, open settings using the automatically issued URL. Local automation can use `--no-browser --editor-url-file /absolute/path` (the URL expires after five minutes; do not publish the file).

REST routes: `GET /api/health`, `POST /api/session`, `GET /api/editor`, `PUT /api/settings`, `GET /api/matches`, `POST /api/refresh`, and `POST /api/shutdown`. OBS data: `GET /api/overlay/{key}` and SSE `/api/overlay/{key}/events`. The `?preview=demo` parameter returns independently calculated sample data. OBS page: `/overlay/{key}`. Editor: `/settings`.

Statistics include the latest N or all available completed competitive matches, optionally limited to the current act. Remakes and unknown results are excluded; surrender alone does not imply a remake. K/D and KDA use aggregate totals. ACS is total score / total rounds. Winrate is wins / all included matches, including draws. When deaths are zero, the K/D and KDA denominator is 1. Missing RR displays as “—”; the latest match never borrows an older match's RR. Riot limits the accessible history, so “All” does not promise a lifetime archive. The recent-match strip has an independent length.

## Repository hygiene

Commit source files, tests, dependency manifests, presets, and required public assets. Do not commit virtual environments, `node_modules`, production bundles, local settings or databases, lockfiles containing Riot credentials, bootstrap URLs, environment secrets, logs, screenshots, or test/build artifacts. `.gitignore` excludes these local files. Runtime data stays on your machine.

## License

Code is licensed under [MIT](LICENSE). Game artwork, fonts, and dependencies have separate terms in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Cards use original HTML/CSS components; reference images are not included. Autostart, installers, and automatic updates are outside the current scope.
