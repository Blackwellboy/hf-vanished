# HF Vanished

**Models disappear from Hugging Face. We keep the receipts.**

HF Vanished is a public, automated evidence ledger for Hugging Face Hub availability changes.

It records **before → now** evidence for models that become disabled, deleted, auth-required/private, gated, or stripped of model files.

**Live:** https://blackwellboy.github.io/hf-vanished/  
**Repo:** https://github.com/Blackwellboy/hf-vanished

> Facts. Timestamps. Links. Diffs. No manifesto.

## What this project does — and does not do

HF Vanished records **observable availability changes**. It does **not** infer why a model changed state unless a public source explicitly documents the reason.

Possible causes can include author action, licensing, legal action, moderation, safety policy, distribution changes, or something else entirely. If the reason is not documented, the correct answer is **unknown**.

For unauthenticated HTTP `401/403`, the public UI deliberately presents the state conservatively as **AUTH REQUIRED** rather than pretending the response proves motive or ownership action.

## Public views

The site groups events into two simple buckets:

- **VANISHED** — disabled, deleted, auth-required/private after prior public evidence, or model files removed.
- **RESTRICTED** — newly gated or otherwise access-restricted while remaining listed.

Exact event status is still preserved in the ledger.

## Evidence labels

| Label | Meaning |
|---|---|
| **VERIFIED** | The tracker itself observed a public → changed-state transition. |
| **ARCHIVED** | A concrete historical public snapshot is linked and the current state is recorded. |
| **REPORTED** | Curated/publicly reported event that still needs stronger historical proof. |

The UI intentionally exposes this distinction so weak evidence does not look identical to strong evidence.

## Automatic pipeline

Every ~6 hours GitHub Actions runs the whole system unattended:

1. Expand the watch set from the explicit watchlist, search families, and popular Hub models.
2. Poll the public Hugging Face Hub API with **no HF token**.
3. Diff each model against the previous snapshot in `data/state.json`.
4. Suppress brief flaps and ignore models never observed public.
5. Query Wayback CDX for hard disappearances where possible.
6. Validate the generated JSON.
7. Commit refreshed ledger/state data when anything changed.
8. Deploy the refreshed static site to GitHub Pages in the same workflow.

Schedule:

```cron
17 */6 * * *
```

That is minute 17 of every sixth UTC hour. It is deliberately off the top of the hour because GitHub documents heavier scheduled-workflow congestion around `:00`.

There is no server to maintain and no secret credential required. The job has a 30-minute timeout and fails closed if the generated ledger/state JSON is malformed.

**Platform caveat:** GitHub automatically disables scheduled workflows in a public repository after 60 days with no repository activity. Normal project activity avoids that; otherwise the schedule can be re-enabled from Actions.

## Discovery

The current discovery set includes an explicit watchlist plus search families such as:

- `uncensored`
- `abliterated`
- `obliterated`
- `ablited`
- `red-team`
- `jailbreak`
- `refusal-removed`

and a top-download slice from the Hub.

The list is intentionally broader than “uncensored models” because HF Vanished is an availability ledger, not a censorship classifier.

## Statuses

| Status | Meaning |
|---|---|
| **DISABLED** | Hub reports `disabled=true` after prior availability. |
| **DELETED** | Previously public/resolvable path later returns a true missing state such as 404. |
| **PRIVATE / AUTH REQUIRED** | Unauthenticated access is no longer available after prior public evidence. The UI uses conservative wording when HTTP alone cannot distinguish the exact cause. |
| **GATED** | Model remains listed but access becomes gated. |
| **STRIPPED / FILES REMOVED** | Model/weight files disappear while the listing remains. |

**Ignored automatically:** brief flaps under 24h and models never observed public.

## Data

| Path | Role |
|---|---|
| `data/events.json` | Public event ledger consumed by the Pages UI. |
| `data/state.json` | Latest snapshot for each watched model and the diff source. |
| `data/seeds.json` | Explicit watchlist, search families, and curated known events. |

Current schema: `hf-vanished.events.v1`.

## Report a missing model

The easiest way to contribute is the public issue form:

https://github.com/Blackwellboy/hf-vanished/issues/new?template=report-model.yml

It asks for:

- model ID / Hub URL
- what changed
- approximate last-public date
- optional Wayback or other public proof
- notes useful for verification

Public-safe evidence only. Do **not** paste credentials, private dumps, or tokens.

Developers can also PR changes to `data/seeds.json`.

## Local run

```bash
python3 scripts/poll.py
python3 -m http.server 8080
```

Then open `http://localhost:8080`.

## Design rule

Keep this project boring underneath:

- vanilla HTML/CSS/JS
- static JSON
- one Python poller
- GitHub Actions
- GitHub Pages
- public APIs only

No accounts, no database server, no app backend, no tracking SDK required.

The simplicity is a feature.

## License

CC0-1.0 for ledger data presentation in this repo unless noted otherwise. Upstream model weights remain under their own licenses.
