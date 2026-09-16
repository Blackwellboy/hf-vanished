#!/usr/bin/env python3
"""Persistent/enriched runner for HF Vanished."""
from __future__ import annotations

import urllib.parse
import poll

MAX_WEIGHT_NAMES = 96
_original_expand = poll.expand_seeds
_original_classify = poll.classify_http
_original_diff = poll.diff_events
_original_fetch = poll.fetch_model
_original_bootstrap = poll.bootstrap_known


def _license_from_payload(payload: dict) -> str | None:
    card = payload.get("cardData")
    if isinstance(card, dict) and card.get("license"):
        value = card.get("license")
        return ", ".join(str(x) for x in value if x) if isinstance(value, list) else str(value)
    for tag in payload.get("tags") or []:
        if isinstance(tag, str) and tag.lower().startswith("license:"):
            return tag.split(":", 1)[1]
    return None


def enriched_classify(code: int | None, payload: dict | None) -> dict:
    snap = _original_classify(code, payload)
    if code == 200 and isinstance(payload, dict):
        siblings = payload.get("siblings") or []
        weight_files = [
            str(item.get("rfilename")) for item in siblings
            if isinstance(item, dict) and item.get("rfilename")
            and any(str(item.get("rfilename", "")).lower().endswith(ext) for ext in poll.WEIGHT_EXTS)
        ]
        snap.update({
            "license": _license_from_payload(payload),
            "pipeline_tag": payload.get("pipeline_tag"),
            "library_name": payload.get("library_name"),
            "weight_files": weight_files[:MAX_WEIGHT_NAMES],
            "weight_files_truncated": max(0, len(weight_files) - MAX_WEIGHT_NAMES),
        })
    snap["auth_required"] = code in (401, 403)
    return snap


def enriched_fetch(model_id: str) -> dict:
    snap = _original_fetch(model_id)
    if snap.get("visibility") == "public" and not snap.get("disabled"):
        snap["last_public_checked_at"] = snap.get("checked_at")
    return snap


def cumulative_expand(seeds: dict) -> list[str]:
    ids = list(_original_expand(seeds)); seen = set(ids)
    state = poll.load_json(poll.STATE_PATH, {"models": {}})
    for model_id in state.get("models", {}):
        if model_id and model_id not in seen:
            seen.add(model_id); ids.append(model_id)
    return ids


def bootstrap_missing(seeds: dict, state: dict, events: list[dict]) -> None:
    """Curated seeds are bootstrap data, not work to repeat every six hours."""
    existing = {(e.get("id"), str(e.get("status") or "").upper()) for e in events}
    missing = []
    for item in seeds.get("known_events", []):
        if not isinstance(item, dict) or not item.get("id") or not item.get("status"):
            missing.append(item); continue
        key = (item.get("id"), str(item.get("status")).upper())
        if key not in existing or item.get("id") not in state.get("models", {}):
            missing.append(item)
    if not missing:
        return
    subset = dict(seeds); subset["known_events"] = missing
    _original_bootstrap(subset, state, events)


def conservative_diff(prev: dict | None, cur: dict) -> list[tuple[str, str, str]]:
    out = []
    for kind, severity, summary in _original_diff(prev, cur):
        if kind == "private" and cur.get("http") in (401, 403):
            summary = "Unauthenticated access now returns HTTP 401/403 after a prior public observation."
        out.append((kind, severity, summary))
    return out


def enrich_outputs() -> None:
    state = poll.load_json(poll.STATE_PATH, {"models": {}})
    envelope = poll.load_json(poll.EVENTS_PATH, {"events": []})
    for event in envelope.get("events") or []:
        model_id = event.get("id")
        if not model_id: continue
        event["pirateface_url"] = f"https://pirateface.co/{urllib.parse.quote(str(model_id), safe='/')}"
        snap = state.get("models", {}).get(model_id) or {}
        if (event.get("curr") or {}).get("http") in (401, 403):
            event.setdefault("curr", {})["auth_required"] = True
        if any(snap.get(k) is not None for k in ("sha", "license", "file_count", "weight_count", "weight_files")):
            event["last_public"] = {
                "checked_at": snap.get("last_public_checked_at") or snap.get("checked_at"),
                "sha": snap.get("sha"), "license": snap.get("license"),
                "pipeline_tag": snap.get("pipeline_tag"), "library_name": snap.get("library_name"),
                "file_count": snap.get("file_count"), "weight_count": snap.get("weight_count"),
                "weight_files": snap.get("weight_files") or [],
                "weight_files_truncated": snap.get("weight_files_truncated") or 0,
            }
    envelope["cadence"] = "17 */6 * * *"
    poll.save_json(poll.EVENTS_PATH, envelope)


def main() -> int:
    poll.classify_http = enriched_classify
    poll.fetch_model = enriched_fetch
    poll.expand_seeds = cumulative_expand
    poll.bootstrap_known = bootstrap_missing
    poll.diff_events = conservative_diff
    rc = poll.main()
    if rc == 0: enrich_outputs()
    return rc

if __name__ == "__main__": raise SystemExit(main())
