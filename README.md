# HF Vanished

Public evidence ledger of Hugging Face Hub **visibility changes**.

**Repo:** https://github.com/Blackwellboy/hf-vanished  
**Live Pages:** https://blackwellboy.github.io/hf-vanished/

Tone: facts, timestamps, links, diffs. Not a manifesto.

## Status chips

| Chip | Severity | Meaning |
|------|----------|---------|
| **DISABLED** | hard | Hub `disabled=true` after the repo was available |
| **DELETED** | hard | Was public / resolvable, now HTTP 404 |
| **PRIVATE** | hard | Taken private after a public observation (unauth API → 401/403) |
| **GATED** | soft | Newly gated after an open observation |
| **STRIPPED** | soft | Weight/files removed while the listing remains |

**Ignored:** brief flaps (&lt;24h), and models never observed public (always-private).

## Data files

| Path | Role |
|------|------|
| `data/events.json` | Ledger consumed by the Pages UI |
| `data/state.json` | Last snapshot per watched model (diff source) |
| `data/seeds.json` | Watchlist, search families, curated known events |

### `events.json` schema (`hf-vanished.events.v1`)

```json
{
  "generated_at": "2026-09-16T12:00:00Z",
  "schema": "hf-vanished.events.v1",
  "cadence": "0 */6 * * *",
  "events": [
    {
      "id": "org/model",
      "status": "DISABLED",
      "severity": "hard",
      "kind": "disabled",
      "summary": "…",
      "detected_at": "2026-09-16T00:00:00Z",
      "hf_url": "https://huggingface.co/org/model",
      "wayback_url": "https://web.archive.org/web/…/https://huggingface.co/org/model",
      "prev": { "visibility": "public", "gated": false, "weight_count": 12 },
      "curr": { "visibility": "disabled", "disabled": true, "http": 200 }
    }
  ]
}
```

## Pipeline

1. Expand seeds: explicit watchlist + keyword families (`uncensored`, `abliterated`, `obliterated`, `ablited`, `red-team`, `jailbreak`, `refusal-removed`) + top downloads.
2. Poll public Hub API: `GET https://huggingface.co/api/models/{id}` (no token).
3. Diff against `state.json` → hard/soft events; suppress flaps; skip always-private.
4. For hard disappearances, query Wayback CDX for a last-public `200` snapshot.
5. Write `events.json` for the static UI.

Cadence: GitHub Action cron `0 */6 * * *` (~every 6 hours), plus `workflow_dispatch`.

The poll workflow commits refreshed `data/*.json` **and** deploys Pages in the same run (`GITHUB_TOKEN` pushes do not re-trigger other workflows).

**No secrets.** No HF tokens, no PATs in workflows. Uses `GITHUB_TOKEN` only for committing refreshed data and deploying Pages.

## Local run

```bash
python3 scripts/poll.py
# opens index.html via any static server, e.g.:
python3 -m http.server 8080
```

## Contribute seed IDs

Public-safe IDs only. Do **not** paste private evidence dumps.

1. Fork / PR against `data/seeds.json`.
2. Add to `watchlist` (monitor) or `known_events` (curated ledger row with `status`, `severity`, `summary`, optional `wayback_url`).
3. Prefer models with prior public proof (downloads history, docs, Wayback).

## License

CC0-1.0 for ledger data presentation in this repo unless noted otherwise. Upstream model weights remain under their own licenses.
