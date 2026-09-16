# HF Vanished

**Models disappear from Hugging Face. We keep the receipts.**

HF Vanished is a public, automated evidence ledger for Hugging Face Hub availability changes. It records **before → now** evidence for models that become disabled, deleted, auth-required/private, gated, or stripped of model files, then checks whether a known recovery path exists.

It also has an additive forensic layer for **source-backed reasons, public discussion/commit context, cryptographic file identity, and correlation-only incident signals**.

**Live:** https://blackwellboy.github.io/hf-vanished/  
**Repo:** https://github.com/Blackwellboy/hf-vanished  
**Machine feed:** https://blackwellboy.github.io/hf-vanished/data/status.json

> Facts. Timestamps. Sources. Hashes. Correlation ≠ causation.

## What this project does — and does not do

HF Vanished records **observable availability changes**. It does **not** infer why a model changed state unless a public source explicitly documents the reason.

Possible causes can include author action, licensing, legal action, moderation, safety policy, distribution changes, or something else entirely. If the reason is not documented, the correct answer is **unknown**.

For unauthenticated HTTP `401/403`, the public UI deliberately presents **AUTH REQUIRED** rather than pretending the response alone proves deletion, censorship, or an author decision.

Timing clusters, discussion spikes, keyword matches, same-owner removals, or same-family removals are useful research signals. They are **not evidence by themselves** of mass reporting, organized campaigns, censorship, legal action, or government intervention.

## Public views

- **VANISHED** — disabled, deleted, auth-required/private after prior public evidence, or model files removed.
- **RESTRICTED** — newly gated or otherwise access-restricted while remaining listed.

Evidence strength is shown separately:

| Label | Meaning |
|---|---|
| **VERIFIED** | The tracker itself observed a public → changed-state transition. |
| **ARCHIVED** | A concrete historical public snapshot is linked and the current state is recorded. |
| **REPORTED** | Curated/publicly reported event that still needs stronger historical proof. |

## WHY / reason evidence

The cause of a disappearance is a separate field from the disappearance itself.

Reason confidence labels:

| Label | Meaning |
|---|---|
| **OFFICIAL** | A platform, owner, legal authority, or other definitive public source explicitly states the reason. |
| **PRIMARY SOURCE** | A directly involved party publicly states the reason. |
| **CORROBORATED** | Multiple credible public sources agree but no definitive official statement is recorded. |
| **REPORTED** | A public report exists but remains unverified or disputed. |
| **UNKNOWN** | No public source-backed cause has been recorded. |

A non-`UNKNOWN` reason must have at least one public source URL in `data/reasons.json`.

The automated forensic job may capture keyword/context **signals** from model cards, commits or public discussions. Those are explicitly labelled `NON_CAUSAL_SIGNAL` and are never promoted to a reason automatically.

## Forensic evidence layer

The six-hour pipeline now maintains bounded public forensic context in addition to availability state:

- recent public Hugging Face discussions and selected discussion events/comments;
- recent repository commit metadata;
- model-card SHA-256;
- a compact pre/post timeline;
- source-backed reason status;
- per-evidence-record SHA-256;
- file/snapshot identity where the public Hub API exposes it;
- temporal/same-owner/same-family incident correlation.

The evidence pass prioritizes event models and rotates through still-public watched models so useful public context can be retained **before** a repository becomes unavailable.

See [`docs/FORENSICS.md`](docs/FORENSICS.md) for the full evidence model and limitations.

## Hashing and model identity

HF Vanished distinguishes three identities:

1. **Hub revision** — the repository revision observed by the normal poller.
2. **File identity** — Git object ID, LFS SHA-256, and/or Xet hash when publicly exposed by the Hub tree API.
3. **Manifest root SHA-256** — deterministic SHA-256 of the canonical file-identity manifest recorded by HF Vanished.

The evidence object gets its own `evidence_sha256` as well.

A hash can prove that two artifacts/records are identical. **A hash does not preserve the model bytes.** HF Vanished still separates proof from recovery.

When a complete live file tree is no longer available, the manifest is explicitly marked as a bounded `LAST_PUBLIC_SAMPLE` rather than pretending the historical manifest is complete.

## Incident correlation

`data/incidents.json` groups events using machine-observable signals such as:

- `TEMPORAL_CLUSTER`
- `SAME_OWNER_CLUSTER`
- `SAME_MODEL_FAMILY`

Every automatic incident is marked `CORRELATION_ONLY`.

This makes it possible to ask useful questions such as “did several related models change state in the same 24-hour window?” without claiming to know why that happened.

## Recovery layer

HF Vanished does not host model weights. It separates **proof** from **recovery**:

- **Wayback Machine** — historical evidence that a model page/listing existed.
- **Pirate Face** — best-effort check for a checksum-backed model page and, when available, a torrent/magnet.
- **Hugging Face search** — find surviving mirrors, quants, conversions, or re-uploads.
- **FrostByte** — an independent desktop app that already accepts Hugging Face downloads, magnets/torrents, and IPFS. When HF Vanished finds a magnet, the UI lets you copy it for FrostByte or another torrent client.

Recovery labels:

