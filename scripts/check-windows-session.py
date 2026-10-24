"""Read-only live integration check; prints no credentials or player identifiers."""
import asyncio
import json
import re
import sys
import argparse
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from valtool_overlay.riot import Catalog, RiotClient, RiotError, parse_match
from valtool_overlay.windows import WindowsSessionProvider
from valtool_overlay.service import OverlayService, RiotWorker
from valtool_overlay.storage import Storage


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sync', action='store_true')
    options = parser.parse_args()
    catalog = Catalog()
    session = await WindowsSessionProvider(catalog).discover()
    if session is None:
        print("Waiting for Riot Client")
        return
    print(json.dumps({"connected": True, "running": session.running, "shard": session.shard,
                      "region": session.region, "version": session.version}))
    class CountedClient(RiotClient):
        counts = {}
        async def get(self, session, path, **kwargs):
            kind = 'details' if path.startswith('match-details/') else 'history' if path.startswith('match-history/') else 'updates' if 'competitiveupdates' in path else 'mmr'
            self.counts[kind] = self.counts.get(kind, 0) + 1
            return await super().get(session, path, **kwargs)
    client = CountedClient()
    try:
        if options.sync:
            service = OverlayService(Storage(Path(__file__).resolve().parents[1] / 'work/live-check'))
            worker = RiotWorker(service, client, catalog=catalog)
            try:
                await worker.sync(session)
                print(json.dumps({'syncComplete': True, 'loaded': len(service.records), 'pending': service.pending_details,
                                  'games': service.snapshot().stats.games,
                                  'cached': len(service.storage.read_matches(session.cache_key))}))
            except RiotError:
                raise
            except Exception as error:
                print('Sync failure type:', type(error).__name__)
                print('Frames:', [(Path(frame.filename).name, frame.name, frame.lineno) for frame in traceback.extract_tb(error.__traceback__)])
                if isinstance(error, KeyError) and re.fullmatch(r'[a-zA-Z_]+', str(error.args[0])):
                    print('Missing field:', error.args[0])
                raise SystemExit(1) from None
            return
        mmr = await client.mmr(session)
        history = await client.history(session, 0)
        updates = await client.updates(session, 0)
        print(json.dumps({"rank": catalog.rank(mmr).name, "activeActFound": catalog.active_season is not None,
                          "historyCount": len(history.get("History", [])), "historyTotal": history.get("Total"),
                          "ratingCount": len(updates.get("Matches", []))}))
        if history.get("History"):
            payload = await client.details(session, history["History"][0]["MatchID"])
            match = parse_match(payload, session.puuid, None, catalog)
            player = next((player for player in payload.get('players', []) if player.get('subject') == session.puuid), {})
            print(json.dumps({"latestMatchParsed": match is not None,
                              "completionState": payload.get("matchInfo", {}).get("completionState"),
                              "hasTempValues": payload.get("hasTempValues"),
                              "completed": payload.get('matchInfo', {}).get('isCompleted'),
                              "stats": {key: player.get('stats', {}).get(key) for key in ('kills', 'deaths', 'assists', 'score', 'roundsPlayed')},
                              "roundResults": len(payload.get('roundResults', [])),
                              "teamRounds": [{key: team.get(key) for key in ('won', 'roundsPlayed', 'roundsWon')} for team in payload.get('teams', [])]}))
    except RiotError as error:
        print(f"Remote check failed: HTTP {error.status}; code={error.code}; retryAfter={error.retry_after}")
        print('Request counts:', client.counts)
        if options.sync:
            print('Cached matches:', len(service.records), 'pending:', service.pending_details)
        raise SystemExit(1) from None
    finally:
        await client.close()


asyncio.run(main())
