# Third-party assets

## Riot Games artwork

Files under `frontend/public/ranks` and `frontend/public/agents` are VALORANT rank emblems and agent portraits owned by Riot Games. They are distributed separately from this project's MIT-licensed code and are not relicensed under MIT.

Asset source: [Valorant-API](https://valorant-api.com/), downloaded on 2026-10-24 from `media.valorant-api.com`. Upstream endpoint metadata: `/v1/competitivetiers` and `/v1/agents?isPlayableCharacter=true`.

Riot Games, VALORANT and associated assets are trademarks and/or copyrighted material of Riot Games, Inc. This project is not endorsed by or affiliated with Riot Games. Review Riot's applicable developer and fan-content policies before redistributing a public release.

## Fonts

Inter and Barlow Condensed are bundled locally via `@fontsource-variable/inter` and `@fontsource/barlow-condensed`. Both fonts use the SIL Open Font License 1.1. Their copyright and license files are included in the `licenses` directory.

## Dependencies

The Windows tray uses pystray (LGPL-3.0-or-later), Pillow (HPND), and six (MIT). Their wheel metadata and license files are included in the Windows bundle alongside the other Python runtime dependency notices.

React, Vite, Tailwind CSS, Lucide, FastAPI, Uvicorn, httpx, Pydantic and their dependencies retain their respective upstream licenses. Versions are recorded in `package-lock.json` and `backend/requirements-dev.txt`. Distribution bundles must include applicable dependency license notices.
