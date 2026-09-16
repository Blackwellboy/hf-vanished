#!/usr/bin/env python3
"""Create a deterministic digest index for HF Vanished public forensic feeds."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "provenance.json"
FILES = [
    "events.json",
    "state.json",
    "status.json",
    "integrations.json",
    "reasons.json",
    "evidence.json",
    "manifests.json",
    "incidents.json",
    "lineage.json",
    "analytics.json",
    "mirrors.json",
]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    entries = []
    for name in FILES:
        path = DATA / name
        if not path.exists():
            continue
        raw = path.read_bytes()
        entries.append({"path": f"data/{name}", "size": len(raw), "sha256": sha256_bytes(raw)})
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    out = {
        "schema": "hf-vanished.provenance.v1",
        "generated_at": now(),
        "algorithm": "sha256",
        "files": entries,
        "root_sha256": sha256_bytes(canonical),
        "signature": {
            "mode": "sigstore-keyless-if-available",
            "bundle_path": "data/provenance.sigstore.json",
            "note": "The digest bundle is always generated. A detached Sigstore bundle is produced by GitHub Actions when keyless signing succeeds."
        },
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(OUT)
    print(f"provenance files={len(entries)} root={out['root_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
