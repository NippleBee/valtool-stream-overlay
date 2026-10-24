# ValTool Stream Overlay

A local VALORANT statistics overlay for OBS, configured in your browser. The project has two packages: React + Vite + TypeScript + Tailwind in `frontend/`, and Python + FastAPI + Uvicorn + httpx + SQLite in `backend/`. A single Python process serves the API, SSE updates, and the production frontend.

Features include three card sizes, Midnight and Pastel themes, configurable metrics and match windows, match history, preset import/export, a live preview, and a separate transparent OBS source. Python calculates all statistics, including demo previews. The application and documentation use English.

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

`--demo` explicitly enables sample data in both settings and OBS. Without this flag, the server waits for a Riot session. You can enable sample data only in the preview without changing the regular OBS source. Automatic Windows client discovery is not connected yet; `--lockfile /path/to/lockfile` provides a manual integration entry point. Development on Mac covers the interface and server without a running game. Remaining Windows work includes automatic client discovery, validation with a real game session and OBS, and executable packaging.

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

Defaults: port **32145** and the `backend/.data/` directory. Override them with `npm start -- --data-dir /absolute/path --port 32145`. To migrate an existing installation, stop the old server and pass its data directory with `--data-dir`, or copy the complete directory into `backend/.data/`. Do not run two processes against the same database. The `settings.json` format (schemaVersion 1), `matches`/`contexts` tables, OBS key, and camelCase fields remain compatible with the prototype. The obsolete `autoStart` field is ignored. Unreadable settings are not overwritten; saves create a `.bak` backup.

Matches are isolated by `puuid:shard`. Tokens and the lockfile password remain in backend memory. The server binds only to `127.0.0.1`, validates Host/Origin, and issues a one-time editor URL. The OBS key permits reading prepared data; the editor uses a separate HttpOnly cookie. After a restart, open settings using the automatically issued URL. Local automation can use `--no-browser --editor-url-file /absolute/path` (the URL expires after five minutes; do not publish the file).

REST routes: `GET /api/health`, `POST /api/session`, `GET /api/editor`, `PUT /api/settings`, `GET /api/matches`, `POST /api/refresh`, and `POST /api/shutdown`. OBS data: `GET /api/overlay/{key}` and SSE `/api/overlay/{key}/events`. The `?preview=demo` parameter returns independently calculated sample data. OBS page: `/overlay/{key}`. Editor: `/settings`.

Statistics include the latest N or all available completed competitive matches, optionally limited to the current act. Remakes and unknown results are excluded; surrender alone does not imply a remake. K/D and KDA use aggregate totals. ACS is total score / total rounds. Winrate is wins / all included matches, including draws. When deaths are zero, the K/D and KDA denominator is 1. Missing RR displays as “—”; the latest match never borrows an older match's RR. Riot limits the accessible history, so “All” does not promise a lifetime archive. The recent-match strip has an independent length.

## Repository hygiene

Commit source files, tests, dependency manifests, presets, and required public assets. Do not commit virtual environments, `node_modules`, production bundles, local settings or databases, lockfiles containing Riot credentials, bootstrap URLs, environment secrets, logs, screenshots, or test/build artifacts. `.gitignore` excludes these local files. Runtime data stays on your machine.

## License

Code is licensed under [MIT](LICENSE). Game artwork and fonts have separate terms in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Cards use original HTML/CSS components; reference images are not included. Tray integration, autostart, installers, and automatic updates are outside the current scope.
