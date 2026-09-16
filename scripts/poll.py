#!/usr/bin/env python3
"""hf-vanished poller — public HF Hub + Wayback CDX only. No tokens."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SEEDS_PATH = DATA / "seeds.json"
STATE_PATH = DATA / "state.json"
EVENTS_PATH = DATA / "events.json"

UA = "hf-vanished/0.1 (+https://github.com/Blackwellboy/hf-vanished; public ledger)"
WEIGHT_EXTS = (".safetensors", ".bin", ".gguf", ".pt", ".ckpt", ".pth", ".msgpack")

# Ignore flaps shorter than this between public↔non-public (hours).
FLAP_HOURS = 24


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def http_get(url: str, timeout: int = 45) -> tuple[int | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body
    except Exception as e:
        return None, repr(e)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open() as f:
        return json.load(f)


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def classify_http(code: int | None, payload: dict | None) -> dict[str, Any]:
    """Map Hub response → normalized visibility snapshot."""
    if code == 200 and isinstance(payload, dict):
        siblings = payload.get("siblings") or []
        weight_files = [
            s.get("rfilename")
            for s in siblings
            if isinstance(s, dict)
            and any(str(s.get("rfilename", "")).lower().endswith(ext) for ext in WEIGHT_EXTS)
        ]
        gated = payload.get("gated")
        return {
            "visibility": "disabled"
            if payload.get("disabled")
            else ("private" if payload.get("private") else "public"),
            "disabled": bool(payload.get("disabled")),
            "private": bool(payload.get("private")),
            "gated": False if gated in (None, False, "", 0) else gated,
            "downloads": payload.get("downloads"),
            "likes": payload.get("likes"),
            "sha": payload.get("sha"),
            "last_modified": payload.get("lastModified"),
            "file_count": len(siblings),
            "weight_count": len(weight_files),
            "http": 200,
        }
    if code == 404:
        return {
            "visibility": "deleted",
            "disabled": False,
            "private": False,
            "gated": False,
            "http": 404,
            "file_count": 0,
            "weight_count": 0,
        }
    if code in (401, 403):
        # Unauthenticated Hub API returns 401/403 for private repos.
        return {
            "visibility": "private",
            "disabled": False,
            "private": True,
            "gated": False,
            "http": code,
            "file_count": 0,
            "weight_count": 0,
        }
    return {
        "visibility": "unknown",
        "disabled": False,
        "private": False,
        "gated": False,
        "http": code,
        "error": True,
    }


def fetch_model(model_id: str) -> dict[str, Any]:
    url = f"https://huggingface.co/api/models/{urllib.parse.quote(model_id, safe='/')}"
    code, body = http_get(url)
    payload = None
    if code == 200:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            code = None
    snap = classify_http(code, payload)
    snap["id"] = model_id
    snap["checked_at"] = utc_now()
    return snap


def wayback_last_public(model_id: str) -> dict[str, str] | None:
    page = f"https://huggingface.co/{model_id}"
    q = urllib.parse.urlencode(
        {
            "url": page,
            "output": "json",
            "fl": "timestamp,original,statuscode",
            "filter": "statuscode:200",
            "limit": "-1",
            "fastLatest": "true",
        }
    )
    code, body = http_get(f"https://web.archive.org/cdx/search/cdx?{q}", timeout=70)
    if code != 200:
        return None
    try:
        rows = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(rows, list) or len(rows) < 2:
        return None
    ts, original, _sc = rows[1]
    return {
        "timestamp": ts,
        "url": f"https://web.archive.org/web/{ts}/{original}",
    }


def expand_seeds(seeds: dict) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()

    def add(mid: str) -> None:
        mid = mid.strip()
        if mid and mid not in seen:
            seen.add(mid)
            ids.append(mid)

    for mid in seeds.get("watchlist", []):
        add(mid)
    for mid in seeds.get("known_events", []):
        if isinstance(mid, str):
            add(mid)
        elif isinstance(mid, dict) and mid.get("id"):
            add(mid["id"])

    # Live keyword / tag family search (public API).
    for family in seeds.get("search_families", []):
        q = family if isinstance(family, str) else family.get("query", "")
        if not q:
            continue
        limit = 25 if isinstance(family, str) else int(family.get("limit", 25))
        url = (
            "https://huggingface.co/api/models?"
            + urllib.parse.urlencode(
                {"search": q, "limit": limit, "sort": "downloads", "direction": -1}
            )
        )
        code, body = http_get(url, timeout=40)
        if code != 200:
            print(f"warn: search {q!r} -> HTTP {code}", file=sys.stderr)
            continue
        try:
            models = json.loads(body)
        except json.JSONDecodeError:
            continue
        for m in models:
            mid = m.get("modelId") or m.get("id")
            if mid:
                add(mid)
        time.sleep(0.15)

    # Top / popular slice.
    top_n = int(seeds.get("top_n", 40))
    url = (
        "https://huggingface.co/api/models?"
        + urllib.parse.urlencode({"limit": top_n, "sort": "downloads", "direction": -1})
    )
    code, body = http_get(url, timeout=40)
    if code == 200:
        try:
            for m in json.loads(body):
                mid = m.get("modelId") or m.get("id")
                if mid:
                    add(mid)
        except json.JSONDecodeError:
            pass
    return ids


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def hours_between(a: str | None, b: str | None) -> float | None:
    da, db = parse_iso(a), parse_iso(b)
    if not da or not db:
        return None
    return abs((db - da).total_seconds()) / 3600.0


def event_status(kind: str) -> str:
    return {
        "disabled": "DISABLED",
        "deleted": "DELETED",
        "private": "PRIVATE",
        "gated": "GATED",
        "stripped": "STRIPPED",
    }[kind]


def make_event(
    model_id: str,
    kind: str,
    severity: str,
    summary: str,
    prev: dict | None,
    cur: dict,
    wayback: dict | None,
) -> dict[str, Any]:
    ev = {
        "id": model_id,
        "status": event_status(kind),
        "severity": severity,  # hard | soft
        "kind": kind,
        "summary": summary,
        "detected_at": cur.get("checked_at") or utc_now(),
        "hf_url": f"https://huggingface.co/{model_id}",
        "prev": {
            "visibility": (prev or {}).get("visibility"),
            "gated": (prev or {}).get("gated"),
            "weight_count": (prev or {}).get("weight_count"),
            "checked_at": (prev or {}).get("checked_at"),
        },
        "curr": {
            "visibility": cur.get("visibility"),
            "gated": cur.get("gated"),
            "disabled": cur.get("disabled"),
            "weight_count": cur.get("weight_count"),
            "http": cur.get("http"),
            "checked_at": cur.get("checked_at"),
        },
    }
    if wayback:
        ev["wayback_url"] = wayback.get("url")
        ev["wayback_timestamp"] = wayback.get("timestamp")
    return ev


def diff_events(prev: dict | None, cur: dict) -> list[tuple[str, str, str]]:
    """Return list of (kind, severity, summary)."""
    out: list[tuple[str, str, str]] = []
    if cur.get("error") or cur.get("visibility") == "unknown":
        return out

    # Always-private: never observed public → ignore PRIVATE/DELETED noise.
    always_private = bool((prev or {}).get("always_private"))
    seen_public = bool((prev or {}).get("seen_public")) or (
        prev is not None and prev.get("visibility") == "public" and not prev.get("disabled")
    )

    if prev is None:
        # First observation: record hard terminal states only when we already
        # know the model was public (seed known_events handled separately).
        return out

    prev_vis = prev.get("visibility")
    cur_vis = cur.get("visibility")

    if cur.get("disabled") and not prev.get("disabled"):
        out.append(("disabled", "hard", "Repo disabled on the Hub after previously being available."))

    if cur_vis == "deleted" and prev_vis != "deleted":
        if seen_public or prev_vis == "public":
            out.append(("deleted", "hard", "Repo returned HTTP 404 after previously resolving."))
        # else: ignore unknown→deleted without public evidence

    if cur_vis == "private" and prev_vis == "public" and not always_private:
        out.append(("private", "hard", "Repo requires auth (taken private) after a public observation."))

    # Soft: newly gated while remaining listed.
    prev_gated = prev.get("gated") not in (False, None, "", 0)
    cur_gated = cur.get("gated") not in (False, None, "", 0)
    if cur_vis == "public" and cur_gated and not prev_gated and not cur.get("disabled"):
        out.append(
            (
                "gated",
                "soft",
                f"Newly gated ({cur.get('gated')!r}) after an open observation.",
            )
        )

    # Soft: weight strip while repo remains.
    if (
        cur_vis == "public"
        and not cur.get("disabled")
        and isinstance(prev.get("weight_count"), int)
        and isinstance(cur.get("weight_count"), int)
        and prev["weight_count"] > 0
        and cur["weight_count"] == 0
    ):
        out.append(
            (
                "stripped",
                "soft",
                f"Weight files removed ({prev['weight_count']} → 0) while repo listing remains.",
            )
        )

    return out


def merge_event(events: list[dict], new: dict) -> None:
    """Upsert by (id, status); keep earliest detected_at, refresh curr/wayback."""
    for i, ev in enumerate(events):
        if ev.get("id") == new["id"] and ev.get("status") == new["status"]:
            merged = dict(ev)
            # Keep original detection time; refresh evidence.
            for k in ("summary", "curr", "wayback_url", "wayback_timestamp", "severity", "kind", "hf_url"):
                if k in new and new[k] is not None:
                    merged[k] = new[k]
            if new.get("prev") and not merged.get("prev"):
                merged["prev"] = new["prev"]
            events[i] = merged
            return
    events.append(new)


def bootstrap_known(seeds: dict, state: dict, events: list[dict]) -> None:
    """Inject curated known hard/soft events (real IDs only)."""
    for item in seeds.get("known_events", []):
        if not isinstance(item, dict) or not item.get("id") or not item.get("status"):
            continue
        mid = item["id"]
        snap = fetch_model(mid)
        time.sleep(0.1)
        want = str(item["status"]).upper()

        # Refuse to seed a status that contradicts the live Hub response.
        if want == "PRIVATE" and snap.get("visibility") != "private":
            print(f"skip seed PRIVATE {mid}: live visibility={snap.get('visibility')}", file=sys.stderr)
            continue
        if want == "DELETED" and snap.get("visibility") != "deleted":
            print(f"skip seed DELETED {mid}: live visibility={snap.get('visibility')}", file=sys.stderr)
            continue
        if want == "DISABLED" and not snap.get("disabled"):
            print(f"skip seed DISABLED {mid}: live disabled={snap.get('disabled')}", file=sys.stderr)
            continue
        if want == "GATED" and snap.get("gated") in (False, None, "", 0):
            print(f"skip seed GATED {mid}: live gated={snap.get('gated')!r}", file=sys.stderr)
            continue

        st = state.get("models", {}).get(mid, {})
        if snap.get("visibility") == "public" and not snap.get("disabled"):
            st["seen_public"] = True
        if item.get("was_public"):
            st["seen_public"] = True
            st["always_private"] = False
        elif snap.get("visibility") == "private" and not st.get("seen_public"):
            st["always_private"] = st.get("always_private", True)
        st.update({k: snap.get(k) for k in snap})
        state.setdefault("models", {})[mid] = st

        wb = None
        if item.get("wayback_url"):
            wb = {
                "url": item["wayback_url"],
                "timestamp": item.get("wayback_timestamp") or "",
            }
        elif want in ("DISABLED", "DELETED", "PRIVATE") or snap.get("disabled"):
            wb = wayback_last_public(mid)
            time.sleep(0.2)

        summary = item.get("summary") or f"Seeded {item['status']} observation."
        ev = {
            "id": mid,
            "status": want,
            "severity": item.get("severity", "hard"),
            "kind": item.get("kind") or want.lower(),
            "summary": summary,
            "detected_at": item.get("detected_at") or snap.get("checked_at") or utc_now(),
            "hf_url": f"https://huggingface.co/{mid}",
            "source": "seed",
            "curr": {
                "visibility": snap.get("visibility"),
                "gated": snap.get("gated"),
                "disabled": snap.get("disabled"),
                "weight_count": snap.get("weight_count"),
                "http": snap.get("http"),
                "checked_at": snap.get("checked_at"),
            },
        }
        if wb:
            ev["wayback_url"] = wb.get("url")
            if wb.get("timestamp"):
                ev["wayback_timestamp"] = wb["timestamp"]
        merge_event(events, ev)


def main() -> int:
    seed_only = "--seed-only" in sys.argv
    seeds = load_json(SEEDS_PATH, {})
    state = load_json(STATE_PATH, {"models": {}, "updated_at": None})
    envelope = load_json(EVENTS_PATH, {"generated_at": None, "schema": "hf-vanished.events.v1", "events": []})
    events: list[dict] = list(envelope.get("events") or [])

    bootstrap_known(seeds, state, events)

    if seed_only:
        watch_ids = []
        print("seed-only: skipping full watch expansion", file=sys.stderr)
    else:
        watch_ids = expand_seeds(seeds)
    print(f"watching {len(watch_ids)} model ids", file=sys.stderr)

    for mid in watch_ids:
        cur = fetch_model(mid)
        prev = state.get("models", {}).get(mid)

        # Track public sightings / always-private.
        if prev is None:
            prev_rec: dict[str, Any] = {}
            if cur.get("visibility") == "private":
                prev_rec["always_private"] = True
            elif cur.get("visibility") == "public":
                prev_rec["seen_public"] = True
                prev_rec["always_private"] = False
        else:
            prev_rec = dict(prev)
            if cur.get("visibility") == "public" and not cur.get("disabled"):
                prev_rec["seen_public"] = True
                prev_rec["always_private"] = False

        # Flap suppression: if we recently flipped and flipped back, skip.
        last_event_at = prev_rec.get("last_event_at")
        gap = hours_between(last_event_at, cur.get("checked_at"))

        changes = diff_events(prev if prev else None, cur)
        for kind, severity, summary in changes:
            if gap is not None and gap < FLAP_HOURS and prev_rec.get("last_event_kind") == kind:
                print(f"skip flap {mid} {kind}", file=sys.stderr)
                continue
            # Ignore private without public history.
            if kind == "private" and not prev_rec.get("seen_public"):
                continue
            wb = None
            if kind in ("disabled", "deleted", "private"):
                wb = wayback_last_public(mid)
                time.sleep(0.15)
            ev = make_event(mid, kind, severity, summary, prev, cur, wb)
            merge_event(events, ev)
            prev_rec["last_event_at"] = cur.get("checked_at")
            prev_rec["last_event_kind"] = kind
            print(f"event {ev['status']} {mid}", file=sys.stderr)

        # Persist snapshot
        prev_rec.update({k: cur.get(k) for k in cur})
        state.setdefault("models", {})[mid] = prev_rec
        time.sleep(0.08)

    # Sort: hard first, then newest detected_at.
    sev_rank = {"hard": 0, "soft": 1}

    def sort_key(e: dict) -> tuple:
        return (
            sev_rank.get(e.get("severity", "soft"), 9),
            e.get("detected_at") or "",
            e.get("id") or "",
        )

    events_sorted = sorted(events, key=sort_key, reverse=False)
    # Within same severity, newest first
    hard = [e for e in events_sorted if e.get("severity") == "hard"]
    soft = [e for e in events_sorted if e.get("severity") != "hard"]
    hard.sort(key=lambda e: e.get("detected_at") or "", reverse=True)
    soft.sort(key=lambda e: e.get("detected_at") or "", reverse=True)
    events_out = hard + soft

    state["updated_at"] = utc_now()
    envelope = {
        "generated_at": utc_now(),
        "schema": "hf-vanished.events.v1",
        "cadence": "0 */6 * * *",
        "source": "https://github.com/Blackwellboy/hf-vanished",
        "events": events_out,
    }
    save_json(STATE_PATH, state)
    save_json(EVENTS_PATH, envelope)
    print(f"wrote {EVENTS_PATH} ({len(events_out)} events)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