| Label | Meaning |
|---|---|
| **PROTECTED** | Hugging Face is still reachable and a Pirate Face torrent is known. |
| **RESCUED** | HF Vanished sees the source as vanished while a Pirate Face torrent is known. |
| **AT RISK** | Source is still reachable, but no active Pirate Face torrent has been verified yet. |
| **NO KNOWN COPY** | Source is vanished and this tracker has not verified a Pirate Face torrent. This is **not** a claim that no copy exists anywhere. |
| **UNMIRRORED** | No Pirate Face torrent is known and the recorded license is outside Pirate Face's currently advertised MIT/Apache-2.0 intake. |
| **UNKNOWN** | Recovery status has not been probed yet or the external check failed. |

Pirate Face and FrostByte are independent projects; links here do not imply affiliation or endorsement.

## Automatic pipeline

Every ~6 hours GitHub Actions runs unattended:

1. Expand the watch set from the explicit watchlist, search families, and popular Hub models.
2. Add every model ever seen in `data/state.json` so discovery is **cumulative** — once watched, always watched.
3. Poll the public Hugging Face Hub API with **no HF token**.
4. Capture public metadata useful later: Hub revision, license, file counts, model format tags, and a bounded sample of weight filenames.
5. Diff each model against its previous snapshot.
6. Suppress brief flaps and ignore models never observed public.
7. Query Wayback CDX for hard disappearances where possible.
8. Run a bounded forensic pass over event models plus a rotating public watch-set slice: discussions, commits, model-card hash, file identity and incident signals.
9. Run a bounded, fail-soft Pirate Face probe. Event models are prioritized and the rest of the persistent watch set is rotated over time.
10. Generate the v1 status feed plus additive evidence, manifest and incident feeds.
11. Validate JSON and source-backed reason invariants, commit changed data, and deploy the refreshed static site.

Schedule:

```cron
17 */6 * * *
```

That is minute 17 of every sixth UTC hour. It is deliberately off the top of the hour because GitHub documents heavier scheduled-workflow congestion around `:00`.

There is no server to maintain and no secret credential required. Optional public evidence/recovery failures are fail-soft and cannot erase the core v1 availability event.

**Platform caveat:** GitHub automatically disables scheduled workflows in a public repository after 60 days with no repository activity. Normal project activity avoids that; otherwise the schedule can be re-enabled from Actions.

## Discovery

Current discovery includes an explicit watchlist plus search families such as:

- `uncensored`
- `abliterated`
- `obliterated`
- `ablited`
- `red-team`
- `jailbreak`
- `refusal-removed`

and a top-download slice from the Hub. The watch set is cumulative, so models discovered today remain checked even if they later fall out of those search results.

The list is intentionally broader than “uncensored models” because HF Vanished is an availability ledger, not a censorship classifier.

## Data

| Path | Role |
|---|---|
| `data/events.json` | Existing public disappearance/restriction event ledger. |
| `data/state.json` | Latest persistent snapshot for every watched model. |
| `data/status.json` | Compact lifecycle + recovery feed for clients/integrations. |
| `data/integrations.json` | Cached external recovery observations and rotation cursor. |
| `data/seeds.json` | Explicit watchlist, search families, and curated known events. |
| `data/reasons.json` | Curated public-source reason classifications; UNKNOWN by default. |
| `data/evidence.json` | Bounded discussion/commit/timeline/source evidence cache with record hashes. |
| `data/manifests.json` | File identity manifests and deterministic manifest root hashes. |
| `data/incidents.json` | Correlation-only temporal/owner/family incident clusters. |

Schemas:

- `hf-vanished.events.v1`
- `hf-vanished.status.v1`
- `hf-vanished.integrations.v1`
- `hf-vanished.reasons.v1`
- `hf-vanished.evidence.v1`
- `hf-vanished.manifest.v1`
- `hf-vanished.incidents.v1`

See [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) for recovery integration behavior and [`docs/FORENSICS.md`](docs/FORENSICS.md) for forensic feed semantics.

## FrostByte integration

FrostByte's public product page documents Hugging Face, magnet/torrent, and IPFS downloads. HF Vanished therefore publishes **handoff data**, not an invented proprietary URL scheme:

```json
{
  "preservation": "RESCUED",
  "pirateface": {
    "url": "https://pirateface.co/org/model",
    "status": "torrent",
    "magnet": "magnet:?xt=..."
  },
  "frostbyte": {
    "app_url": "https://blackfrostai.com/frostbyte",
    "handoff": "magnet",
    "magnet": "magnet:?xt=..."
  }
}
```

A future FrostByte release can consume `data/status.json` directly or add an official application deep-link scheme without HF Vanished changing its evidence model.

## Report a missing model

Use the public issue form:

https://github.com/Blackwellboy/hf-vanished/issues/new?template=report-model.yml

Include the model ID/URL, what changed, approximate last-public date, and public Wayback/evidence links. If you believe a reason is documented, include the **public source**. Relevant Hugging Face discussion/comment URLs and known file hashes are useful too.

Do **not** paste credentials, private dumps, tokens, or non-public correspondence.

## Local run

```bash
python3 scripts/poll_forever.py
python3 scripts/evidence.py
python3 scripts/integrations.py
python3 -m http.server 8080
```

Then open `http://localhost:8080`.

## Design rule

Keep the project boring underneath:

- vanilla HTML/CSS/JS
- static JSON
- small Python pollers
- GitHub Actions
- GitHub Pages
- public sources only

No accounts, database server, tracking SDK, or required secret credentials. The simplicity is a feature.

## License

CC0-1.0 for ledger data presentation in this repo unless noted otherwise. Upstream model weights, model cards, archived material, Pirate Face records, public discussions/statements, and third-party applications remain under their own licenses/terms.
