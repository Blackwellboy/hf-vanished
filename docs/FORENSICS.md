# HF Vanished forensic evidence layer

HF Vanished separates **observation**, **source evidence**, **reason classification**, **cryptographic identity**, and **correlation**.

The core rule is unchanged:

> If a public source does not document why a model changed state, the reason is `UNKNOWN`.

A disappearance, HTTP status, timing cluster, keyword, report volume, model category, or discussion spike is never enough on its own to label a cause.

## Feeds

### `data/events.json`
Existing `hf-vanished.events.v1` availability ledger. Kept backwards compatible.

### `data/status.json`
Existing `hf-vanished.status.v1` lifecycle/recovery feed. Kept backwards compatible.

### `data/reasons.json`
`hf-vanished.reasons.v1` is the small curated source-of-truth for causal classifications.

A non-`UNKNOWN` entry must include at least one public source URL.

Example:

```json
{
  "category": "legal",
  "status": "OFFICIAL",
  "summary": "The platform publicly states that the repository was disabled following a legal request.",
  "sources": [
    {
      "type": "platform_statement",
      "url": "https://example.invalid/public-statement",
      "published_at": "2026-09-16T00:00:00Z"
    }
  ]
}
```

Allowed evidence statuses:

- `OFFICIAL` — platform/owner/legal authority explicitly states the reason.
- `PRIMARY_SOURCE` — directly involved party publicly states the reason.
- `CORROBORATED` — multiple credible public sources agree, but no definitive official statement is recorded.
- `REPORTED` — a public report exists but remains unverified or disputed.
- `UNKNOWN` — no source-backed reason is recorded.

Allowed categories:

- `author_action`
- `legal`
- `licensing`
- `moderation`
- `safety_policy`
- `terms_of_service`
- `distribution_change`
- `platform_action`
- `other`
- `unknown`

### `data/evidence.json`
`hf-vanished.evidence.v1` is the bounded forensic cache for public material relevant to a model.

It can contain:

- reason classification from `reasons.json`;
- recent public Hugging Face discussions and selected discussion events/comments;
- recent repository commits;
- model-card hash;
- keyword/context **signals**;
- a compact timeline;
- a SHA-256 digest of the evidence record itself;
- pointer to the snapshot manifest root hash.

`reason_signals` are explicitly marked `NON_CAUSAL_SIGNAL`. They are search leads, not conclusions.

### `data/manifests.json`
`hf-vanished.manifest.v1` records the strongest public file identity information available from the Hub tree API.

For each file HF Vanished may retain:

- path;
- size;
- Git object ID;
- LFS SHA-256 when exposed by the public API;
- Xet hash when exposed by the public API.

The sorted snapshot metadata is canonicalized and SHA-256 hashed into `root_sha256`.

A root hash proves the identity of the **recorded manifest**. It does not prove that HF Vanished possesses or hosts the model bytes.

When the live tree can no longer be fetched, the manifest can fall back to the last public revision and bounded filename sample already recorded by the v1 poller. That state is labelled `LAST_PUBLIC_SAMPLE`, not a complete manifest.

### `data/incidents.json`
`hf-vanished.incidents.v1` contains machine-generated correlation groups.

Current signals include:

- `TEMPORAL_CLUSTER`
- `SAME_OWNER_CLUSTER`
- `SAME_MODEL_FAMILY`

Every generated incident is labelled `CORRELATION_ONLY`.

An incident cluster does **not** establish:

- mass reporting;
- coordination;
- censorship;
- legal action;
- government intervention;
- shared motive.

Those require separate public evidence and, when justified, a sourced entry in `reasons.json`.

## Why capture discussions before a model vanishes?

After a repository becomes private, disabled, or deleted, discussion and commit APIs may no longer be publicly available. The evidence job therefore combines:

1. event-priority refreshes; and
2. a rotating sample of still-public watched repositories.

That lets the project retain bounded public context before it disappears without turning the six-hour job into an unbounded archive crawler.

## Hashing model

There are three different identities and they should not be confused:

1. **Hub revision** — Git repository revision recorded by the normal poller.
2. **File identity** — LFS SHA-256 / Git OID / Xet hash where exposed publicly.
3. **Manifest root SHA-256** — deterministic hash of the file identity manifest HF Vanished recorded.

The evidence object also gets its own `evidence_sha256`, allowing later changes to the evidence cache to be detected.

A future signing layer can sign manifest/evidence roots without changing these schemas.

## Bounded / fail-soft operation

The forensic layer is intentionally secondary to the availability ledger.

- It operates only on a bounded number of models each run.
- Public API failures leave previously cached evidence intact where possible.
- No Hugging Face credential is required.
- A failure to enrich discussions/commits/manifests must not erase or invalidate the v1 disappearance event.

## Reporting a reason

The public issue form accepts source links and discussion/comment links. Submitted explanations remain reports until checked against a public source and deliberately promoted into `data/reasons.json`.

The project should prefer saying **UNKNOWN** over publishing an attractive but unsupported explanation.
