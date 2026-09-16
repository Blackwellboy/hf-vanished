# Independent mirroring

HF Vanished is designed so the public record does not have to depend on one web host, company, or jurisdiction.

The project itself does **not** claim that any particular country or provider is legally safer. Jurisdiction and governance rules change, and legal conclusions need professional advice. Instead, HF Vanished makes the ledger easy to copy and cryptographically compare.

## What a mirror should carry

At minimum mirror:

- `index.html`
- `assets/`
- `data/events.json`
- `data/status.json`
- `data/evidence.json`
- `data/manifests.json`
- `data/incidents.json`
- `data/lineage.json`
- `data/analytics.json`
- `data/provenance.json`
- `data/provenance.sigstore.json` when available
- `data/mirrors.json`

A plain Git clone or static-file sync is enough. No database is required.

## Verification

`data/provenance.json` lists SHA-256 digests for the core public feeds and a deterministic root SHA-256.

A mirror can therefore publish:

- the upstream Git commit it mirrored;
- the observed `provenance.root_sha256`;
- its last successful verification timestamp.

When the GitHub Actions keyless-signing step succeeds, `data/provenance.sigstore.json` additionally provides a Sigstore bundle for the provenance file.

A mirror matching the same root is serving the same recorded ledger payload even if its hostname, operator, hosting provider, or jurisdiction differs.

## Mirror registry

Candidate mirrors are listed in `data/mirrors.json` only after public verification.

Suggested mirror entry:

```json
{
  "id": "example-mirror",
  "url": "https://example.invalid/hf-vanished/",
  "operator": "Example operator",
  "jurisdiction": "operator supplied description",
  "provider": "operator supplied description",
  "verified_at": "2026-09-16T00:00:00Z",
  "provenance_root_sha256": "...",
  "status": "VERIFIED"
}
```

Jurisdiction/provider fields are descriptive. They are not endorsements and do not imply immunity from takedowns or regulation.

## Why multiple mirrors help

Independent mirrors reduce dependence on one domain or provider and make historical rewriting easier to detect.

They do **not** make unlawful material lawful, override upstream licences, or guarantee permanent availability.

HF Vanished's role is the evidence ledger. Model files and third-party archives remain subject to their own licences, terms, and applicable law.
