#!/usr/bin/env python3
"""Build aggregate HF Vanished analytics from public ledger/evidence data."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EVENTS = DATA / "events.json"
EVIDENCE = DATA / "evidence.json"
INCIDENTS = DATA / "incidents.json"
OUT = DATA / "analytics.json"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def month(ts: str | None) -> str:
    if not ts:
        return "unknown"
    return str(ts)[:7] if len(str(ts)) >= 7 else "unknown"


def main() -> int:
    events = read(EVENTS, {"events": []}).get("events") or []
    evidence = read(EVIDENCE, {"models": {}}).get("models") or {}
    incidents = read(INCIDENTS, {"incidents": []}).get("incidents") or []

    status = Counter(str(e.get("status") or "UNKNOWN").upper() for e in events)
    by_month = Counter(month(e.get("detected_at")) for e in events)
    owners = Counter(str(e.get("id") or "").split("/", 1)[0] for e in events if e.get("id") and "/" in str(e.get("id")))
    reason_status = Counter()
    reason_category = Counter()
    for row in evidence.values():
        reason = (row or {}).get("reason") or {}
        rs = str(reason.get("status") or "UNKNOWN").upper()
        rc = str(reason.get("category") or "unknown").lower()
        reason_status[rs] += 1
        reason_category[rc] += 1

    reason_total = sum(reason_status.values())
    sourced = reason_total - reason_status.get("UNKNOWN", 0)
    out = {
        "schema": "hf-vanished.analytics.v1",
        "generated_at": now(),
        "summary": {
            "events": len(events),
            "restored": status.get("RESTORED", 0),
            "evidence_packets": len(evidence),
            "sourced_reasons": sourced,
            "unknown_reasons": reason_status.get("UNKNOWN", 0),
            "known_reason_rate": round(sourced / reason_total, 4) if reason_total else 0.0,
            "incident_clusters": len(incidents),
        },
        "event_status": dict(sorted(status.items())),
        "reason_status": dict(sorted(reason_status.items())),
        "reason_category": dict(sorted(reason_category.items())),
        "events_by_month": dict(sorted(by_month.items())),
        "top_event_owners": [{"owner": owner, "events": count} for owner, count in owners.most_common(50)],
        "interpretation": "Aggregate counts describe the HF Vanished ledger. Correlation and category counts do not establish motive beyond the source-backed reason records.",
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(OUT)
    print(f"analytics events={len(events)} sourced_reasons={sourced} incidents={len(incidents)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
