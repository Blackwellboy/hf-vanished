# HF Vanished integrations

HF Vanished keeps evidence collection separate from recovery/download tooling.

The public contract for clients is:

`https://blackwellboy.github.io/hf-vanished/data/status.json`

Schema: `hf-vanished.status.v1`.

## Per-model record

Each watched model can expose:

- `hf.lifecycle` — `AVAILABLE`, `RESTRICTED`, `VANISHED`, or `UNKNOWN`
- `hf.visibility`, HTTP state, gate state, and last check time
- `last_public` — last retained Hub revision/license/file metadata where available
- `mirror_eligibility` — whether the recorded license matches Pirate Face's currently advertised MIT/Apache-2.0 intake
- `preservation` — `PROTECTED`, `RESCUED`, `AT_RISK`, `NO_KNOWN_COPY`, `UNMIRRORED`, or `UNKNOWN`
- `pirateface.url` — deterministic `pirateface.co/<namespace>/<model>` URL
- `pirateface.status` — `torrent`, `indexed`, `not_indexed`, or `unknown`
- `pirateface.magnet` — only when observed in the public page
- `pirateface.seeders` — only when exposed by the public page
- `frostbyte.app_url` — official FrostByte product page
- `frostbyte.handoff` — `huggingface`, `magnet`, or `null`
- `frostbyte.magnet` — same public magnet when available

Consumers must treat missing fields as unknown, not false.

## Pirate Face

Pirate Face currently advertises a future drop-in API but does not document that API as generally available. HF Vanished therefore does **not** depend on private endpoints or credentials.

Instead, `scripts/integrations.py` performs a bounded public-page probe:

- event models are prioritized;
- the rest of the persistent watch set is rotated;
- checks are cached in `data/integrations.json`;
- transient external failures retain the last known good recovery state;
- unknown/parser failures do not create a fake torrent;
- direct model URLs are deterministic from the Hugging Face model ID.

When Pirate Face publishes a stable API, this probe can be replaced without changing `status.json` consumers.

## FrostByte

The public FrostByte documentation currently supports Hugging Face downloads, torrent/magnet links, and IPFS, but does not publish a custom `frostbyte://` deep-link protocol.

HF Vanished therefore does not invent one. If a Pirate Face magnet is known, the site offers **COPY MAGNET** and links to FrostByte. A future FrostByte build can either:

1. consume `status.json` and show HF Vanished lifecycle/recovery state inside its model UI; or
2. publish an official application URL scheme, at which point HF Vanished can add a real one-click handoff.

Suggested future client behavior:

- `AVAILABLE + PROTECTED` → normal HF download, with P2P fallback available;
- `VANISHED + RESCUED` → offer the verified Pirate Face magnet;
- `VANISHED + NO_KNOWN_COPY` → show evidence and mirror search, but do not claim a recoverable download;
- always display source/revision/license metadata when available.

## Trust and licensing

HF Vanished does not host model weights and does not decide whether redistribution is lawful. Licenses are recorded as evidence from the public Hub metadata when observed. Recovery links remain subject to the upstream model license and the policies/terms of the independent service providing the copy.

`NO_KNOWN_COPY` means exactly that: HF Vanished has not verified a Pirate Face torrent. It does not mean the model bytes no longer exist anywhere.

Pirate Face and FrostByte are independent projects. Integration metadata and links do not imply affiliation, endorsement, or control.
