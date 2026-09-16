#!/usr/bin/env python3
"""Build explicit model lineage from public Hub base_model metadata only."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE = DATA / "state.json"
LINEAGE = DATA / "lineage.json"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def main() -> int:
    state = read(STATE, {"models": {}})
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    seen_edges = set()
    for mid, snap in (state.get("models") or {}).items():
        if not mid:
            continue
        nodes[mid] = {
            "id": mid,
            "visibility": snap.get("visibility"),
            "revision": snap.get("sha"),
            "license": snap.get("license"),
            "pipeline_tag": snap.get("pipeline_tag"),
        }
        bases = snap.get("base_models") or []
        if isinstance(bases, str):
            bases = [bases]
        for base in bases:
            base = str(base).strip()
            if not base:
                continue
            nodes.setdefault(base, {"id": base, "external_to_watchset": base not in (state.get("models") or {})})
            key = (base, mid, "DECLARED_BASE_MODEL")
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({
                "from": base,
                "to": mid,
                "relation": "DECLARED_BASE_MODEL",
                "evidence": "Hugging Face model-card base_model metadata",
                "inferred": False,
            })
    out = {
        "schema": "hf-vanished.lineage.v1",
        "generated_at": now(),
        "policy": "Only explicit public base_model metadata creates lineage edges. Name similarity is not treated as provenance.",
        "nodes": nodes,
        "edges": edges,
    }
    tmp = LINEAGE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(LINEAGE)
    print(f"lineage nodes={len(nodes)} edges={len(edges)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
